"""Finite own-base SFT with exact resume and assistant-token-weighted loss.

Inputs must be explicitly admitted canonical JSONL conversations. This does not
admit data, provision a GPU, replace a base checkpoint, run Python tool frames or
claim conversation quality from language loss. Use a separately reserved lease.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import math
import random
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import time

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cloud_training.nano_benchmark import BATCH, PINNED_REVISION, atomic_json, deterministic_attention
from cloud_training.nano_chat_format import VERSION, encode_conversation
from cloud_training.nano_quality_gate import dataset_coverage, contract_errors, ValidationGuard, evaluation_candidates
from cloud_training.nano_data import sha256_file
from cloud_training.nano_train import CloudJournal, deadline_timestamp, numerical_identity

NATIVE_IGNORE = -1  # Pinned nanochat GPT.forward, distinct from export labels -100.
from cloud_training.nano_context import DEFAULT_CONTEXT, SUPPORTED_CONTEXTS, transition_config, validate_context_edge
SEQUENCE = DEFAULT_CONTEXT


def sft_schedule(progress, step):
    if not 0 <= progress <= 1 or step < 0:
        raise ValueError('Invalid SFT progress')
    return (1.0 if progress <= .5 else 2*(1-progress)), .85 + .10*min(step/300,1)


def batch_recipe(batch_tokens, microbatch, context=SEQUENCE):
    """Explicit position-token batch, not assistant-target batch; never repeats data."""
    if type(context) is not int or context not in SUPPORTED_CONTEXTS:raise ValueError('Unsupported sequence length')
    if type(batch_tokens) is not int or not 8192<=batch_tokens<=BATCH or batch_tokens%context:
        raise ValueError("Effective batch must be8192..524288 and divisible by the selected context")
    rows=batch_tokens//context
    if type(microbatch) is not int or microbatch<1 or rows%microbatch:
        raise ValueError("Microbatch must divide effective batch rows")
    return {"batch_tokens":batch_tokens,"rows_per_update":rows,"lr_batch_scale":math.sqrt(batch_tokens/BATCH)}


def reset_sft_lrs(optimizer, fresh_lrs, batch_scale=1.0, multiplier=1.0):
    """Fresh LR ×0.8×sqrt(batch/reference), retaining moments from the parent.

    Square-root scaling is an explicit conservative heuristic, not an assertion
    of equivalent AdamW/Muon dynamics; select targeted settings on held-out dev.
    """
    if isinstance(batch_scale,bool) or not isinstance(batch_scale,(int,float)) or not math.isfinite(batch_scale) or not 0<batch_scale<=1:
        raise ValueError("Invalid LR batch scale")
    if isinstance(multiplier,bool) or not isinstance(multiplier,(int,float)) or not math.isfinite(multiplier) or not 0<multiplier<=1:
        raise ValueError('LR multiplier must be finite in (0,1]')
    if len(optimizer.param_groups)!=len(fresh_lrs):
        raise ValueError('Optimizer group mismatch')
    for group,lr in zip(optimizer.param_groups,fresh_lrs):
        group['lr']=group['initial_lr']=lr*.8*batch_scale*multiplier
        if group.get('kind')=='muon':group['weight_decay']=0.0


def load_manifest(path, tokenizer_sha, context=SEQUENCE):
    path=Path(path).resolve();m=json.loads(path.read_text())
    if m.get('schema')!=1 or m.get('training_admitted') is not True or m.get('format_version')!=VERSION:
        raise ValueError('Admitted SFT manifest with exact format version required')
    if m.get('tokenizer_sha256')!=tokenizer_sha or m.get('context_tokens')!=context:
        raise ValueError('SFT tokenizer/context mismatch')
    admission=m.get('admission',{});receipt=path.parent/admission.get('receipt','')
    if not receipt.is_file() or sha256_file(receipt)!=admission.get('sha256'):
        raise ValueError('Missing/changed SFT admission receipt')
    review=json.loads(receipt.read_text())
    if context==4096 and review.get('context_tokens')!=context:raise ValueError('4K admission receipt must bind context')
    expected=[m.get(k,{}).get('sha256') for k in ('train','validation')]
    if (review.get('training_admitted') is not True or review.get('tokenizer_sha256')!=tokenizer_sha
        or review.get('format_version')!=VERSION or review.get('jsonl_sha256')!=expected):
        raise ValueError('SFT admission does not bind exact train/development files')
    if expected[0]==expected[1]:raise ValueError('Train/development files overlap')
    for split in ('train','validation'):
        item=m[split];file=(path.parent/item['file']).resolve()
        if sha256_file(file)!=item['sha256']:raise ValueError('Changed SFT JSONL')
        item['_file']=str(file)
    m['_sha256']=sha256_file(path)
    return m


class JsonlConversations:
    """Hash-bound offsets and lengths; full conversations are encoded on demand."""
    def __init__(self,path,tokenizer,expected_sha,context=SEQUENCE):
        if type(context) is not int or context not in SUPPORTED_CONTEXTS:raise ValueError('Unsupported dataset context')
        self.context=context
        self.path=Path(path);self.tokenizer=tokenizer;self.sha=expected_sha
        if sha256_file(path)!=expected_sha:raise ValueError('JSONL identity changed')
        self.offsets=[];self.lengths=[];self.target_counts=[];self.fingerprints=set();self.row_fingerprints=[]
        with self.path.open('rb') as f:
            while True:
                offset=f.tell();line=f.readline(1_048_577)
                if not line:break
                if len(line)>1_048_576:raise ValueError('Overlarge JSONL conversation')
                row=json.loads(line)
                rendered=self._render(row)
                fingerprint=hashlib.sha256(json.dumps({'messages':row['messages'],'policies':row.get('policies')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                if fingerprint in self.fingerprints:raise ValueError('Duplicate SFT conversation')
                self.fingerprints.add(fingerprint);self.row_fingerprints.append(fingerprint)
                self.offsets.append(offset);self.lengths.append(len(rendered['ids']))
                self.target_counts.append(sum(rendered['mask'][1:]))
        if not self.offsets:raise ValueError('Empty SFT dataset')

    def _render(self,row):
        if type(row)!=dict or 'messages' not in row:raise ValueError('Canonical conversation required')
        rendered=encode_conversation(self.tokenizer,row['messages'],policies=row.get('policies'),context=self.context)
        if not any(rendered['mask'][1:]):raise ValueError('No assistant supervision')
        return rendered

    def __len__(self):return len(self.offsets)

    def get(self,index):
        with self.path.open('rb') as f:
            f.seek(self.offsets[index]);row=json.loads(f.readline())
        fingerprint=hashlib.sha256(json.dumps({'messages':row['messages'],'policies':row.get('policies')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if fingerprint!=self.row_fingerprints[index]:raise ValueError('Conversation content changed since preflight')
        rendered=self._render(row)
        if len(rendered['ids'])!=self.lengths[index] or sum(rendered['mask'][1:])!=self.target_counts[index]:
            raise ValueError('Conversation changed since preflight')
        return rendered['ids'],rendered['mask']


class FiniteEpochDataset:
    """Explicit finite replay, with epoch count bound into the restart identity.

    An explicit seed shuffles each epoch; None preserves historical audit order. Development data is never repeated.
    Virtual indices let the existing exact packing cursor span epoch boundaries.
    """
    def __init__(self,dataset,epochs,seed=None,*,diagnostic_only=False):
        if type(epochs) is not int or not 1<=epochs<=(64 if diagnostic_only else 8) or not len(dataset):
            raise ValueError('Finite epochs must be an integer in1..8 with nonempty data')
        self.dataset=dataset;self.epochs=epochs;self.tokenizer=dataset.tokenizer;self.context=getattr(dataset,"context",SEQUENCE)
        self.order=[]
        if seed is not None and type(seed)is not int:raise ValueError('Integer shuffle seed required')
        for epoch in range(epochs):
            order=list(range(len(dataset)))
            if seed is not None:random.Random(seed+epoch).shuffle(order)
            self.order.extend(order)
        self.lengths=[dataset.lengths[i] for i in self.order]
        self.target_counts=[dataset.target_counts[i] for i in self.order]
        identity=f'{dataset.sha}:finite_epochs:{epochs}' if seed is None else json.dumps({'dataset':dataset.sha,'epochs':epochs,'seed':seed,'order':self.order},sort_keys=True)
        self.sha=hashlib.sha256(identity.encode()).hexdigest()

    def __len__(self):return len(self.lengths)

    def get(self,index):
        if type(index) is not int or not 0<=index<len(self):raise IndexError(index)
        return self.dataset.get(self.order[index])


class BestFitConversations:
    """Pinned best-fit algorithm, finite buffer100; no epoch wrap or truncation."""
    def __init__(self,dataset,*,capacity=None,buffer_size=100):
        if capacity is None:capacity=getattr(dataset,"context",SEQUENCE)+1
        if capacity<2 or buffer_size<1 or any(n>capacity for n in dataset.lengths):
            raise ValueError('Conversation does not fit a complete row')
        self.dataset=dataset;self.capacity=capacity;self.buffer_size=buffer_size
        self.next_index=0;self.buffer=[];self.consumed=0;self.rows=0

    def state_dict(self):
        return {'dataset_sha256':self.dataset.sha,'next_index':self.next_index,'buffer':self.buffer.copy(),
                'consumed':self.consumed,'rows':self.rows,'capacity':self.capacity,'buffer_size':self.buffer_size}

    def load_state_dict(self,state):
        if state.get('dataset_sha256')!=self.dataset.sha or state.get('capacity')!=self.capacity or state.get('buffer_size')!=self.buffer_size:
            raise ValueError('SFT cursor identity mismatch')
        cursor,buf,consumed,rows=state.get('next_index'),state.get('buffer'),state.get('consumed'),state.get('rows')
        if type(cursor)is not int or not 0<=cursor<=len(self.dataset) or not isinstance(buf,list) or len(buf)>self.buffer_size:
            raise ValueError('Invalid SFT cursor')
        if any(type(i)is not int or not 0<=i<cursor for i in buf) or len(set(buf))!=len(buf) or type(consumed)is not int or consumed!=cursor-len(buf) or type(rows)is not int or rows<0:
            raise ValueError('Invalid pending conversation buffer')
        self.next_index,self.buffer,self.consumed,self.rows=cursor,buf.copy(),consumed,rows

    def next_indices(self):
        selected=[];remaining=self.capacity
        while remaining:
            while len(self.buffer)<self.buffer_size and self.next_index<len(self.dataset):
                self.buffer.append(self.next_index);self.next_index+=1
            fitting=[i for i in self.buffer if self.dataset.lengths[i]<=remaining]
            if not fitting:break
            chosen=max(fitting,key=lambda i:self.dataset.lengths[i])
            self.buffer.remove(chosen);selected.append(chosen)
            remaining-=self.dataset.lengths[chosen];self.consumed+=1
        if not selected:
            if self.buffer or self.next_index<len(self.dataset):raise ValueError('Unpackable complete conversation')
            raise StopIteration
        self.rows+=1
        return selected

    def next_row(self):
        ids=[];mask=[]
        for index in self.next_indices():
            x,m=self.dataset.get(index);ids.extend(x);mask.extend(m)
        n=self.capacity-len(ids)
        ids.extend([self.dataset.tokenizer.get_bos_token_id()]*n);mask.extend([0]*n)
        return ids[:-1],[token if supervised else NATIVE_IGNORE for token,supervised in zip(ids[1:],mask[1:])]


def count_packed_rows(dataset,buffer_size=100):
    packing=BestFitConversations(dataset,buffer_size=buffer_size)
    while True:
        try:packing.next_indices()
        except StopIteration:return packing.rows


def collect_update(packing, microbatch, rows_per_update=256):
    """CPU rows only; count all valid labels BEFORE any accumulated backward."""
    batches=[];finished=False
    for _ in range(math.ceil(rows_per_update/microbatch)):
        xs=[];ys=[]
        for _ in range(min(microbatch,rows_per_update-len(batches)*microbatch)):
            try:x,y=packing.next_row()
            except StopIteration:finished=True;break
            xs.append(x);ys.append(y)
        if not xs:break
        while len(xs)<microbatch:
            xs.append([packing.dataset.tokenizer.get_bos_token_id()]*(packing.capacity-1))
            ys.append([NATIVE_IGNORE]*(packing.capacity-1))
        batches.append((xs,ys))
        if finished:break
    count=sum(t!=NATIVE_IGNORE for _,ys in batches for row in ys for t in row)
    return batches,count


def backward_weighted(model,batches,total_targets,*,device,stop_check=lambda:False):
    """Global valid-target denominator; works with uneven/zero-target microbatches."""
    import torch
    if total_targets<=0:raise ValueError('Positive supervised target count required')
    actual=sum(t!=NATIVE_IGNORE for _,ys in batches for row in ys for t in row)
    if actual!=total_targets:raise ValueError('Assistant target denominator mismatch')
    summed=0.0
    for xs,ys in batches:
        if stop_check():raise InterruptedError('Lease/signal during SFT accumulation')
        x=torch.tensor(xs,dtype=torch.long,device=device);y=torch.tensor(ys,dtype=torch.long,device=device)
        loss=model(x,y,loss_reduction='sum')
        if not bool(torch.isfinite(loss)):raise FloatingPointError('Nonfinite SFT loss')
        (loss/total_targets).backward();summed+=float(loss.detach())
    return summed/total_targets


def evaluate_fixed(model,dataset,*,rows,microbatch,device):
    import torch
    from cloud_training.nano_checkpoint import capture_rng,restore_rng_state
    if type(rows)is not int or not 1<=rows<=512 or type(microbatch)is not int or microbatch<1:
        raise ValueError('Fixed development evaluation must use1..512rows and positive microbatch')
    rng=capture_rng();modes=[(m,m.training) for m in model.modules()]
    pack=BestFitConversations(dataset);losses=[];targets=0
    try:
        model.eval()
        with torch.inference_mode():
            while pack.rows<rows:
                batches,count=collect_update(pack,microbatch,min(rows-pack.rows,microbatch))
                if not batches:break
                for xs,ys in batches:
                    x=torch.tensor(xs,dtype=torch.long,device=device);y=torch.tensor(ys,dtype=torch.long,device=device)
                    loss=model(x,y,loss_reduction='sum')
                    if not bool(torch.isfinite(loss)):raise FloatingPointError('Nonfinite development loss')
                    losses.append(float(loss));targets+=sum(t!=NATIVE_IGNORE for row in ys for t in row)
        if not targets:raise ValueError('No development assistant targets')
        return {'purpose':'masked_development_loss_not_conversation_acceptance','rows':pack.rows,
                'assistant_targets':targets,'cross_entropy_nats':math.fsum(losses)/targets,'dataset_sha256':dataset.sha,
                'complete':pack.consumed==len(dataset)}
    finally:
        for module,mode in modes:module.training=mode
        restore_rng_state(rng)



def evaluate_families(model,dataset,*,rows,microbatch,device):
    families={}
    for i,line in enumerate(dataset.path.read_text().splitlines()):families.setdefault(json.loads(line).get('family','unclassified'),[]).append(i)
    result={}
    for family,indices in families.items():
        class Subset:
            tokenizer=dataset.tokenizer
            context=dataset.context
            lengths=[dataset.lengths[i] for i in indices]
            sha=hashlib.sha256((dataset.sha+json.dumps(indices)).encode()).hexdigest()
            def __len__(self):return len(indices)
            def get(self,index):return dataset.get(indices[index])
        result[family]=evaluate_fixed(model,Subset(),rows=rows,microbatch=microbatch,device=device)
    return result


def replace_best_pin(journal,new_uri):
    """Only unpin prior best after the new committed best is already journaled."""
    from copy import deepcopy
    value=deepcopy(journal)
    found=[e for e in value['entries'] if e['receipt']['remote_prefix']==new_uri]
    if len(found)!=1 or found[0]['state']!='committed' or 'best' not in found[0]['pins']:
        raise ValueError('New committed best must be published before replacing old pin')
    for entry in value['entries']:
        if entry['receipt']['remote_prefix']!=new_uri:
            entry['pins']=[p for p in entry['pins'] if p!='best']
    return value


def ensure_separate_output(base,output):
    base,output=Path(base).resolve(),Path(output).resolve()
    if output==base or output in base.parents or base in output.parents:
        raise ValueError('SFT output must be separate from immutable base bundle')
    return base,output


def validate_base_metadata(base,expected_manifest_sha,tokenizer_sha):
    from cloud_training.nano_checkpoint import validate_bundle
    base=Path(base).resolve();validate_bundle(base)
    if sha256_file(base/'manifest.json')!=expected_manifest_sha:raise ValueError('Base bundle identity mismatch')
    metadata=json.loads((base/'metadata.json').read_text());identity=metadata['identity']
    if identity.get('phase')!='base' or identity.get('initialization')!='own_random' or identity.get('revision')!=PINNED_REVISION:
        raise ValueError('Only an identified own random-initialized base is permitted')
    if identity.get('tokenizer_sha256')!=tokenizer_sha:raise ValueError('Base/tokenizer mismatch')
    cfg=identity.get('config',{});depth=cfg.get('n_layer')
    if metadata['step']<1:raise ValueError('Base must have retained training updates')
    if depth not in (12,16) or cfg!={'sequence_len':2048,'vocab_size':32768,'n_layer':depth,'n_embd':depth*64,
                                  'n_head':depth//2,'n_kv_head':depth//2,'window_pattern':'SSSL'}:
        raise ValueError('Unsupported own-base configuration')
    return metadata


def validate_parent_chain(parent, expected_sha, tokenizer_sha, *, stage, ancestors=()):
    """Verify every referenced immutable ancestor bundle, ending at own random base.

    Embedded identities alone are insufficient. Targeted warm-start requires all
    ancestor bundles locally; each edge binds an exact manifest hash + identity.
    Hashes establish integrity inside trusted project storage, not authenticity.
    """
    from cloud_training.nano_checkpoint import validate_bundle
    if stage not in ('general','targeted'): raise ValueError('Unknown SFT stage')
    locations={}
    for path in [parent,*ancestors]:
        path=Path(path).resolve();validate_bundle(path)
        key=sha256_file(path/'manifest.json')
        if key in locations: raise ValueError('Duplicate ancestor bundle')
        locations[key]=path
    if expected_sha not in locations or locations[expected_sha]!=Path(parent).resolve(): raise ValueError('Parent manifest mismatch')
    seen=set()
    def visit(key,expected_identity=None):
        if key in seen or len(seen)>=8: raise ValueError('Cyclic/overlong checkpoint lineage')
        if key not in locations: raise ValueError('Every ancestor bundle is required')
        seen.add(key);path=locations[key]
        meta=json.loads((path/'metadata.json').read_text());identity=meta['identity']
        if expected_identity is not None and identity!=expected_identity: raise ValueError('Ancestor identity mismatch')
        if meta['step']<1 or identity.get('revision')!=PINNED_REVISION or identity.get('tokenizer_sha256')!=tokenizer_sha:
            raise ValueError('Ancestor requires retained own-model updates and identical tokenizer/revision')
        if identity.get('phase')=='base':
            validate_base_metadata(path,key,tokenizer_sha)
            return meta,key
        if identity.get('phase')!='sft' or identity.get('format_version')!=VERSION:
            raise ValueError('Only own SFT/base lineage permitted')
        if not re.fullmatch('[0-9a-f]{64}',identity.get('source_manifest_sha256','')):
            raise ValueError('SFT ancestor requires dataset identity')
        parent_sha=identity.get('parent_bundle_manifest_sha256',identity.get('base_bundle_manifest_sha256'))
        parent_identity=identity.get('parent_identity',identity.get('base_identity'))
        if not isinstance(parent_identity,dict): raise ValueError('Missing parent identity')
        root,root_sha=visit(parent_sha,parent_identity)
        validate_context_edge(parent_identity,identity)
        if identity.get('base_bundle_manifest_sha256')!=root_sha or identity.get('base_identity')!=root['identity']:
            raise ValueError('SFT root provenance mismatch')
        return root,root_sha
    root,root_sha=visit(expected_sha)
    parent_meta=json.loads((Path(parent)/'metadata.json').read_text())
    wanted='base' if stage=='general' else 'sft'
    if parent_meta['identity']['phase']!=wanted: raise ValueError(stage+' stage requires '+wanted+' parent')
    if set(locations)!=seen: raise ValueError('Unused ancestor bundles rejected')
    return parent_meta,root,root_sha


def run(args):
    if args.deterministic:
        os.environ["CUBLAS_WORKSPACE_CONFIG"]=":4096:8"
    import torch
    from cloud_training.nano_checkpoint import save_bundle,load_bundle,capture_rng,restore_rng_state,validate_bundle
    from cloud_training.l4_recovery_check import upload_bundle
    from cloud_training.nano_retention import record_upload
    base,out=ensure_separate_output(args.base,args.output)
    tokenizer_dir=Path(args.tokenizer).resolve()
    if sha256_file(tokenizer_dir/'tokenizer.pkl')!=args.tokenizer_sha:raise ValueError('Tokenizer file identity mismatch')
    base_meta,root_meta,root_sha=validate_parent_chain(base,args.base_manifest_sha,args.tokenizer_sha,stage=args.stage,ancestors=args.ancestor)
    for ancestor in args.ancestor: ensure_separate_output(ancestor,out)
    target_context=args.context_tokens
    target_config,context_change=transition_config(base_meta['identity']['config'],target_context,allow_extension=args.allow_context_extension)
    recipe=batch_recipe(args.batch_tokens,args.microbatch,target_context)
    manifest=load_manifest(args.manifest,args.tokenizer_sha,target_context)
    if args.stage=='targeted' and manifest['_sha256']==base_meta['identity'].get('source_manifest_sha256'):
        raise ValueError('Targeted stage requires a distinct explicitly admitted dataset')
    repo=Path(args.repo).resolve()
    if subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()!=PINNED_REVISION or subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip():
        raise ValueError('Pinned clean upstream checkout required')
    sys.path.insert(0,str(repo))
    from nanochat.tokenizer import RustBPETokenizer
    tok=RustBPETokenizer.from_directory(str(tokenizer_dir))
    train=JsonlConversations(manifest['train']['_file'],tok,manifest['train']['sha256'],context=target_context)
    dev=JsonlConversations(manifest['validation']['_file'],tok,manifest['validation']['sha256'],context=target_context)
    if train.fingerprints&dev.fingerprints:raise ValueError('Train/development conversation overlap')
    contract_path=Path(args.quality_contract)
    contract=json.loads(contract_path.read_text());contract_sha=sha256_file(contract_path)
    diagnostic_only=bool(getattr(args,'fit_diagnostic',False))
    if diagnostic_only != (contract.get('objective')=='english_fit_diagnostic'):
        raise ValueError('Diagnostic mode requires explicit flag and matching isolated contract')
    if diagnostic_only and args.stage!='general':raise ValueError('Fit diagnostic must start from immutable base')
    admission=json.loads((Path(args.manifest).resolve().parent/manifest['admission']['receipt']).read_text())
    coverage={'train':dataset_coverage(train),'development':dataset_coverage(dev)}
    checker=contract_errors
    if diagnostic_only:
        from cloud_training.nano_fit_contract import errors as checker, validate_review_file
        validate_review_file(args.manifest,admission,contract)
    errors=checker(contract,manifest=manifest,admission=admission,train=coverage['train'],dev=coverage['development'],epochs=args.epochs,lr_multiplier=args.lr_multiplier,eval_interval=args.eval_every_updates,max_updates=args.max_updates)
    atomic_json(out/'quality-preflight.json',{'status':'blocked' if errors else 'diagnostic_ready_not_quality_accepted','contract_sha256':contract_sha,'coverage':coverage,'reasons':errors})
    if errors:raise ValueError('Quality preflight blocked: '+'; '.join(errors))
    if args.resume:
        saved_guards=json.loads((Path(args.resume)/'metadata.json').read_text())['loop']['quality_guards']
        if any(g['stopped'] for g in saved_guards.values()):raise ValueError('Quality-stopped experiment cannot auto-resume; preserve it and define a new bounded experiment')
    train=FiniteEpochDataset(train,args.epochs,seed=args.seed,diagnostic_only=diagnostic_only)
    total_rows=count_packed_rows(train,buffer_size=args.packing_buffer_size);horizon=math.ceil(total_rows/recipe["rows_per_update"])
    if horizon<2:raise ValueError('Finite SFT corpus too small for this schedule; no automatic replay or zero-LR-only run')
    if args.validate_only:
        print(json.dumps({'status':'admitted_inputs_verified_not_GPU_qualified','packed_rows':total_rows,
                          'planned_updates':horizon,'packing_buffer_size':args.packing_buffer_size,'stage':args.stage,**recipe,'assistant_targets':sum(train.target_counts)},indent=2));return 0
    if not torch.__version__.startswith('2.9.') or not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise ValueError('Pinned torch2.9 CUDA BF16 required')
    import nanochat.flash_attention as attention
    if args.kernel_path:
        from kernels import get_local_kernel
        attention._fa3=get_local_kernel(Path(args.kernel_path),'flash_attn3').flash_attn_interface
        attention.HAS_FA3=True;attention.USE_FA3=attention._resolve_use_fa3()
    if args.deterministic:
        torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.benchmark=False
        torch.backends.cudnn.deterministic=True
    attention_deterministic=bool(args.deterministic_attention or (args.deterministic and attention.USE_FA3))
    if attention_deterministic: deterministic_attention(attention)
    from nanochat.gpt import GPT,GPTConfig
    from nanochat.common import COMPUTE_DTYPE
    if COMPUTE_DTYPE!=torch.bfloat16:raise ValueError('BF16 activations required')
    torch.set_num_threads(args.cpu_threads)
    config=GPTConfig(**target_config)
    with torch.device('meta'):model=GPT(config)
    model.to_empty(device='cuda');model.init_weights();model.train()
    optimizer=model.setup_optimizer(unembedding_lr=.008,embedding_lr=.3,matrix_lr=.02,weight_decay=0.0,scalar_lr=.5)
    fresh_lrs=[g['lr'] for g in optimizer.param_groups]
    load_bundle(base,model=model,optimizer=optimizer,expected_identity=base_meta['identity'])
    reset_sft_lrs(optimizer,fresh_lrs,recipe["lr_batch_scale"],args.lr_multiplier)
    torch.manual_seed(args.seed);torch.cuda.manual_seed_all(args.seed)
    files=('nano_quality_gate.py','nano_fit_contract.py','nano_context.py','nano_sft.py','nano_chat_format.py','nano_checkpoint.py','nano_train.py','nano_retention.py','l4_recovery_check.py')
    identity={'phase':'sft','diagnostic_only':diagnostic_only,'stage':args.stage,'quality_contract_sha256':contract_sha,'data_order_sha256':train.sha,'parent_bundle_manifest_sha256':args.base_manifest_sha,
              'parent_identity':base_meta['identity'],'revision':PINNED_REVISION,'config':vars(config),'tokenizer_sha256':args.tokenizer_sha,
              'format_version':VERSION,'base_bundle_manifest_sha256':root_sha,'base_identity':root_meta['identity'],
              'source_manifest_sha256':manifest['_sha256'],'horizon_updates':horizon,'packed_rows':total_rows,
              'packing_buffer_size':args.packing_buffer_size,'batch_tokens':args.batch_tokens,'lr_batch_scale':recipe['lr_batch_scale'],'lr_multiplier':args.lr_multiplier,'epochs':args.epochs,
              'numerical_mode':numerical_identity(torch,attention_deterministic=attention_deterministic),'microbatch':args.microbatch,'seed':args.seed,'torch':torch.__version__,
              'attention':'fa3' if attention.USE_FA3 else 'sdpa','kernel_sha256':args.kernel_sha,
              'eval_rows':args.eval_rows,'eval_every_updates':args.eval_every_updates,
              'adapter_hashes':{f:sha256_file(Path(__file__).parent/f) for f in files}}
    if context_change is not None:identity['context_transition']=context_change
    packing=BestFitConversations(train,buffer_size=args.packing_buffer_size);step=0;trained_targets=0;best_dev=None;best_step=None
    guard_states=None
    if args.resume:
        restored=load_bundle(args.resume,model=model,optimizer=optimizer,expected_identity=identity)
        step=restored['metadata']['step'];packing.load_state_dict(restored['data_state']['packing'])
        if restored['data_state']['next_batch']!=step:raise ValueError('SFT next-update mismatch')
        guard_states=restored['metadata']['loop']['quality_guards']
        trained_targets=restored['metadata']['loop']['trained_targets'];best_dev=restored['metadata']['loop']['best_dev'];best_step=restored['metadata']['loop']['best_step']
    out.mkdir(parents=True,exist_ok=True)
    journal=CloudJournal(out/'retention-journal.json',campaign_prefix=args.backup_prefix,identity=identity,resume_step=step if args.resume else None)
    compiled=torch.compile(model,dynamic=False)
    deadline=deadline_timestamp(args.deadline_utc);cutoff=deadline-args.checkpoint_reserve_seconds
    if time.time()>=cutoff:raise ValueError('Insufficient lease after preflight')
    interrupted=[]
    def handle(sig,frame):interrupted.append(sig)
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,handle)
    def stopping():return bool(interrupted) or time.time()>=cutoff
    max_step=min(horizon,step+args.max_updates) if args.max_updates else horizon
    guard_names=['aggregate',*sorted(coverage['development']['families'])]
    if guard_states is not None and set(guard_states)!=set(guard_names):raise ValueError('Quality guard resume family mismatch')
    guards={name:ValidationGuard(contract['regression'],None if guard_states is None else guard_states[name]) for name in guard_names}
    status={'status':'running','identity':identity,'step':step,'assistant_targets':trained_targets,'train_loss_scope':'last_optimizer_update_only'}
    def observe_quality(aggregate):
        families=evaluate_families(model,dev,rows=args.eval_rows,microbatch=args.microbatch,device=next(model.parameters()).device)
        status['development_by_family']=families
        observations={'aggregate':aggregate,**families}
        if not all(r['complete'] for r in observations.values()):raise ValueError('Partial development evaluation cannot drive quality decisions')
        # Validate all observations before mutating persisted patience counters.
        staged={name:ValidationGuard(contract['regression'],g.state) for name,g in guards.items()}
        stopped=[name for name,r in observations.items() if staged[name].observe(step,r['cross_entropy_nats'])]
        guards.update(staged)
        status['quality_guards']={name:dict(g.state) for name,g in guards.items()}
        return stopped
    last_save=time.monotonic();last_saved=step if args.resume else None
    def checkpoint(reason,pin=False):
        nonlocal last_save,last_saved
        if last_saved==step:return
        journal.deadline=time.monotonic()+min(args.checkpoint_reserve_seconds,deadline-time.time())
        path=out/f'step-{step:08d}'
        save_bundle(path,model=model,optimizer=optimizer,metadata={'step':step,'identity':identity,'reason':reason,
                   'loop':{'trained_targets':trained_targets,'best_dev':best_dev,'best_step':best_step,'quality_guards':{name:dict(g.state) for name,g in guards.items()}}},
                   data_state={'exact':True,'next_batch':step,'packing':packing.state_dict()})
        journal.set_phase('checkpoint_upload_in_progress',step=step)
        receipt=upload_bundle(path,remote_prefix=args.backup_prefix,timeout=min(args.checkpoint_reserve_seconds,journal.deadline-time.monotonic()))
        pins=(['final'] if step==horizon else [])+(['best'] if step==best_step else [])
        record_upload(journal.path,receipt,campaign_prefix=args.backup_prefix,pins=pins)
        journal.set_phase('ready')
        # Publish the new best before unpinning the old best; at most one best is retained.
        if step==best_step:
            data=replace_best_pin(json.loads(journal.path.read_text()),receipt['remote_prefix'])
            atomic_json(journal.path,data);journal.persist()
        if deadline-time.time()>args.checkpoint_reserve_seconds and journal.deadline-time.monotonic()>60:
            status['retention']=journal.prune(timeout=min(180,max(1,journal.deadline-time.monotonic()-30)))
        status['last_checkpoint']={'step':step,'path':str(path),'upload':receipt}
        atomic_json(out/'progress.json',status)
        journal.deadline=None;last_save=time.monotonic();last_saved=step
        import shutil
        local=sorted(out.glob('step-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'))
        for old in local[:-2]:
            if int(old.name.split('-')[1])!=best_step:
                validate_bundle(old);shutil.rmtree(old)
    if stopping() and not args.resume:
        atomic_json(out/'result.json',dict(status,status='stopped',reason='lease_before_initial_evaluation',quality_accepted=False))
        return 2
    if not stopping():
        status['development_start']=evaluate_fixed(model,dev,rows=args.eval_rows,microbatch=args.microbatch,device=next(model.parameters()).device)
        initial_dev=status['development_start']['cross_entropy_nats']
        # Resume loading must not add an unscheduled validation strike or silently change the best pin.
        if not args.resume:
            observe_quality(status['development_start'])
            best_dev,best_step=initial_dev,step
    if not args.resume:checkpoint('initial_warm_started_sft')
    reason='dataset_complete' if max_step==horizon else 'pilot_update_limit'
    while step<max_step:
        if any(g.state['stopped'] for g in guards.values()):reason='quality_regression_stop';break
        if stopping():reason='lease_or_signal';break
        cursor,rng=packing.state_dict(),capture_rng()
        batches,count=collect_update(packing,args.microbatch,recipe["rows_per_update"])
        if not batches:reason='dataset_complete';break
        torch.cuda.synchronize();tick=time.monotonic()
        try:
            loss=backward_weighted(compiled,batches,count,device=next(model.parameters()).device,stop_check=stopping)
            torch.nn.utils.get_total_norm([p.grad for p in model.parameters() if p.grad is not None],error_if_nonfinite=True)
        except (InterruptedError,FloatingPointError,RuntimeError) as error:
            model.zero_grad(set_to_none=True);packing.load_state_dict(cursor);restore_rng_state(rng)
            reason='lease_or_signal' if isinstance(error,InterruptedError) else 'training_failure'
            status['error']=str(error);break
        lr,momentum=sft_schedule(cursor["consumed"]/len(train),step)
        for group in optimizer.param_groups:
            group['lr']=group['initial_lr']*lr
            if group['kind']=='muon':group['momentum']=momentum;group['weight_decay']=0.0
        optimizer.step();model.zero_grad(set_to_none=True);torch.cuda.synchronize()
        step+=1;trained_targets+=count
        status.update(step=step,assistant_targets=trained_targets,train_loss=loss,
                      consumed_conversations=packing.consumed,packed_rows=packing.rows,update_seconds=time.monotonic()-tick,last_update_assistant_targets=count)
        new_best=False
        if (step%args.eval_every_updates==0 or step==max_step) and not stopping():
            try:
                ev=evaluate_fixed(model,dev,rows=args.eval_rows,microbatch=args.microbatch,device=next(model.parameters()).device)
                status['development']=ev
                stopped_families=observe_quality(ev)
                if stopped_families:status['quality_stop_families']=stopped_families
                if best_dev is None or ev['cross_entropy_nats']<best_dev:
                    best_dev,best_step=ev['cross_entropy_nats'],step;new_best=True
            except (ValueError, RuntimeError, FloatingPointError) as error:
                status['error']=str(error);reason='quality_evaluation_failure'
                checkpoint(reason)
                break
        with (out/'updates.jsonl').open('a') as f:f.write(json.dumps(status,allow_nan=False)+'\n')
        atomic_json(out/'progress.json',status)
        if new_best or any(g.state['stopped'] for g in guards.values()) or time.monotonic()-last_save>=args.checkpoint_seconds:checkpoint('development_best' if new_best else 'quality_regression_stop' if any(g.state['stopped'] for g in guards.values()) else 'periodic')
        if any(g.state['stopped'] for g in guards.values()):reason='quality_regression_stop';break
    checkpoint(reason,pin=step==horizon)
    status.update(status='complete' if step==horizon and reason=='dataset_complete' else 'stopped',reason=reason,
                  quality_accepted=False,evaluation_candidates=evaluation_candidates(json.loads(journal.path.read_text()),best_step,step),
                  step=step,assistant_targets=trained_targets,best_development_loss=best_dev,best_development_step=best_step,
                  acceptance='Not evaluated by this worker; use independent actual conversation/tool tests.')
    atomic_json(out/'result.json',status)
    return 2 if reason in ('training_failure','quality_evaluation_failure','quality_regression_stop') else 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','base','base-manifest-sha','tokenizer','tokenizer-sha','repo','output'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--validate-only',action='store_true')
    p.add_argument('--quality-contract',required=True,help='Hash-bound data intent, coverage, recipe and validation-regression controls')
    p.add_argument('--stage',choices=('general','targeted'),default='general')
    p.add_argument('--ancestor',action='append',default=[],help='Each immutable ancestor bundle required for targeted SFT lineage')
    p.add_argument('--batch-tokens',type=int,default=BATCH,help='Effective position tokens/update;32768 recommended initial targeted experiment')
    p.add_argument('--lr-multiplier',type=float,default=1.0,help='Explicit reduced SFT learning rate, recorded in checkpoint identity; (0,1]')
    p.add_argument('--context-tokens',type=int,choices=SUPPORTED_CONTEXTS,default=SEQUENCE)
    p.add_argument('--allow-context-extension',action='store_true',help='Explicit warm start2Kto4K; never edits the parent checkpoint')
    p.add_argument('--fit-diagnostic',action='store_true',help='Isolated English learnability diagnostic, never a release candidate')
    p.add_argument('--epochs',type=int,default=1,help='Explicit finite passes over admitted training data;1..8, no implicit replay')
    p.add_argument('--deterministic',action='store_true')
    p.add_argument('--deterministic-attention',action='store_true')
    p.add_argument('--resume');p.add_argument('--backup-prefix');p.add_argument('--deadline-utc')
    p.add_argument('--kernel-path');p.add_argument('--kernel-sha')
    p.add_argument('--packing-buffer-size',type=int,default=1,help='Default1 preserves shuffled input order without longest-first starvation; bound into restart identity')
    p.add_argument('--microbatch',type=int,default=4);p.add_argument('--cpu-threads',type=int,default=4)
    p.add_argument('--seed',type=int,default=103);p.add_argument('--max-updates',type=int)
    p.add_argument('--eval-rows',type=int,default=128);p.add_argument('--eval-every-updates',type=int,default=200)
    p.add_argument('--checkpoint-seconds',type=int,default=900);p.add_argument('--checkpoint-reserve-seconds',type=int,default=300)
    a=p.parse_args()
    if not 1<=a.packing_buffer_size<=100:p.error('Packing buffer must be in1..100')
    if not 1<=a.epochs<=(64 if a.fit_diagnostic else 8):p.error('Epoch limit exceeded for selected mode')
    if not math.isfinite(a.lr_multiplier) or not 0<a.lr_multiplier<=1:p.error('LR multiplier must be finite in (0,1]')
    try: batch_recipe(a.batch_tokens,a.microbatch,a.context_tokens)
    except ValueError as error: p.error(str(error))
    if min(a.cpu_threads,a.eval_rows,a.eval_every_updates,a.checkpoint_seconds,a.checkpoint_reserve_seconds)<1:
        p.error('Invalid batch/interval settings')
    if a.eval_rows>512:p.error('Development loss budget capped at512rows')
    if a.max_updates is not None and a.max_updates<1:p.error('Positive max-updates required')
    if bool(a.kernel_path)!=bool(a.kernel_sha):p.error('Kernel path and hash required together')
    if not a.validate_only:
        if not a.deadline_utc or not a.backup_prefix:p.error('Reserved lease deadline and backup-prefix required')
        if not a.checkpoint_reserve_seconds<deadline_timestamp(a.deadline_utc)-time.time()<=21600:p.error('Deadline must allow reserve and be within6hours')
    os.environ.setdefault('HF_HUB_OFFLINE','1');os.environ.setdefault('WANDB_MODE','disabled')
    os.environ.setdefault('PYTORCH_ALLOC_CONF','expandable_segments:True')
    _,out=ensure_separate_output(a.base,a.output)
    for ancestor in a.ancestor: ensure_separate_output(ancestor,out)
    out.mkdir(parents=True,exist_ok=True)
    with (out/'.writer.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return run(a)


if __name__=='__main__':raise SystemExit(main())
