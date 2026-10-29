import json,re
from pathlib import Path
P=Path(__file__).resolve().parent;DATA=P.parent/'phase-a-2026-10-28/private/prepared-v2'
train=json.loads((DATA/'canonical.json').read_text());matrix={r['id']:r for r in json.loads((DATA/'matrix.json').read_text())};allowed={};places={};names=set()
for r in train:
 s=r['scenario'];allowed.setdefault(s['item'],set()).add(s['color']);places.setdefault(s['item'],set()).add(s['place']);names.add(s['name'])
colors=set().union(*allowed.values());locations=set().union(*places.values());out={}
for i in range(4):
 rows=[json.loads(x) for x in (P/'private'/f'arm-{i}/evaluation/1000-matrix.jsonl').read_text().splitlines()];D=[r for r in rows if r['cell']=='D'];groups={}
 def add(key,r,assoc=None):
  v=groups.setdefault(key,{'correct':0,'total':0,'wrong_with_training_association':0,'wrong_with_parseable_attribute':0});v['total']+=1;v['correct']+=int(r['complete'])
  if not r['complete'] and assoc is not None:v['wrong_with_parseable_attribute']+=1;v['wrong_with_training_association']+=int(assoc)
 for r in D:
  s=matrix[r['id']]['scenario'];f=r['family']
  if f=='state':add('state-turn-'+str(r['turn']),r)
  if f=='name':add('name-'+s['name_novelty'],r)
  if f=='clarification':add('clarification-'+s['slot']+'-turn-'+str(r['turn']),r)
  if f in ['distractor','format'] or f=='state' and r['turn']==0:
   words=set(re.findall(r'\w+',r['response'].lower())) & colors
   add('initial-color-binding',r,next(iter(words)) in allowed[s['item']] if len(words)==1 else None)
  if f=='location':
   words=set(re.findall(r'\w+',r['response'].lower())) & locations
   add('location-binding',r,next(iter(words)) in places[s['item']] if len(words)==1 else None)
 out[str(i)]=groups
(P/'binding-diagnosis.json').write_text(json.dumps({'arms':out,'limit':'Posthoc descriptive audit, no rescoring or model inference. Attribute parsing is restricted to exactly one known color/place word. Counts across task variants share scenario worlds; not independent samples.'},indent=2)+'\n')
print(json.dumps(out['1'],indent=2))
