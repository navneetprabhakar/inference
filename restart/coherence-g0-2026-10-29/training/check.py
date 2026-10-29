"""Read-only integrity/coverage checks; NOT semantic review."""
import json, hashlib
from collections import Counter
from pathlib import Path
from build import sp,serial,FAMILIES,STRUCTURES,review_record
R=Path(__file__).resolve().parent
rows=json.loads((R/'private/candidates.json').read_text());byid={r['id']:r for r in rows}
assert len(rows)==len(byid)==6400
assert Counter(r['family'] for r in rows)=={f:800 for f in FAMILIES}
assert Counter((r['family'],r['abstract_structure']) for r in rows)=={(f,s):200 for f in FAMILIES for s in STRUCTURES}
for r in rows:
 assert serial(r['messages'])==(r['ids'],r['mask'])
 assert r['validation']['worst_generated_history_plus_last_reply']<=256
 assert all(n<=32 for n in r['validation']['native_reply_lengths_including_eos'])
 assert 2<=len(r['messages'])//2<=4
 assert [m['role'] for m in r['messages']]==['user','assistant']*(len(r['messages'])//2)
repeat=json.loads((R/'private/repeat-subset.json').read_text())
for seed in [291102,291103]:
 sched=json.loads((R/f'private/schedule-{seed}.json').read_text());assert len(sched)==1000
 for i,step in enumerate(sched):
  assert step['update']==i+1
  assert [byid[x]['family'] for x in step['conversation_ids']]==FAMILIES
 for j,f in enumerate(FAMILIES):
  deck=[s['conversation_ids'][j] for s in sched]
  assert len(set(deck[:800]))==800
  assert set(deck[800:])==set(repeat[f]) and len(set(deck[800:]))==200
allreview=sum([json.loads(p.read_text()) for p in sorted((R/'private').glob('review-all-*.json'))],[])
assert allreview==[review_record(r) for r in rows]
second=sum([json.loads(p.read_text()) for p in sorted((R/'private').glob('review-second-*.json'))],[])
assert len(second)==1280 and len({r['id'] for r in second})==1280
assert Counter((byid[r['id']]['family'],byid[r['id']]['abstract_structure']) for r in second)=={(f,s):40 for f in FAMILIES for s in STRUCTURES}
manifest=json.loads((R/'manifest.json').read_text())
for p,h in manifest['files'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
print('PASS: candidate serialization, caps, quotas, review coverage, schedules, hashes. No semantic approval implied.')
