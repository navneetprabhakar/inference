"""Targeted no-cache replay of actual first-reply prefixes, without training."""
# Creator: Navneet Prabhakar
import json,time
from pathlib import Path
from slm.data.stream_hash import sha
from slm.inference.greedy import GreedyModel,prompt_ids
from slm.common.tokenizer import STRUCTURAL,OFFSET
ROOT=Path('data/balanced-versus-foundation-assessment-v1')
OUT=ROOT/'uncached-prefix-probe'

def main():
 if OUT.exists():raise FileExistsError('Retain original targeted probe')
 if not json.loads((ROOT/'completion.json').read_text())['complete']:raise ValueError('Finish paired actual conversations first')
 p=json.loads((ROOT/'plan.json').read_text());OUT.mkdir();results=[];started=time.monotonic()
 for name,binding in p['models'].items():
  model=GreedyModel(binding['path'],p['tokenizer'],'mlx','default',expected_tokenizer_hash=sha(Path(p['tokenizer'])/'manifest.json'),embedding_implementation='dense-onehot-v1')
  original=[json.loads(x) for x in (ROOT/name/'turns.jsonl').read_text().splitlines()]
  for n in range(1,101,10):
   row=original[(n-1)*3];ids=prompt_ids(model.tokenizer,[dict(role='user',content=row['user'])]);raw=[]
   for i in range(min(16,len(row['response']['token_ids']))):
    logits,_,_=model.impl.forward(model.params,model.config,model.array([ids]),embedding_implementation='dense-onehot-v1')
    if not model.finite(logits[0,-1]):raise FloatingPointError('Nonfinite uncached probe')
    token=model.argmax(logits[0,-1]);raw.append(token);ids.append(token)
    if token<OFFSET:break
   cached=row['response']['token_ids'][:len(raw)]
   results.append(dict(model=name,conversation=n,actual_cached_prefix=cached,actual_uncached_prefix=raw,exact=raw==cached))
  del model
 for path,h in p['inputs'].items():
  if sha(path)!=h:raise ValueError('Original paired input changed')
 report=dict(creator='Navneet Prabhakar',complete=True,checks=len(results),exact_matches=sum(x['exact'] for x in results),results=results,seconds=time.monotonic()-started,paired_plan_sha256=sha(ROOT/'plan.json'),probe_sha256=sha(__file__),model_updates=0,teacher_calls=0,cloud_commands=0,scope='First up to16generated tokens of one first-turn prompt per category/model. Targeted agreement only; not a full sequence/backend/gradient audit.')
 (OUT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');Path('reports/paired-uncached-prefix-probe-v1.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='results'}))
if __name__=='__main__':main()
