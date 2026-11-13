import json,re,subprocess,sys,random,copy,hashlib
from pathlib import Path
r=Path('runs/long-context-campaign-v3/followups-01');s=next(x for x in map(json.loads,(r/'candidates.jsonl').read_text().splitlines()) if x['id']=='v3-02-intervals')
a=re.findall(r'```python\n(.*?)```',s['messages'][11]['content'],re.S)[0].split("if __name__")[0]
b=re.findall(r'```python\n(.*?)```',s['messages'][-1]['content'],re.S)[0]
code=a+'\n'+b;p=r/'reviewed_subtract.py';p.write_text(code);subprocess.run([sys.executable,str(p)],check=True)
ns={'__name__':'reviewed'};exec(code,ns);fn=ns['subtract'];rng=random.Random(32)
for _ in range(1000):
 a=[tuple(sorted(rng.choices(range(-20,21),k=2))) for j in range(rng.randrange(15))];b=[tuple(sorted(rng.choices(range(-20,21),k=2))) for j in range(rng.randrange(15))];old=copy.deepcopy((a,b));out=fn(iter(a),iter(b))
 points=lambda xs:{i for l,h in xs for i in range(l,h)}
 assert points(out)==points(a)-points(b) and (a,b)==old
 assert all(l<h for l,h in out) and all(out[i][1]<out[i+1][0] for i in range(len(out)-1))
report={'result':'pass','displayed_tests':3,'independent_set_difference_checks':1000,'implementation_sha256':hashlib.sha256(code.encode()).hexdigest()};(r/'subtract-code-verification.json').write_text(json.dumps(report,indent=2));print(report)
