"""Teacher-forced complete-alternative scoring, without model initialization.

Prompt and continuation are encoded separately, matching frozen continuation
lengths. All continuation tokens plus EOS are scored; prompt tokens are not.
The scoped caller owns checkpoint provenance, runtime charging and custody.
"""
import hashlib
import json
import numpy as np
from slm.common.tokenizer import STRUCTURAL
from . import choice_scoring
from .evaluation_snapshot import MANIFEST_SHA256, _file


def load_development(project, suite):
    if suite not in ('grammar','grounded'):
        raise ValueError('Only development choice suites allowed')
    root=project/'restart/execution-v1/evaluation-frozen-v1'
    raw=_file(root,'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=MANIFEST_SHA256:
        raise ValueError('Changed frozen evaluation manifest')
    manifest=json.loads(raw);relative='development/'+suite+'.jsonl'
    raw=_file(root,relative).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest['files_sha256'][relative]:
        raise ValueError('Changed development choices')
    items=[json.loads(line) for line in raw.splitlines()]
    if len(items)!=(200 if suite=='grammar' else 100) or any(i['split']!='development' for i in items):
        raise ValueError('Wrong development denominator/split')
    return items


def prepare(items, tokenizer, *, variant='original', context_limit=512):
    if variant not in ('original','empty','shuffled'):
        raise ValueError('Unknown passage variant')
    if type(context_limit) is not int or not 1<=context_limit<=512:
        raise ValueError('Invalid context limit')
    # Validate labels and equal-length contract with the frozen scoring code.
    choice_scoring.score(items,[])
    prepared=[]
    for item in items:
        prompt=item['prompt'] if variant=='original' else item['controls'][variant+'_prompt']
        prefix=tokenizer.encode(prompt)
        alternatives=[]
        if len(item['alternatives'])!=len(item['continuation_token_lengths']):
            raise ValueError('Changed alternative inventory')
        for text,length in zip(item['alternatives'],item['continuation_token_lengths']):
            continuation=tokenizer.encode(text)
            if len(continuation)!=length:
                raise ValueError('Frozen continuation lengths differ from tokenizer')
            if any(type(t) is not int or not len(STRUCTURAL)<=t<tokenizer.vocab_size for t in prefix+continuation):
                raise ValueError('Invalid encoded content ID')
            tokens=[STRUCTURAL['bos'],*prefix,*continuation,STRUCTURAL['eos']]
            if len(tokens)-1>context_limit:
                raise ValueError('Choice exceeds context; no truncation allowed')
            alternatives.append({'inputs':tokens[:-1],'targets':tokens[1:],'score_start':len(prefix)})
        prepared.append({'id':item['id'],'alternatives':alternatives})
    return prepared


def execute(items,tokenizer,*,logits,heartbeat,variant='original'):
    prepared=prepare(items,tokenizer,variant=variant)
    outputs=[]
    for item in prepared:
        probabilities=[]
        for alternative in item['alternatives']:
            heartbeat()
            x=np.asarray([alternative['inputs']],dtype=np.int32)
            values=logits(x,np.ones(x.shape,dtype=bool))
            if (not isinstance(values,np.ndarray) or values.dtype!=np.float32
                    or values.shape!=(*x.shape,tokenizer.vocab_size) or not np.isfinite(values).all()):
                raise ValueError('Invalid choice logits')
            start=alternative['score_start']
            values=values[0,start:].astype(np.float64)
            shifted=values-values.max(axis=-1,keepdims=True)
            targets=np.asarray(alternative['targets'][start:],dtype=np.int32)
            lp=shifted[np.arange(len(targets)),targets]-np.log(np.exp(shifted).sum(axis=-1))
            probabilities.append(lp.tolist());heartbeat()
        outputs.append({'id':item['id'],'token_log_probabilities':probabilities})
    return {'variant':variant,'outputs':outputs,'metrics':choice_scoring.score(items,outputs)}


def verify(items,result,*,variant):
    if result.get('variant')!=variant:
        raise ValueError('Changed passage variant')
    outputs=result.get('outputs')
    if not isinstance(outputs,list) or len(outputs)!=len(items):
        raise ValueError('Incomplete choice output inventory')
    scored=choice_scoring.score(items,outputs)
    if any(row['failure'] not in (None,'tie') for row in scored['items']):
        raise ValueError('Incomplete/invalid token scores')
    if result.get('metrics')!=scored:
        raise ValueError('Choice summary differs from token scores')
    return scored
