"""Execute reviewed outline versions and independent order/validation probes."""
import copy,hashlib,json,random,re,subprocess,sys
from pathlib import Path
root=Path('runs/long-context-campaign-v3/cohort-01');s=next(s for s in map(json.loads,(root/'candidates.jsonl').read_text().splitlines()) if s['id']=='v3-01-outline')
checks=0;tested=[]
for index in [5,11,17]:
 code=re.findall(r'```python\n(.*?)```',s['messages'][index]['content'],re.S)[0]
 path=root/f'outline-message-{index}.py';path.write_text(code);ns={'__name__':'reviewed'};exec(compile(code,str(path),'exec'),ns);fn=ns['outline']
 rng=random.Random(71)
 for _ in range(100):
  n=rng.randrange(1,35);records=[{'id':i,'parent_id':rng.choice([None]+list(range(i))),'title':str(i)} for i in range(n)];rng.shuffle(records);before=copy.deepcopy(records)
  out=fn(records);assert [r['id'] for r in out]==[r['id'] for r in records if r['parent_id'] is None]
  pending=out[:];seen=set()
  while pending:
   node=pending.pop();assert node['id'] not in seen;seen.add(node['id'])
   assert [c['id'] for c in node['children']]==[r['id'] for r in records if r['parent_id']==node['id']]
   pending.extend(node['children'])
  assert len(seen)==n and records==before;checks+=1
 bad=[[{'id':1,'parent_id':None}]*2,[{'id':1,'parent_id':2}]]
 if index!=5:bad += [[{'id':None,'parent_id':None}],[{'id':1,'parent_id':1}],[{'id':0,'parent_id':None},{'id':1,'parent_id':2},{'id':2,'parent_id':1}]]
 for records in bad:
  try:fn(records)
  except ValueError:pass
  else:raise AssertionError(('accepted invalid',index,records))
  checks+=1
 if index!=5:
  records=[{'id':i,'parent_id':None if i==0 else i-1} for i in reversed(range(7000))];out=fn(iter(records));node=out[0]
  for i in range(7000):
   assert node['id']==i
   if i<6999:node=node['children'][0]
  checks+=1
 tested.append({'message_index':index,'sha256':hashlib.sha256(code.encode()).hexdigest()})
subprocess.run([sys.executable,str(root/'outline-message-17.py')],check=True)
report={'result':'pass','independent_checks':checks,'random_forests':300,'deep_chain_length':7000,'deep_chain_versions':2,'displayed_tests':3,'implementations':tested,'limits':'Hashable IDs; expected hash-table complexity, shallow copies as documented. Intermediate message5 intentionally lacks later cycle/None validation.'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
