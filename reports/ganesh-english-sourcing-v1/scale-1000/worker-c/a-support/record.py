import json,hashlib
from pathlib import Path
O=Path(__file__).resolve().parent
rows={r['group']:r for r in map(json.loads,(O/'packet.jsonl').read_text().splitlines())}
def record(notes):
 p=O/'manual-review-progress.json';prior=json.loads(p.read_text()) if p.exists() else [];by={r['group']:r for r in prior}
 for g,(decision,reason) in notes.items():
  r=rows[g];h=hashlib.sha256(json.dumps(r['messages'],ensure_ascii=False,sort_keys=True).encode()).hexdigest();assert h==r['content_sha256'];n=sum(m['role']=='assistant' for m in r['messages']);by[g]={'group':g,'messages_sha256':h,'decision':decision,'assistant_turns_reviewed':n,'reviewed_turn_numbers':list(range(1,n+1)),'rationale':reason}
 p.write_text(json.dumps(list(by.values()),indent=2));print('reviewed',len(by))
