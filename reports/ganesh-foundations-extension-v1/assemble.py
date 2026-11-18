import json
from pathlib import Path
import verify_extension as gate
from supplemental_arithmetic import entry
P=gate.P;ROOT=gate.ROOT
rows=[]
for domain in ('maths','decisions','orchestration'):
 for row in gate.read(P/domain/'selected.jsonl'):
  row['curriculum_track']=domain;row['partition']='train_candidate';row['data_intent']='foundations_extension_candidate';rows.append(row)
def ref(p):return {'path':str(p.relative_to(ROOT)),'sha256':gate.v.sha(p)}
rootref=ref(P/'root-read-review.json')
aux=P/'supplemental-arithmetic.json';aux.write_text(json.dumps({'entries':[entry(r,gate.v.digest) for r in rows if r['curriculum_track']!='maths']},indent=2)+'\n');auxref=ref(aux)
for r in rows:
 r['root_review_receipt']=rootref
 if r['curriculum_track']!='maths':r['supplemental_arithmetic_receipt']=auxref
stats=gate.verify(rows)
out=ROOT/'runs/ganesh-foundations-extension-v1/reviewed-v1.jsonl';content=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows)
if out.exists():assert out.read_text()==content,'Refusing to replace selected corpus'
else:out.write_text(content)
stats.update(payload=str(out.relative_to(ROOT)),payload_sha256=gate.v.sha(out),track_sessions={d:sum(r['curriculum_track']==d for r in rows) for d in ('maths','decisions','orchestration')})
(P/'verification.json').write_text(json.dumps(stats,indent=2)+'\n');print(json.dumps(stats,indent=2))
