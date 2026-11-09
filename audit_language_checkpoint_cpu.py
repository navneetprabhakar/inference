"""Finite CPU-only forward audit of the failed25M checkpoint; no weight writes."""
import hashlib
import json
from pathlib import Path
import resource
import signal
import sys
import time

import torch
from gpt2 import Config,GPT2
from tokenizer import load
from audit_language_math import reference

ROOT=Path(__file__).resolve().parent


def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    start=time.monotonic();torch.set_num_threads(1)
    def check():
        assert time.monotonic()-start<300 and not (ROOT/'runs/STOP').exists()
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert rss*(1 if sys.platform=='darwin' else 1024)<4*1024**3
    def deadline(*_):raise TimeoutError('300-second checkpoint audit ceiling')
    signal.signal(signal.SIGALRM,deadline);signal.alarm(300);check()
    run=ROOT/'runs/own-base-fresh-broad-language-100m-01'
    request=json.loads((run/'milestone-24993792-request.json').read_text());entry=request['checkpoint'];path=run/entry['file']
    assert path.stat().st_size==entry['bytes'] and digest(path)==entry['sha256']
    payload=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
    assert payload['trained_tokens']==24993792 and payload['identity']['initialization']['mode']=='own_pretraining'
    model=GPT2(Config()).eval();model.load_state_dict(payload['model'],strict=True);del payload;check()
    tokenizer=load()
    texts=['The box is red. The color of the box is','The box is blue. The color of the box is']
    encoded=[tokenizer.encode(x).ids for x in texts]
    assert len(encoded[0])==len(encoded[1]) and len(encoded[0])<=64
    x=torch.tensor(encoded)
    with torch.inference_mode():
        actual=model(x);check();expected=reference(model,x);check()
        torch.testing.assert_close(actual,expected,atol=2e-4,rtol=2e-4)
        masked=torch.zeros_like(x,dtype=torch.bool);masked[:,-1]=True
        torch.testing.assert_close(model(x,prediction_mask=masked),actual[:,-1],atol=2e-4,rtol=2e-4);check()
        prefix=model(x[:,:-2]);check()
        torch.testing.assert_close(prefix,actual[:,:-2],atol=2e-4,rtol=2e-4)
        probs=actual[:,-1].softmax(-1)
        context_l1=float((probs[0]-probs[1]).abs().sum())
        top=[]
        for row in probs:
            values,indices=row.topk(5)
            top.append([dict(token=tokenizer.decode([int(i)]),probability=float(v)) for i,v in zip(indices,values)])
    assert digest(path)==entry['sha256'];check()
    result=dict(state='PASS_actual_checkpoint_cpu_forward_equivalence_not_quality',checkpoint=entry,
                trained_targets=24993792,forward_calls=4,max_sequence_length=x.shape[1],
                max_manual_attention_logit_difference=float((actual-expected).abs().max()),
                changed_context_probability_l1=context_l1,probe_texts=texts,top_next_tokens=top,
                seconds=time.monotonic()-start,weights_written=False,
                code_sha256={n:digest(ROOT/n) for n in ['audit_language_checkpoint_cpu.py','audit_language_math.py','gpt2.py','tokenizer.py']},
                limitations=['CPU FP32 only; MPS and BF16 still untested by this audit.','Two simple public probes are a sensitivity check, not a context benchmark.','Teacher-forced forward equivalence does not establish coherent generation.'])
    with (ROOT/'reports/post-25m-correctness-audit-v1/checkpoint-cpu.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    signal.alarm(0);print(json.dumps(result))


if __name__=='__main__':main()
