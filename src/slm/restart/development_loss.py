"""Frozen development-only loss inputs and complete per-target loss evidence.

No initialization, training, final-set access, or implicit backend loading.
The caller must bind model/checkpoint ownership and charge supervised runtime.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from slm.common.tokenizer import STRUCTURAL
from .token_store import _read
from .segments import Segment, collate


class _LossTokens:
    def __init__(self, root, *, manifest_sha256, split, vocab_size=8192):
        root=Path(root).absolute();raw=_read(root,'manifest.json')
        if hashlib.sha256(raw).hexdigest()!=manifest_sha256:
            raise ValueError('Changed development manifest')
        manifest=json.loads(raw)
        if (manifest['split']!=split or set(manifest['files'])!={'tokens.u16','index.jsonl'}
                or type(vocab_size) is not int or vocab_size<=len(STRUCTURAL)):
            raise ValueError('Development-only input contract required')
        files={name:_read(root,name) for name in manifest['files']}
        if any(hashlib.sha256(files[k]).hexdigest()!=pin for k,pin in manifest['files'].items()):
            raise ValueError('Changed development input')
        tokens=np.frombuffer(files['tokens.u16'],dtype='<u2')
        rows=[];offset=0;ids=set();families=set();byte_count=0
        for line in files['index.jsonl'].decode().splitlines():
            row=json.loads(line);n=row['targets'];full=row['full_document_targets']
            if (row['split']!=split or not isinstance(row['audit_id'],str) or not row['audit_id']
                    or row['audit_id'] in ids or not isinstance(row['family_id'],str) or not row['family_id']
                    or row['family_id'] in families or type(n) is not int or type(full) is not int
                    or not 0<n<=full or type(row['offset']) is not int or row['offset']!=offset
                    or type(row['partial']) is not bool or row['partial']!=(n<full)
                    or type(row['scored_utf8_bytes']) is not int or row['scored_utf8_bytes']<=0):
                raise ValueError('Invalid development index')
            values=tokens[offset:offset+n]
            content=values if row['partial'] else values[:-1]
            if (len(values)!=n or np.any(values>=vocab_size) or np.any(content<len(STRUCTURAL))
                    or (not row['partial'] and values[-1]!=STRUCTURAL['eos'])):
                raise ValueError('Invalid development targets/EOS')
            if rows and rows[-1]['partial']:
                raise ValueError('Only last selected document may be partial')
            rows.append(row);ids.add(row['audit_id']);families.add(row['family_id'])
            offset+=n;byte_count+=row['scored_utf8_bytes']
        if (not rows or offset!=len(tokens) or offset!=manifest['targets']
                or len(rows)!=manifest['documents'] or len(families)!=manifest['families']
                or byte_count!=manifest['scored_utf8_bytes']):
            raise ValueError('Incomplete development coverage')
        self.manifest=manifest;self.tokens=tokens;self.rows=tuple(rows);self.manifest_sha256=manifest_sha256
        self.targets=offset;self.scored_bytes=byte_count;self.vocab_size=vocab_size

    def segments(self):
        for row in self.rows:
            base=row['offset']
            for first in range(0,row['targets'],512):
                last=min(first+512,row['targets'])
                targets=tuple(map(int,self.tokens[base+first:base+last]))
                predecessor=STRUCTURAL['bos'] if first==0 else int(self.tokens[base+first-1])
                yield Segment(row['audit_id'],first,last,(predecessor,)+targets[:-1],targets)


class DevelopmentTokens(_LossTokens):
    def __init__(self,root,*,manifest_sha256,vocab_size=8192):
        super().__init__(root,manifest_sha256=manifest_sha256,split='development',vocab_size=vocab_size)


def score(store, *, context, logits, heartbeat):
    """logits(x,padding) returns settled CPU NumPy logits from the bound model.

    One document-local segment at a time bounds memory; scoring uses FP64 stable
    logsumexp over FP32 model logits. Every selected target is retained, no drops.
    """
    records=[]
    for part in store.segments():
        heartbeat()
        x,y,mask,_=collate([part]);output=logits(x,mask.astype(bool))
        if (not isinstance(output,np.ndarray) or output.dtype!=np.float32
                or output.shape!=(*x.shape,store.vocab_size) or not np.isfinite(output).all()):
            raise ValueError('Invalid or nonfinite development logits')
        values=output[0].astype(np.float64)
        shifted=values-values.max(axis=-1,keepdims=True)
        nll=np.log(np.exp(shifted).sum(axis=-1))-shifted[np.arange(len(part.targets)),y[0]]
        records.append(dict(document=part.document,first=part.first,last=part.last,
                            target_ids=list(part.targets),nll=nll.tolist()))
        heartbeat()
    result={'context':context,'manifest_sha256':store.manifest_sha256,'records':records}
    result['metrics']=summarize(store,result)
    return result


def summarize(store,payload):
    if payload.get('manifest_sha256')!=store.manifest_sha256:
        raise ValueError('Loss evidence uses different target set')
    records=payload.get('records')
    expected=list(store.segments())
    if not isinstance(records,list) or len(records)!=len(expected):
        raise ValueError('Missing development segment evidence')
    losses=[]
    for part,row in zip(expected,records):
        if (not isinstance(row,dict) or set(row)!={'document','first','last','target_ids','nll'}
                or row['document']!=part.document or type(row['first']) is not int or type(row['last']) is not int
                or row['first']!=part.first or row['last']!=part.last
                or not isinstance(row['target_ids'],list) or any(type(t) is not int for t in row['target_ids'])
                or row['target_ids']!=list(part.targets) or not isinstance(row['nll'],list)
                or len(row['nll'])!=len(part.targets)
                or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in row['nll'])):
            raise ValueError('Invalid per-target development evidence')
        losses.extend(row['nll'])
    total=math.fsum(losses)
    if len(losses)!=store.targets or not math.isfinite(total):
        raise ValueError('Invalid aggregate development loss')
    return dict(targets=store.targets,documents=len(store.rows),nll_sum=total,
                nll=total/store.targets,bits_per_byte=total/math.log(2)/store.scored_bytes)


def verifier(store):
    """Verify counts/identity and recompute metrics; not proof of model execution.

    Scoped evaluator custody and checkpoint binding must establish provenance.
    """
    def verify(raw,context):
        payload=json.loads(raw)
        if payload.get('context')!=context or context.get('event')!='dev_loss_checkpoint':
            raise ValueError('Wrong loss evaluation context')
        metrics=summarize(store,payload)
        if payload.get('metrics')!=metrics:
            raise ValueError('Reported development metrics differ from raw losses')
        return True
    return verify


def quality_verifier(store):
    """Adapter for the durable quality barrier; recompute before returning NLL."""
    check=verifier(store)
    def verify(raw,context):
        check(raw,context)
        return {'nll':summarize(store,json.loads(raw))['nll']}
    return verify
