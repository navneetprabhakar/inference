"""Deterministic available-plaintext overlap audit; never reads sealed release paths."""
import json,re,hashlib,subprocess,collections,unicodedata
from pathlib import Path
P=Path(__file__).parent;S=Path('reports/oasst-correction-memory-v1'); rows=json.loads((S/'shortlist.json').read_text())['rows']
def words(s):return re.findall(r'\w+',unicodedata.normalize('NFKC',s).casefold())
def grams(w):return set(tuple(w[i:i+5]) for i in range(len(w)-4))
def extract(o):
 if isinstance(o,dict):
  for k,v in o.items():
   if k in ('content','text','user','reference_answer','prompt','response','instruction','output') and isinstance(v,str):yield v
   elif isinstance(v,(dict,list)):yield from extract(v)
 elif isinstance(o,list):
  for v in o:yield from extract(v)
qs=[]
for r in rows:
 for i,m in enumerate(r['messages']):
  w=words(m['content']);qs.append({'key':r['review_key'],'message':i,'w':w,'g':grams(w),'norm':' '.join(w),'best':[],'hits':[]})
paths=[Path(n) for n in subprocess.check_output(['rg','--files','--hidden','--no-ignore','-g','*.jsonl','data','reports','runs'],text=True).splitlines()]
exclude=re.compile(r'(sealed|release|holdout|protected|custody|/[^/]*eval[^/]*/|english-source-|\.index\.jsonl$|/(events|resources|loss|updates|retention|windows)\.jsonl$)',re.I)
files=[];skipped=[];segments=0;errors=[]
for p in sorted(paths):
 if exclude.search(str(p)):skipped.append(str(p));continue
 raw=p.read_bytes();count=0
 for line_no,line in enumerate(raw.splitlines(),1):
  try:o=json.loads(line)
  except (ValueError,UnicodeDecodeError):errors.append({'path':str(p),'line':line_no});continue
  for s in extract(o):
   w=words(s)
   if len(w)<8:continue
   count+=1;segments+=1;norm=' '.join(w);g=grams(w)
   for q in qs:
    exact=norm==q['norm'];common=len(g&q['g'])
    if not exact and common==0:continue
    jac=common/len(g|q['g']) if g|q['g'] else 0
    containment=common/min(len(g),len(q['g'])) if g and q['g'] else 0
    hit={'path':str(p),'line':line_no,'exact':exact,'jaccard_5gram':round(jac,5),'containment_5gram':round(containment,5),'words':len(w),'text_sha256':hashlib.sha256(s.encode()).hexdigest()}
    if exact or jac>=.65 or (min(len(w),len(q['w']))>=20 and containment>=.85):q['hits'].append(hit)
    q['best']=sorted(q['best']+[hit],key=lambda x:(x['jaccard_5gram'],x['containment_5gram']),reverse=True)[:3]
 files.append({'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'text_segments':count})
result={'scope':'available local JSONL plaintext only; not full historical/GCS/binary or sealed-release clearance','method':'NFKC/casefold word normalization; exact or word5gram Jaccard>=.65 or containment>=.85 with>=20words; segments>=8words','shortlist_sha256':hashlib.sha256((S/'shortlist.json').read_bytes()).hexdigest(),'files':files,'excluded_paths':skipped,'parse_errors':errors,'segments':segments,'queries':[{k:v for k,v in q.items() if k not in ('w','g','norm')} for q in qs]}
(P/'overlap.json').write_text(json.dumps(result,indent=2)+'\n');print('Files',len(files),'segments',segments,'errors',len(errors),'hits',sum(len(q['hits']) for q in qs))
for q in qs:
 print(q['key'],q['message'],'hits',len(q['hits']),'best',q['best'][:1])
