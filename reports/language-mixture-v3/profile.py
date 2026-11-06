import collections,hashlib,json,pathlib,re,sqlite3,time,shutil
import pyarrow.parquet as pq
R=pathlib.Path(__file__).resolve().parents[2]; D=R/'data/language-mixture-v3';V=R/'data/language-mixture-v1';W=R/'data/language-mixture-v2';start=time.monotonic()
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def check():
 assert time.monotonic()-start<900 and not(R/'runs/STOP').exists() and not(D/'STOP').exists()
 assert shutil.disk_usage(R).free>20*1024**3
check();m=json.loads((V/'partial-candidate-manifest.json').read_text());assert sha(V/'candidates.sqlite')==m['candidate_database_sha256'];raw=m['source_files'][-1];assert sha(raw['path'])==raw['sha256']
receipt=json.loads((W/'quality-review.json').read_text());assert sha(W/'proposed-exclusions.json')==receipt['exclusions_sha256']
old=json.loads((W/'quality-sample-receipt.json').read_text());assert sha(V/'custody.json')==old['custody_sha256']
excluded=set(json.loads((V/'custody.json').read_text())['excluded_doc_ids'])|{x['doc_id'] for x in json.loads((W/'proposed-exclusions.json').read_text())}
previous={x['doc_id'] for x in old['sample_ids']}
con=sqlite3.connect(f'file:{V}/candidates.sqlite?mode=ro',uri=True)
meta={row[1]:row for row in con.execute("select doc_id,source_row,split,tokens from documents where source='web'") if row[0] not in excluded}
scores={}; ix=0
for b in pq.ParquetFile(raw['path']).iter_batches(batch_size=8192,columns=['id','score','int_score'],use_threads=False):
 check()
 for row in b.to_pylist():
  if ix in meta:
   assert row['id']==meta[ix][0];scores[row['id']]=(row['score'],row['int_score'])
  ix+=1
assert len(scores)==len(meta)
phrases=['subscribe to our newsletter','subscribe to the newsletter','leave a comment','post a comment','share this article','related articles','related posts','you may also like','follow us on facebook','all rights reserved']
def rules(text):
 lines=[re.sub(r'\s+',' ',s.strip().casefold()) for s in text.splitlines() if s.strip()];c=collections.Counter(x for x in lines if len(x)>=20);total=sum(map(len,lines));out=[]
 if text.count('?')>=8 and sum(x.endswith('?') for x in lines)>=3:out.append('faq')
 if sum(n-1 for n in c.values())>=3 and sum((n-1)*len(x) for x,n in c.items())>=.15*total:out.append('repeated_lines')
 tail=[]
 for x in reversed(lines):
  if len(x)>120:break
  tail.append(x)
 if len(tail)>=8 and sum(map(len,tail))>=.2*total:out.append('short_line_tail')
 if sum(p in text.casefold() for p in phrases)>=5:out.append('boilerplate')
 return out
counts=collections.defaultdict(collections.Counter);dist=collections.Counter();eligible=[];flags=collections.Counter()
for n,(did,split,tokens,text,url) in enumerate(con.execute("select doc_id,split,tokens,text,canonical_url from documents where source='web'")):
 if n%1000==0:check()
 if did in excluded:continue
 score,ints=scores[did];dist[str(ints)]+=1;rs=rules(text)
 for q in (4,4.5,5):
  if score<q:continue
  c=counts[str(q)+':'+split];c['before_docs']+=1;c['before_tokens']+=tokens
  if rs:
   for flag in rs:flags[str(q)+':'+flag]+=1
  else:
   c['after_docs']+=1;c['after_tokens']+=tokens
   if split=='validation':c['short_32_127' if 32<=tokens-1<=127 else ('long_ge128' if tokens-1>=128 else 'under32')]+=1
 if score>=4 and not rs and split=='train' and did not in previous:eligible.append((tokens,did,score))
eligible.sort();chosen=[]
for q in range(4):
 group=[(t,d,s) for i,(t,d,s) in enumerate(eligible) if min(3,i*4//len(eligible))==q]
 group.sort(key=lambda x:hashlib.sha256(('forge-language-v3-20261106|'+x[1]).encode()).hexdigest())
 for t,d,s in group[:4]:
  text,url=con.execute('select text,canonical_url from documents where doc_id=?',(d,)).fetchone();chosen.append(dict(doc_id=d,tokens=t,score=s,quartile=q+1,text=text,url=url))
(D/'sample.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in chosen))
result=dict(state='sample_frozen_before_review_not_admitted',counts=dict(counts),int_score_document_distribution=dict(dist),filter_counts_overlapping=dict(flags),sample_sha256=sha(D/'sample.jsonl'),sample_ids=[{k:x[k] for k in ('doc_id','tokens','score','quartile')} for x in chosen],raw_sha256=raw['sha256'],v2_receipt_sha256=sha(W/'quality-review.json'),protocol_sha256=sha(pathlib.Path(__file__).with_name('QUALITY_PROTOCOL.md')),code_sha256=sha(pathlib.Path(__file__)),seconds=time.monotonic()-start)
(D/'profile.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
