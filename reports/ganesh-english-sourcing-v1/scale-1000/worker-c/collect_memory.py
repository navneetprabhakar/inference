import json,hashlib
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];R=ROOT/'runs/ganesh-english-sourcing-v1/scale-1000/worker-c';rows={r['group']:r for r in map(json.loads,(R/'baseline.jsonl').read_text().splitlines())};claims=json.loads((O/'claimed-memory-annotations.json').read_text());allr=[];errors=[]
for f in sorted(O.glob('m*.review.json')):
 d=json.loads(f.read_text())
 for r in d['reviews']:
  if r['messages_hash']!=rows[r['group']]['id']:errors.append(r['group']+':hash')
  if r['actual_intervening_complete_turns']!=r['probe_turn']-r['actual_last_supporting_turn']-1:errors.append(r['group']+':gap arithmetic')
  allr.append(dict(r,review_path=str(f.relative_to(ROOT)),review_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),original_claim=claims[r['group']]))
if len({r['group'] for r in allr})!=len(allr):errors.append('duplicategroups')
(O/'memory-manifest.json').write_text(json.dumps(allr,indent=2));print({'reviewed':len(allr),'valid':sum(r['annotation_valid'] for r in allr),'invalid':sum(not r['annotation_valid'] for r in allr),'errors':errors})
