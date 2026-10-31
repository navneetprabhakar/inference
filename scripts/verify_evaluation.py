"""Reproduce monitored losses and check whether BF16 changes the conclusions."""
import json
from pathlib import Path
import mlx.core as mx
from tokenizers import Tokenizer
from evaluate_pilot import load,checkpoint,generate,PROMPTS,ROOT,REPORT
from benchmark_mlx import Model
from train_local import evaluate
m=load('100m');actual=evaluate(m,ROOT/'data/pilot-v1');expected=json.loads((ROOT/'runs/local-campaign-v1/pilot/result.json').read_text())['final_validation']
deltas={k:abs(actual[k]-expected[k]) for k in actual};assert max(deltas.values())<1e-4
tok=Tokenizer.from_file(str(ROOT/'data/pilot-v1/tokenizer.json'));ids=tok.encode('Plants need sunlight because').ids
report={'original_validation_reproduced':actual,'absolute_loss_deltas':deltas,'numerics':{},'note':'A tied/near-tied BF16 argmax can change with kernel shape. Check FP32 logits to separate rounding from an inference defect.'}
for dtype in ['bf16','fp32']:
 if dtype=='fp32':m=Model(768,12,16384);m.load_weights(str(checkpoint('pilot')));mx.eval(m.parameters())
 short=m(mx.array([ids]))[0,-1].astype(mx.float32);pad=m(mx.array([ids+[1]*(512-len(ids))]))[0,len(ids)-1].astype(mx.float32);mx.eval(short,pad)
 maximum=float(mx.max(mx.abs(short-pad)));same=int(mx.argmax(short))==int(mx.argmax(pad))
 report['numerics'][dtype]={'maximum_logit_difference':maximum,'same_greedy_next_token':same,'short_next_token':tok.decode([int(mx.argmax(short))]),'padded_next_token':tok.decode([int(mx.argmax(pad))])}
 if dtype=='fp32':assert same and maximum<1e-3
(REPORT/'inference-check.json').write_text(json.dumps(report,indent=2)+'\n')
samples=[]
for i,(category,prompt) in enumerate(PROMPTS):
 samples.append({'category':category,'prompt':prompt,'decoding':'greedy_fp32_master_weights',**generate(m,tok,prompt,'greedy',100+i)})
(REPORT/'fp32-generations.json').write_text(json.dumps(samples,indent=2)+'\n');print(json.dumps(report,indent=2))
for r in samples:print(r['category'],repr(r['output']))
