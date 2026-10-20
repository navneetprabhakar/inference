"""Audit additional intact long prose; no threshold or original population rewrite."""
# Creator: Navneet Prabhakar
import json,sqlite3,re
from pathlib import Path
from slm.data.english_eligibility import reasons
from slm.data.schema import digest
from slm.data.stream_hash import sha
out=Path('data/english-long-prose-review-v1')
if out.exists():raise FileExistsError(out)
out.mkdir();d=sqlite3.connect('file:'+str(Path('data/global-exact-families-v2/families.sqlite').resolve())+'?mode=ro',uri=True)
a=[]
for sid,data in d.execute("SELECT sid,data FROM records WHERE ingredient='general' AND candidate=1 AND fixed=0 AND blocked=0"):
 r=json.loads(data);t=r['texts']['content']
 if 12000<len(t)<=40000 and reasons(r)==['bounded_coherent_prose_length']:a.append((sid,r))
a.sort(key=lambda x:x[1]['tokens']);samples=[]
for q in range(4):
 b=a[len(a)*q//4:len(a)*(q+1)//4]
 sid,r=min(b,key=lambda x:digest(['intact-long-prose-v1',x[1]['id']]))
 samples.append(dict(sid=sid,content_sha256=digest(r['texts']['content']),record=r))
(out/'samples.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in samples))
p=dict(creator='Navneet Prabhakar',kind='finite-long-prose-scope-review-v1',rationale='Length beyond12K is a resource/review scope, not by itself a semantic defect. Existing intact documents can be packed causally without truncation; all other exclusion rules unchanged. Full additional stratum receives fresh complete-record audit before admission.',additional_population=len(a),additional_content_tokens=sum(r['tokens'] for _,r in a),samples=4,maximum_nonapproval_fraction=.25,critical_privacy_defects_allowed=0,rule_sha256=sha('src/slm/data/english_eligibility.py'),source_sha256=sha('data/global-exact-families-v2/families.sqlite'),sample_sha256=sha(out/'samples.jsonl'),training_approved=False)
(out/'plan.json').write_text(json.dumps(p,indent=2)+'\n');print(json.dumps(p,indent=2))
