"""Freeze source/length-stratified complete-record review; no admission."""
# Creator: Navneet Prabhakar
import json,sqlite3
from pathlib import Path
from slm.data.schema import digest
from slm.data.stream_hash import sha
out=Path('data/english-corpus-admission-review-v1')
if out.exists():raise FileExistsError(out)
out.mkdir();db=sqlite3.connect('file:'+str(Path('data/global-exact-families-v2/families.sqlite').resolve())+'?mode=ro',uri=True)
selected=[];counts={}
for source in ['general','explanatory','narrative']:
 rows=[]
 for sid,data in db.execute('SELECT sid,data FROM records WHERE ingredient=? AND candidate=1 AND fixed=0 AND blocked=0',(source,)):
  r=json.loads(data);rows.append((sid,r))
 counts[source]=len(rows)
 ranked=sorted(rows,key=lambda x:(x[1]['tokens'] or 0,x[0]));n=len(ranked)
 for stratum in range(4):
  bucket=ranked[n*stratum//4:n*(stratum+1)//4]
  for sid,r in sorted(bucket,key=lambda x:digest(['english-corpus-admission-review-v1',x[1]['id']]))[:3]:
   selected.append(dict(sid=sid,source=source,length_quartile=stratum,content_sha256=digest(r['texts']['content']),record=r))
with (out/'samples.jsonl').open('x') as f:
 for r in selected:f.write(json.dumps(r,ensure_ascii=False)+'\n')
plan=dict(creator='Navneet Prabhakar',kind='finite-language-research-admission-review-v1',authority='delegated_expert',human_attestation=False,source_db_sha256=sha('data/global-exact-families-v2/families.sqlite'),script_sha256=sha(__file__),sampling='Three deterministic hash-selected records per source/token-length quartile, before near grouping. Complete texts; source candidates only. Final eligible membership and any newly joined nonapprovals are checked after grouping.',population=counts,samples=len(selected),sample_file_sha256=sha(out/'samples.jsonl'),policy=dict(scope='Private research on laptop and one authorized GCP VM; no corpus/weights publication',critical_privacy_or_unsafe_defects_allowed=0,source_defect_fraction_reject_above=.25,all_observed_nonapprovals_withhold_family=True,unread_risk='Heuristic language/privacy/content screening is uncalibrated. Small clustered source sample cannot establish corpus error bounds. Factual errors, outdated statements, bias, attribution/underlying source uncertainty remain. Explicit finite research acceptance only; no production certification.'),training_approved=False)
(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps(plan,indent=2))
