"""Lossless review view: exact repetitions counted, original order/text reconstructible."""
# Creator: Navneet Prabhakar
import json,sys
from pathlib import Path
model,start,end=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]);p=((Path('data/grounded-core-comparison-v1')/model.removeprefix('core-')) if model.startswith('core-') else Path('data/grounded-conversation-run-v1')/model)/'turns.jsonl'
rows=[json.loads(x) for x in p.open()];seen={};refs=[json.loads(l) for l in Path('data/grounded-conversations-v1/development-references.jsonl').open()]
if model.endswith('grounded-100'):
 for r in rows:
  q=refs[r['conversation']-1]['original_questions'][r['turn']-1];r['review_question']=q['question'];r['reference_answers']=[a['text'] for a in q['answers']]

def pack(s):
 out=[];buf='';i=0
 while i<len(s):
  best=(0,0,0)
  for n in range(4,min(180,(len(s)-i)//3)+1):
   word=s[i:i+n];count=1
   while s.startswith(word,i+n*count):count+=1
   gain=n*(count-1)
   if count>=3 and gain>best[0]:best=(gain,n,count)
  if best[0]:
   if buf:out.append(buf);buf=''
   _,n,count=best;out.append([s[i:i+n],count]);i+=n*count
  else:buf+=s[i];i+=1
 if buf:out.append(buf)
 assert ''.join(x if isinstance(x,str) else x[0]*x[1] for x in out)==s
 return out
for r in rows:
 key=f"{r['conversation']}.{r['turn']}";s=r['response']['text'];old=seen.get(s);seen.setdefault(s,key)
 if start<=r['conversation']<=end:
  print(json.dumps(dict(id=key,user=r.get('review_question',r['user']),reference_answers=r.get('reference_answers'),reply_equals_prior=old) if old else dict(id=key,user=r.get('review_question',r['user']),reference_answers=r.get('reference_answers'),lossless_exact_runs=pack(s)),ensure_ascii=False))
