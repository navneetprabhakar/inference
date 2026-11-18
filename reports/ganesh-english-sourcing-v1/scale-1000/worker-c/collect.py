import json,hashlib,collections
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];R=ROOT/'runs/ganesh-english-sourcing-v1/scale-1000/worker-c';rows=[json.loads(x) for x in (R/'baseline.jsonl').read_text().splitlines()];by={r['group']:r for r in rows};manifest=[];errors=[]
for f in sorted(O.glob('b*.review.json')):
 b=int(f.name[1:3]);expected={r['group'] for r in rows[b*10:(b+1)*10]};d=json.loads(f.read_text());actual=[r['group'] for r in d['reviews']]
 if set(actual)!=expected or len(actual)!=len(expected):errors.append(f'{f.name}:group coverage')
 events=[json.loads(l) for l in (R/f'b{b:02d}.events.jsonl').read_text().splitlines() if l.strip()]; types=[e.get('item',{}).get('type') for e in events if e.get('type')=='item.completed']
 if types!=['agent_message'] or not any(e['type']=='turn.completed' for e in events):errors.append(f'{f.name}:event completeness/tools {types}')
 for r in d['reviews']:
  source=by[r['group']];count=sum(m['role']=='assistant' for m in source['messages']);idx=[a['turn'] for a in r['assistant_turns']]
  if idx!=list(range(1,count+1)) or source['id']!=r['messages_hash']:errors.append(f'{r["group"]}:turn/hash coverage')
  if (r['overall']=='reject')!=any(a['verdict']=='fail' for a in r['assistant_turns']):errors.append(f'{r["group"]}:verdict inconsistency')
  manifest.append(dict(r,review_path=str(f.relative_to(ROOT)),review_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),reviewed_turn_count=count,review_model_requested='gpt-6.1-terra',backend_model_independently_observed=False))
summary={'sessions_reviewed':len(manifest),'assistant_turns_reviewed':sum(r['reviewed_turn_count'] for r in manifest),'accept':sum(r['overall']=='accept' for r in manifest),'reject':sum(r['overall']=='reject' for r in manifest),'errors':errors,'missing_groups':[r['group'] for r in rows if r['group'] not in {m['group'] for m in manifest}],'rejected_groups':[r['group'] for r in manifest if r['overall']=='reject']}
(O/'review-manifest.json').write_text(json.dumps(manifest,indent=2));(O/'progress.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k not in ['missing_groups','rejected_groups']}))
