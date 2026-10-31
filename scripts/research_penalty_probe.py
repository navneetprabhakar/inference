import sys,json,time,hashlib
from pathlib import Path
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'scripts'))
import mlx.core as mx
from tokenizers import Tokenizer
from benchmark_mlx import Model
from evaluate_pilot import PROMPTS
out=ROOT/'reports/improvement-research';tok=Tokenizer.from_file(str(ROOT/'data/pilot-v1/tokenizer.json'));allrows=[];start=time.time()
for stage,folder in [('100m','runs/local-campaign-v1/pilot'),('200m','runs/continuation-v1/200m')]:
 p=ROOT/folder;cp=p/json.loads((p/'latest.json').read_text())['directory'];m=Model(768,12,16384);m.load_weights(str(cp/'model.safetensors'));m.set_dtype(mx.bfloat16);mx.eval(m.parameters())
 for penalty in [1.0,1.1,1.2]:
  for category,prompt in PROMPTS:
   ids=tok.encode(prompt).ids;output=[];stop='length'
   for _ in range(96):
    logits=m(mx.array([ids[-512:]]))[0,-1].astype(mx.float32)
    if output and penalty!=1:
     ix=mx.array(sorted(set(output)));selected=logits[ix];logits=logits.at[ix].add(mx.where(selected<0,selected*penalty,selected/penalty)-selected)
    nxt=int(mx.argmax(logits))
    if nxt==1:stop='eos';break
    ids.append(nxt);output.append(nxt)
   grams=[tuple(output[i:i+4]) for i in range(max(0,len(output)-3))]
   allrows.append({'checkpoint':stage,'category':category,'prompt':prompt,'penalty':penalty,'scope':'generated tokens only','decoding':'greedy','output':tok.decode(output,skip_special_tokens=False),'stop':stop,'generated_tokens':len(output),'repeated_4gram_fraction':1-len(set(grams))/len(grams) if grams else 0})
   (out/'penalty-generations.json').write_text(json.dumps(allrows,indent=2)+'\n')
  rows=[r for r in allrows if r['checkpoint']==stage and r['penalty']==penalty];print(stage,penalty,sum(r['repeated_4gram_fraction'] for r in rows)/len(rows),flush=True)
 del m;mx.clear_cache()
(out/'penalty-completed.json').write_text(json.dumps({'complete':True,'outputs':len(allrows),'seconds':time.time()-start,'training':False,'scope':'12 existing diagnostic prompts, greedy only, not blind evaluation; generated-token sign-aware repetition penalty; no weights updated'},indent=2)+'\n')
