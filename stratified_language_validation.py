"""Deterministic within-document validation windows and explicit CPU FP32 CE.

Pure helpers: no file reads, private data, packing, training or device discovery.
Document SHA-256 means little-endian uint16 token bytes INCLUDING terminal EOT,
not source-text bytes. Callers own immutable input arrays and runtime budgets.
"""
from collections import defaultdict
import hashlib
import json
import math

import numpy as np


SCHEME='source-document-sha256-order-and-start-v1'


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def token_sha256(array):
    """Hash contiguous little-endian uint16 storage in bounded zero-copy chunks."""
    if (not isinstance(array,np.ndarray) or array.ndim!=1 or array.dtype.str!='<u2'
            or not array.flags.c_contiguous):
        raise ValueError('contiguous little-endian uint16 token array required')
    raw=memoryview(array).cast('B');digest=hashlib.sha256()
    for offset in range(0,len(raw),1024*1024):digest.update(raw[offset:offset+1024*1024])
    return digest.hexdigest()


def _positive_integer(value,name):
    if type(value)!=int or value<=0:raise ValueError(name+' must be a positive integer')


def _shards(shards,pins,vocab_size,eot):
    if not isinstance(shards,dict) or not shards or set(shards)!=set(pins):
        raise ValueError('shards and exact source pins required')
    _positive_integer(vocab_size,'vocabulary size')
    if vocab_size>65536 or type(eot)!=int or not 0<=eot<vocab_size:
        raise ValueError('invalid uint16 vocabulary/EOT')
    for source,array in shards.items():
        if not isinstance(source,str) or not source:raise ValueError('nonempty source name required')
        actual_hash=token_sha256(array)
        pin=pins[source]
        if set(pin)!={'tokens','sha256'} or type(pin['tokens'])!=int or pin['tokens']!=array.size:
            raise ValueError('source token count/pin mismatch')
        if actual_hash!=pin['sha256']:raise ValueError('source hash mismatch')
        if array.size==0 or int(array.max())>=vocab_size:
            raise ValueError('empty source or out-of-vocabulary token')


def _documents(shards,documents,eot):
    records={};by_source=defaultdict(list)
    for row in documents:
        required={'source','document_id','offset','tokens','document_sha256'}
        if set(row)!=required:raise ValueError('document record fields differ from contract')
        source,identifier=row['source'],row['document_id']
        if source not in shards or not isinstance(identifier,str) or not identifier:
            raise ValueError('invalid document source/id')
        key=(source,identifier)
        if key in records:raise ValueError('duplicate source/document ID')
        offset,count=row['offset'],row['tokens']
        if type(offset)!=int or offset<0 or type(count)!=int or count<2 or offset+count>shards[source].size:
            raise ValueError('document bounds invalid')
        tokens=shards[source][offset:offset+count]
        if int(tokens[-1])!=eot or bool(np.any(tokens[:-1]==eot)):
            raise ValueError('document requires one terminal EOT and no interior EOT')
        if token_sha256(tokens)!=row['document_sha256']:raise ValueError('document token hash mismatch')
        records[key]=dict(row);by_source[source].append(dict(row))
    for source,rows in by_source.items():
        previous_end=-1
        for row in sorted(rows,key=lambda r:(r['offset'],r['document_id'])):
            if row['offset']<previous_end:raise ValueError('overlapping source document spans')
            previous_end=row['offset']+row['tokens']
    return records,by_source


def select_windows(shards,documents,source_pins,*,seed,documents_per_source=128,
                   min_targets=32,max_targets=512,vocab_size=50257,eot=50256,
                   per_source_quotas=None,short_boundary_targets=128):
    if type(seed)!=int:raise ValueError('integer seed required')
    for value,name in [(documents_per_source,'documents_per_source'),(min_targets,'min_targets'),(max_targets,'max_targets')]:
        _positive_integer(value,name)
    if max_targets<min_targets:raise ValueError('maximum targets below minimum')
    if type(short_boundary_targets)!=int or short_boundary_targets<=min_targets:
        raise ValueError('short boundary must exceed minimum targets')
    if per_source_quotas is not None:
        if not isinstance(per_source_quotas,dict) or set(per_source_quotas)!=set(shards):
            raise ValueError('quotas required for exactly all sources')
        for quota in per_source_quotas.values():
            if (set(quota)!={'short','long'} or any(type(n)!=int or n<0 for n in quota.values())
                    or sum(quota.values())!=documents_per_source):
                raise ValueError('nonnegative short/long quotas must sum to per-source count')
    _shards(shards,source_pins,vocab_size,eot)
    _,by_source=_documents(shards,documents,eot)
    windows=[];counts={}
    def priority(source,identifier):
        return hashlib.sha256(canonical([SCHEME,'select',seed,source,identifier])).hexdigest()
    for source in sorted(shards):
        rows=by_source[source]
        eligible=[r for r in rows if r['tokens']-1>=min_targets]
        if len(eligible)<documents_per_source:
            raise ValueError(f'{source}: insufficient distinct eligible documents')
        ordered=sorted(eligible,key=lambda r:(priority(source,r['document_id']),r['document_id']))
        if per_source_quotas is None:
            selected=ordered[:documents_per_source]
        else:
            selected=[]
            for label in ('short','long'):
                pool=[r for r in ordered if ('short' if r['tokens']-1<short_boundary_targets else 'long')==label]
                quota=per_source_quotas[source][label]
                if len(pool)<quota:raise ValueError(f'{source}: insufficient {label} documents for frozen quota')
                selected.extend(pool[:quota])
            selected.sort(key=lambda r:(priority(source,r['document_id']),r['document_id']))
        counts[source]=dict(total_documents=len(rows),eligible_documents=len(eligible),
                            excluded_too_short=len(rows)-len(eligible),selected_documents=len(selected),
                            eligible_short_documents=sum(r['tokens']-1<short_boundary_targets for r in eligible),
                            selected_short_documents=sum(r['tokens']-1<short_boundary_targets for r in selected))
        for row in selected:
            targets=min(max_targets,row['tokens']-1)
            largest_start=row['tokens']-(targets+1)
            start_hash=hashlib.sha256(canonical([SCHEME,'start',seed,source,row['document_id']])).hexdigest()
            local=int(start_hash,16)%(largest_start+1)
            start=row['offset']+local
            window=shards[source][start:start+targets+1]
            windows.append(dict(source=source,document_id=row['document_id'],document_offset=row['offset'],
                                document_tokens=row['tokens'],document_sha256=row['document_sha256'],
                                source_sha256=source_pins[source]['sha256'],start=start,local_start=local,
                                targets=targets,length_stratum='short' if row['tokens']-1<short_boundary_targets else 'long',
                                window_sha256=token_sha256(window)))
    manifest=dict(schema=1,scheme=SCHEME,seed=seed,documents_per_source=documents_per_source,
                  min_targets=min_targets,max_targets=max_targets,vocab_size=vocab_size,eot=eot,
                  source_pins=json.loads(canonical(source_pins)),counts=counts,windows=windows,
                  sampling_policy=dict(mode='per-source-length-quotas' if per_source_quotas is not None else 'uniform-documents',
                    short_boundary_targets=short_boundary_targets,
                    quotas=json.loads(canonical(per_source_quotas)),population_estimate=False,
                    interpretation='Descriptive selected-document means; no population reweighting.'))
    manifest['selection_sha256']=hashlib.sha256(canonical(manifest)).hexdigest()
    return manifest


def verify_windows(shards,manifest,*,expected_selection_sha256):
    plain={k:v for k,v in manifest.items() if k!='selection_sha256'}
    actual=hashlib.sha256(canonical(plain)).hexdigest()
    if actual!=expected_selection_sha256 or manifest.get('selection_sha256')!=actual:
        raise ValueError('validation window identity changed')
    if manifest.get('schema')!=1 or manifest.get('scheme')!=SCHEME:
        raise ValueError('unsupported window schema')
    for field in ('documents_per_source','min_targets','max_targets'):
        _positive_integer(manifest[field],field)
    if manifest['max_targets']<manifest['min_targets']:
        raise ValueError('maximum targets below minimum')
    boundary=manifest['sampling_policy']['short_boundary_targets']
    if type(boundary)!=int or boundary<=manifest['min_targets']:
        raise ValueError('invalid length-stratum boundary')
    _shards(shards,manifest['source_pins'],manifest['vocab_size'],manifest['eot'])
    docs=[dict(source=w['source'],document_id=w['document_id'],offset=w['document_offset'],
               tokens=w['document_tokens'],document_sha256=w['document_sha256']) for w in manifest['windows']]
    _,grouped=_documents(shards,docs,manifest['eot'])
    if set(grouped)!=set(shards) or any(len(grouped[s])!=manifest['documents_per_source'] for s in shards):
        raise ValueError('wrong per-source window count')
    policy=manifest['sampling_policy']
    if policy['mode'] not in ('uniform-documents','per-source-length-quotas') or policy['population_estimate'] is not False:
        raise ValueError('invalid sampling policy')
    for row in manifest['windows']:
        if row['length_stratum']!=('short' if row['document_tokens']-1<policy['short_boundary_targets'] else 'long'):
            raise ValueError('document length stratum changed')
        length=row['targets'];local=row['local_start'];start=row['start']
        if (type(length)!=int or length!=min(manifest['max_targets'],row['document_tokens']-1)
                or not manifest['min_targets']<=length<=manifest['max_targets']
                or type(local)!=int or not 0<=local<=row['document_tokens']-length-1
                or start!=row['document_offset']+local):
            raise ValueError('invalid within-document window bounds')
        if row['source_sha256']!=manifest['source_pins'][row['source']]['sha256']:
            raise ValueError('window source pin mismatch')
        if token_sha256(shards[row['source']][start:start+length+1])!=row['window_sha256']:
            raise ValueError('window token hash mismatch')
    if policy['mode']=='per-source-length-quotas':
        if set(policy['quotas'])!=set(shards):raise ValueError('quota source set mismatch')
        for source in shards:
            quota=policy['quotas'][source]
            if (set(quota)!={'short','long'} or any(type(n)!=int or n<0 for n in quota.values())
                    or sum(quota.values())!=manifest['documents_per_source']):
                raise ValueError('invalid frozen length quotas')
            for label in ('short','long'):
                if sum(w['source']==source and w['length_stratum']==label for w in manifest['windows'])!=policy['quotas'][source][label]:
                    raise ValueError('selected window strata differ from quota')
    elif policy['quotas'] is not None:raise ValueError('uniform mode cannot carry quotas')
    return manifest['windows']


def summarize(rows, *, sampling_policy=None):
    if not rows:raise ValueError('no document losses to summarize')
    groups=defaultdict(list);keys=set()
    for row in rows:
        if row.get('length_stratum') not in ('short','long'):raise ValueError('length stratum required')
        key=(row['source'],row['document_id'])
        if key in keys:raise ValueError('duplicate scored document')
        keys.add(key)
        if (type(row['targets'])!=int or row['targets']<=0 or not math.isfinite(row['nll_sum'])
                or row['nll_sum']<0):raise ValueError('invalid scored target count/loss')
        groups[row['source']].append(row)
    def aggregate(items):
        tokens=sum(r['targets'] for r in items)
        loss=math.fsum(r['nll_sum'] for r in items)
        return dict(documents=len(items),targets=tokens,nll_sum=loss,
                    document_mean_ce=math.fsum(r['nll_sum']/r['targets'] for r in items)/len(items),
                    token_weighted_ce=loss/tokens)
    by_source={s:dict(aggregate(groups[s]),by_length_stratum={label:aggregate([r for r in groups[s] if r['length_stratum']==label])
                  for label in ('short','long') if any(r['length_stratum']==label for r in groups[s])}) for s in sorted(groups)}
    return dict(overall=aggregate(rows),by_source=by_source,population_estimate=False,
                sampling_policy=sampling_policy,interpretation='Descriptive means over selected documents only; no population reweighting.',
                source_balanced_document_mean_ce=math.fsum(r['document_mean_ce'] for r in by_source.values())/len(by_source))


def evaluate_cpu(model,shards,manifest,*,expected_selection_sha256,check=None):
    """CPU-only FP32 inference. Validate all source/doc/window pins before calls."""
    import torch
    from torch.nn import functional as F
    rows=verify_windows(shards,manifest,expected_selection_sha256=expected_selection_sha256)
    tensors=list(model.parameters())+list(model.buffers())
    if any(t.device.type!='cpu' or t.is_floating_point() and t.dtype!=torch.float32 for t in tensors):
        raise ValueError('CPU model with FP32 floating tensors required')
    was_training=model.training;model.eval();losses=[]
    try:
        with torch.inference_mode(),torch.autocast('cpu',enabled=False):
            for row in rows:
                if check is not None:check()
                tokens=shards[row['source']][row['start']:row['start']+row['targets']+1]
                if token_sha256(tokens)!=row['window_sha256']:raise ValueError('window changed before model call')
                sequence=torch.from_numpy(tokens.astype(np.int64)).unsqueeze(0)
                logits=model(sequence[:,:-1])
                if (not isinstance(logits,torch.Tensor) or logits.device.type!='cpu' or logits.dtype!=torch.float32
                        or tuple(logits.shape)!=(1,row['targets'],manifest['vocab_size'])
                        or not bool(torch.isfinite(logits).all())):
                    raise ValueError('model must return finite CPU FP32 [1,T,vocabulary] logits')
                total=F.cross_entropy(logits.reshape(-1,manifest['vocab_size']),sequence[:,1:].reshape(-1),reduction='sum')
                value=float(total.item())
                if not math.isfinite(value):raise ValueError('nonfinite document cross entropy')
                losses.append(dict(row,nll_sum=value,mean_ce=value/row['targets']))
    finally:model.train(was_training)
    return dict(selection_sha256=expected_selection_sha256,device='cpu',dtype='float32',
                documents=losses,summary=summarize(losses,sampling_policy=manifest['sampling_policy']))
