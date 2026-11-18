import json,time
from pathlib import Path
BASE=Path(__file__).resolve().parent
workers={}
for name in ('root','worker-a','worker-b','worker-c'):
 p=BASE/name/'progress.json'
 if p.exists():
  d=json.loads(p.read_text());workers[name]={k:v for k,v in d.items() if isinstance(v,(str,int,float,bool))}
new={}
for name in ('root','worker-a','worker-b'):
 p=BASE/name/'accepted.jsonl'
 if p.exists():
  rows=[json.loads(l) for l in p.read_text().splitlines()];new[name]={'sessions':len(rows),'assistant_turns':sum(sum(m['role']=='assistant' for m in r['messages']) for r in rows)}
r={'state':'in_progress_not_admitted','target':1000,'legacy_sessions_under_fresh_review':310,'new_staged_pass_files':new,'workers':workers,'cloud_operations_performed':False,'time':time.time()}
(BASE/'live-progress.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
