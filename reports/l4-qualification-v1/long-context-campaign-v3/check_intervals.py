"""Verify reviewed interval merger against integer-set union, not another merger."""
import copy,hashlib,json,random,re,subprocess,sys
from pathlib import Path
r=Path('runs/long-context-campaign-v3/cohort-02');s=next(s for s in map(json.loads,(r/'candidates.jsonl').read_text().splitlines()) if s['id']=='v3-02-intervals')
code=re.findall(r'```python\n(.*?)```',s['messages'][11]['content'],re.S)[0];p=r/'reviewed_intervals.py';p.write_text(code)
subprocess.run([sys.executable,str(p)],check=True);ns={'__name__':'reviewed'};exec(compile(code,str(p),'exec'),ns);fn=ns['merge'];rng=random.Random(918);checks=0
for _ in range(500):
 pairs=[tuple(sorted((rng.randrange(-15,16),rng.randrange(-15,16)))) for j in range(rng.randrange(16))];before=copy.deepcopy(pairs);result=fn(iter(pairs))
 expected={i for a,b in pairs for i in range(a,b)};observed={i for a,b in result for i in range(a,b)}
 assert expected==observed and pairs==before
 assert all(a<b for a,b in result)
 assert all(result[i][1]<result[i+1][0] for i in range(len(result)-1));checks+=1
for bad in [[(2,1)],[(0,10),(2,1)],[(0,0),(-1,-3)]]:
 try:fn(iter(bad))
 except ValueError:pass
 else:raise AssertionError('invalid bounds accepted')
 checks+=1
report={'result':'pass','implementation_sha256':hashlib.sha256(code.encode()).hexdigest(),'displayed_tests':7,'independent_integer_set_checks':500,'invalid_generator_checks':3,'independent_checks':checks}
(r/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
