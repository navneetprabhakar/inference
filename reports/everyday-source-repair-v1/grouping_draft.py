"""Prospective pure grouping helper. No corpus reads, candidate build or admission.

Caller supplies complete histories and independently reviewed substantive task
keys; this helper does not pretend lexical similarity proves semantic separation.
"""
import hashlib,json,re,unicodedata

def normal(text):
 return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())

def fingerprint(history):
 return hashlib.sha256(json.dumps(history,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def words(text):return re.findall(r"\w+",normal(text))

def shingles(text,n=5):
 w=words(text);return {tuple(w[i:i+n]) for i in range(max(0,len(w)-n+1))}

def propose(records,*,salt,development_percent=20):
 """Return a split PROPOSAL, not custody clearance.

 status: old_train / untouched / historical_holdout / excluded / unknown.
 task_key is a reviewed canonical substantive scenario+requested-operation key,
 not the greeting or merely a broad topic. near duplication merges full-history
 components; same task_key always merges. All historical statuses are supplied
 by a separately verified ledger/custodian, never inferred from missing IDs.
 """
 if not isinstance(salt,str) or not salt or type(development_percent)!=int or not 1<=development_percent<=50:raise ValueError('explicit split policy required')
 if len(records)>5000:raise ValueError('bounded draft <=5000 records')
 rows=sorted(records,key=lambda r:r['doc_id']);ids=[r['doc_id'] for r in rows]
 if len(ids)!=len(set(ids)):raise ValueError('duplicate document identity')
 parents=list(range(len(rows)));features=[];texts=[]
 def find(i):
  while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
  return i
 def union(a,b):
  a,b=find(a),find(b)
  if a!=b:parents[max(a,b)]=min(a,b)
 for r in rows:
  if r['status'] not in {'old_train','untouched','historical_holdout','excluded','unknown'}:raise ValueError('unknown custody status')
  if not r.get('task_key') or not r.get('semantic_review_sha256'):raise ValueError('reviewed substantive grouping required')
  h=r['history'];body=h[int(bool(h and h[0]['role']=='system')):]
  if not body or len(body)%2 or any(m['role']!=('user' if i%2==0 else 'assistant') or not isinstance(m['text'],str) or not m['text'].strip() for i,m in enumerate(body)):raise ValueError('complete alternating history required')
  if sum(len(m['text']) for m in h)>32768:raise ValueError('bounded complete history required')
  if fingerprint(h)!=r['history_sha256']:raise ValueError('history pin mismatch')
  text='\n'.join(m['role']+': '+normal(m['text']) for m in h);texts.append(text);features.append(shingles(text))
 taskindex={};exactindex={};inverted={}
 for i,r in enumerate(rows):
  for key,index in [(r['task_key'],taskindex),(texts[i],exactindex)]:
   if key in index:union(i,index[key])
   else:index[key]=i
  candidates=set()
  for s in features[i]:candidates.update(inverted.get(s,()))
  for j in candidates:
   a,b=features[i],features[j];overlap=len(a&b)
   # Strong lexical overlap is a conservative extra merge, never an eligibility test.
   if overlap>=8 and (overlap/len(a|b)>=.65 or overlap/min(len(a),len(b))>=.8):union(i,j)
  for s in features[i]:inverted.setdefault(s,[]).append(i)
 components={}
 for i,r in enumerate(rows):components.setdefault(find(i),[]).append(r)
 out=[]
 for component in components.values():
  statuses={r['status'] for r in component};keys=sorted({r['task_key'] for r in component});gid=hashlib.sha256(json.dumps(keys,separators=(',',':')).encode()).hexdigest()
  if statuses&{'historical_holdout','excluded','unknown'}:split='quarantine'
  elif 'old_train' in statuses:split='train'
  else:split='exposed-development' if int(hashlib.sha256((salt+'|'+gid).encode()).hexdigest()[:16],16)%100<development_percent else 'train'
  out.append(dict(group=gid,task_keys=keys,doc_ids=sorted(r['doc_id'] for r in component),proposed_split=split,status='pending_new_custody_quality_and_framing',history_sha256={r['doc_id']:r['history_sha256'] for r in component}))
 return sorted(out,key=lambda r:r['group'])
