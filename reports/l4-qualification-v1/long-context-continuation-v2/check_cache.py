"""Independent deterministic state-machine checks; list-based reference model."""
import hashlib, importlib.util, json, random
from pathlib import Path
root=Path('runs/long-context-continuation-cohort-b-revised-v2');p=root/'reviewed_cache.py'
spec=importlib.util.spec_from_file_location('reviewed_cache',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rng=random.Random(7341);steps=0
for capacity in [0,1,2,5]:
 cache=m.HintCache(capacity);reference=[];sentinel=object()
 for _ in range(1000):
  op=rng.choice(['get','put','contains','clear']);key=rng.randrange(7)
  ix=next((i for i,(k,v) in enumerate(reference) if k==key),None)
  if op=='put':
   value=rng.choice([None,0,'hint'])
   cache.put(key,value)
   if capacity:
    if ix is not None:reference.pop(ix)
    reference.append((key,value));reference=reference[-capacity:]
  elif op=='get':
   expected=sentinel if ix is None else reference[ix][1]
   actual=cache.get(key,sentinel)
   assert actual is expected or actual==expected
   if ix is not None:reference.append(reference.pop(ix))
  elif op=='contains':assert (key in cache)==(ix is not None)
  else:cache.clear();reference=[]
  assert cache.keys()==[k for k,v in reference]
  assert len(cache)==len(reference)
  steps+=1
report={'implementation_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'displayed_tests':5,'independent_state_machine_steps':steps,'capacities':[0,1,2,5],'result':'pass','limits':'Nonnegative integer capacities fixed after construction, as stated in dialogue.'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
