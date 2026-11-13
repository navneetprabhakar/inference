"""Run teacher pytest examples and independent stable-rank checks."""
import copy,hashlib,json,os,random,re,subprocess,sys
from pathlib import Path
r=Path('runs/long-context-campaign-v3/cohort-06');s=next(s for s in map(json.loads,(r/'candidates.jsonl').read_text().splitlines()) if s['id']=='v3-06-topk')
blocks=re.findall(r'```python\n(.*?)```',s['messages'][11]['content'],re.S);fncode=blocks[0]
for index,tests in [(9,re.findall(r'```python\n(.*?)```',s['messages'][9]['content'],re.S)[0]),(11,blocks[1])]:
 (r/f'test_topk_{index}.py').write_text(fncode+'\n'+tests)
subprocess.run([sys.executable,'-m','pytest','-q','--confcutdir',str(r.resolve()),str(r/'test_topk_9.py'),str(r/'test_topk_11.py')],check=True,env={**os.environ,'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'})
ns={};exec(fncode,ns);fn=ns['top_k'];rng=random.Random(612);checks=0
class OnePass:
 def __init__(self,rows):self.rows=rows;self.calls=0
 def __iter__(self):
  self.calls+=1
  assert self.calls==1
  return iter(self.rows)
for _ in range(300):
 rows=[{'id':rng.choice(['A','B',{'unorderable':True}]),'score':rng.randrange(-5,6)} for _ in range(rng.randrange(30))];before=copy.deepcopy(rows);k=rng.randrange(len(rows)+4)
 ranks={sum(o['score']>row['score'] for o in rows)+sum(o['score']==row['score'] for o in rows[:i]):row for i,row in enumerate(rows)}
 expected=[ranks[i] for i in range(min(k,len(rows)))];source=OnePass(rows)
 assert fn(source,k)==expected and rows==before and source.calls==1;checks+=1
source=OnePass([])
try:fn(source,-1)
except ValueError:pass
else:raise AssertionError('negative k accepted')
assert source.calls==0;checks+=1
report={'result':'pass','implementation_sha256':hashlib.sha256(fncode.encode()).hexdigest(),'displayed_pytest_cases':7,'independent_stable_rank_checks':300,'independent_checks':checks,'python':sys.version.split()[0],'limits':'Finite ordered numeric scores and integer k; no NaN/complex ordering contract was specified.'}
(r/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
