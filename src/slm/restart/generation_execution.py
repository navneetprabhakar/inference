"""Single-output bounded narrative sampling and deterministic copying probes.

No model loading, retries, output repair, or final-set access. Caller owns the
bound model and supervised time budget. Full-prefix logits avoid cache ambiguity.
"""
import hashlib
import json
import numpy as np
from slm.common.tokenizer import STRUCTURAL
from .generation_metrics import diagnostics,copy_match,copy_gate
from .evaluation_snapshot import MANIFEST_SHA256,_file


def load_development(project,suite):
    if suite not in ('narrative','copy'):raise ValueError('Development generation suite required')
    root=project/'restart/execution-v1/evaluation-frozen-v1'
    raw=_file(root,'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA256:raise ValueError('Changed frozen evaluation manifest')
    m=json.loads(raw);name='development/'+suite+'.jsonl';raw=_file(root,name).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=m['files_sha256'][name]:raise ValueError('Changed frozen generation inputs')
    rows=[json.loads(line) for line in raw.splitlines()]
    ids=[r['id' if suite=='narrative' else 'pair_id'] for r in rows]
    if len(rows)!=100 or len(set(ids))!=100 or any(not i.startswith('development:') for i in ids):
        raise ValueError('Wrong generation denominator/split')
    return rows


def sample(scores,rng):
    """Fixed temperature .7, nucleus .9; stable ID tie breaking, include crossing token."""
    values=np.asarray(scores,dtype=np.float64)
    if values.ndim!=1 or not len(values) or not np.isfinite(values).all():raise ValueError('Invalid generation scores')
    values=(values-values.max())/.7
    probabilities=np.exp(values);probabilities/=probabilities.sum()
    order=np.argsort(-probabilities,kind='stable')
    n=int(np.searchsorted(np.cumsum(probabilities[order]),.9,side='left'))+1
    keep=order[:n];weights=probabilities[keep];weights/=weights.sum()
    return int(rng.choice(keep,p=weights))


def generate(prefix,tokenizer,*,logits,heartbeat,seed=None,copying=False):
    if (not isinstance(prefix,list) or not prefix or len(prefix)>=512
            or any(type(t) is not int or not len(STRUCTURAL)<=t<tokenizer.vocab_size for t in prefix)):
        raise ValueError('Invalid generation prefix')
    if not copying and (type(seed) is not int or seed<0):raise ValueError('Fixed narrative seed required')
    rng=np.random.default_rng(seed) if not copying else None
    inputs=[STRUCTURAL['bos'],*prefix];generated=[];text='';reason='context_limit'
    while len(inputs)<=512:
        heartbeat();x=np.asarray([inputs],dtype=np.int32)
        out=logits(x,np.ones(x.shape,dtype=bool))
        if (not isinstance(out,np.ndarray) or out.dtype!=np.float32
                or out.shape!=(*x.shape,tokenizer.vocab_size) or not np.isfinite(out).all()):
            raise ValueError('Invalid generation logits')
        token=int(np.argmax(out[0,-1])) if copying else sample(out[0,-1],rng)
        generated.append(token);heartbeat()
        if token==STRUCTURAL['eos']:reason='eos';break
        if token<len(STRUCTURAL):reason='invalid_structural_token';break
        text=tokenizer.decode(generated)
        if copying and len(generated)==64:reason='copy_64_tokens';break
        if not copying and len(text.split())>=120:reason='word_limit';break
        inputs.append(token)
    return {'generated_token_ids':generated,'text':text,'stop_reason':reason,'ended_with_eos':reason=='eos',
            'decode_policy':'greedy-lowest-id-tie' if copying else 'temperature-.7-top-p-.9-PCG64',
            'seed':seed if not copying else None}


def narrative(items,tokenizer,*,logits,heartbeat):
    outputs=[];seen=set()
    for item in items:
        if item['id'] in seen:raise ValueError('Duplicate narrative item')
        seen.add(item['id'])
        if (tokenizer.encode(item['prefix'])!=item['prefix_token_ids']
                or item['temperature']!=.7 or item['top_p']!=.9
                or item['minimum_words']!=80 or item['maximum_words']!=120
                or item['early_eos_failure_below_words']!=40):raise ValueError('Changed narrative recipe')
        result=generate(item['prefix_token_ids'],tokenizer,logits=logits,heartbeat=heartbeat,seed=item['generation_seed'])
        result['id']=item['id'];result['diagnostics']=diagnostics(result['text'],ended_with_eos=result['ended_with_eos'])
        result['execution_failure']=result['stop_reason']=='invalid_structural_token'
        outputs.append(result)
    return outputs


def copying(pairs,tokenizer,*,logits,heartbeat):
    if len(pairs)!=100 or len({p['pair_id'] for p in pairs})!=100:raise ValueError('Exactly 100 copy pairs required')
    outputs=[];matches={'training':[],'heldout':[]}
    for pair in pairs:
        result={'pair_id':pair['pair_id']}
        for role in ('training','heldout'):
            item=pair[role];prefix=item['prefix_token_ids'];reference=item['expected_next_64_token_ids']
            if len(prefix)!=64 or tokenizer.encode(item['prefix'])!=prefix or len(reference)!=64:
                raise ValueError('Changed copy prefix/reference')
            raw=generate(prefix,tokenizer,logits=logits,heartbeat=heartbeat,copying=True)
            if raw['stop_reason']=='invalid_structural_token':raise ValueError('Invalid structural copy output')
            raw['match']=copy_match(raw['generated_token_ids'],reference)
            matches[role].append(raw['match']);result[role]=raw
        outputs.append(result)
    return {'outputs':outputs,'metrics':copy_gate(matches['training'],matches['heldout']),
            'policy':'One greedy continuation per prefix, stop at EOS or 64 tokens; no resampling.'}
