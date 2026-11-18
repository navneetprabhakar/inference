"""Bounded train-only source discovery. Never admits data or alters old sets."""
import collections,hashlib,json,re
from pathlib import Path
import pyarrow.parquet as pq
ROOT=Path.cwd(); OUT=ROOT/'runs/ganesh-english-sourcing-v1'; REPORT=ROOT/'reports/ganesh-english-sourcing-v1'
source=ROOT/'runs/english-source-shortlist-v1/smol.parquet'
def digest(v):return hashlib.sha256(v.encode()).hexdigest()
def filehash(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
assert filehash(source)=='498cd4580014f42c40cfde066573564ed28e3e1548a5566715b615f5ea932856'
keywords=r'\b(friend|feeling|conversation|talk|message|email|polite|rewrite|sentence|paragraph|summar|clarif|remember|prefer|instead|correct|plan|organis|organiz|schedule|hobby|weekend|read|writing|write|explain|understand)\w*'
stats=collections.Counter(); pool=[]
for batch in pq.ParquetFile(source).iter_batches(batch_size=512):
 for row in batch.to_pylist():
  idx=stats['source_rows'];stats['source_rows']+=1;ms=row['messages']
  if row['source']!='smol-magpie-ultra-short':continue
  if not 4<=len(ms)<=12 or any(m['role']!=('user' if i%2==0 else 'assistant') for i,m in enumerate(ms)):continue
  stats['multi_turn_structure']+=1
  if sum(len(m['content']) for m in ms)>2200 or any(len(m['content'])>900 for m in ms):continue
  stats['bounded_length']+=1
  if not re.search(keywords,ms[0]['content'],re.I):continue
  stats['topic_filter']+=1
  ident=digest(json.dumps(ms,ensure_ascii=False,sort_keys=True))
  pool.append({'id':ident,'source':'HuggingFaceTB/smol-smoltalk','revision':'f73fe857d519ff6ac5af2ea67c4d3834da7b8bcc','file':'data/train-00000-of-00004.parquet','row_index':idx,'upstream_split':'train','component':row['source'],'provenance':'upstream_synthetic','group':digest(re.sub(r'\s+',' ',ms[0]['content'].casefold()).strip()),'partition':'train_candidate','messages':ms,'training_admitted':False,'rank':digest('ganesh-sourcing-v1:'+ident)})
seen=set();rows=[]
for x in sorted(pool,key=lambda x:x['rank']):
 if x['group'] in seen:continue
 seen.add(x['group']);rows.append(x)
 if len(rows)==1600:break
out=OUT/'source-candidates.jsonl'
with out.open('w') as f:
 for x in rows:f.write(json.dumps(x,ensure_ascii=False)+'\n')
receipt={'status':'discovery_not_admission','stats':dict(stats),'candidates':len(rows),'path':str(out.relative_to(ROOT)),'sha256':filehash(out),'bytes':out.stat().st_size,'selection':'hash ranked eligible English-task keyword candidates; adaptive discovery, not a population estimate','limitations':['Full semantic review pending','Exact root grouping only; template/near-duplicate grouping pending','No sealed evaluation opened','No cloud upload or training']}
(REPORT/'selection.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
