"""Prospective explanatory candidate projection; no admission, packing or training."""
import os
os.environ['TOKENIZERS_PARALLELISM']='false'
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[name]='1'
import collections,hashlib,json,pathlib,resource,shutil,signal,sqlite3,sys,time
from rules import structural_reasons,normalize,h,seed_relation,seed_shingles
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def write(p,x):
 with p.open('x') as f:json.dump(x,f,indent=2,ensure_ascii=False);f.write('\n')
def main():
 import pyarrow.parquet as pq
 from tokenizer import load
 p=json.loads((HERE/'policy.json').read_text());out=ROOT/p['output'];start=time.monotonic();db=None;failure=None;result={'state':'FAIL_incomplete_projection_not_admitted','training_admitted':False}
 def alarm(*args):raise TimeoutError('candidate CPU wall cap')
 signal.signal(signal.SIGALRM,alarm);signal.alarm(1800);os.nice(10)
 def guard():
  if any(x.exists() for x in (ROOT/'runs/STOP',HERE/'STOP',out/'STOP')):raise RuntimeError('STOP')
  if time.monotonic()-start>1800:raise TimeoutError('wall')
  if shutil.disk_usage(ROOT).free<20*1024**3:raise RuntimeError('disk floor')
  if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)>1536*1024**2:raise RuntimeError('RSS cap')
  if out.exists() and sum(x.stat().st_size for x in out.iterdir() if x.is_file())>3*1024**3:raise RuntimeError('output ceiling')
 guard()
 for f,expected in p['pins'].items():guard();assert sha(ROOT/f)==expected,f
 proof=json.loads((ROOT/p['independent_intake_proof']).read_text());assert proof['state']=='PASS_independent_inventory_and_sample_not_admitted'
 assert not out.exists();assert shutil.disk_usage(ROOT).free>=23*1024**3
 out.mkdir(parents=True)
 try:
  tok=load();src=p['source'];raw=ROOT/src['local_path'];assert sha(raw)==src['sha256'];parquet=pq.ParquetFile(raw)
  db=sqlite3.connect(out/'candidates.sqlite');db.execute('pragma journal_mode=DELETE');db.execute('pragma temp_store=MEMORY')
  db.executescript('''create table documents(row_id integer primary key,doc_id text unique,audience text,format text,seed_data text,text text,prompt text,text_sha256 text,normalized_sha256 text unique,prompt_sha256 text,gpt2_text_tokens integer,gpt2_with_eot integer,seed_sha256 text,seed_kind text,relation_group integer,source_record_sha256 text);
create index document_seed_lookup on documents(seed_sha256);
create table decisions(row_id integer primary key,reasons text);
create table seeds(seed_sha256 text primary key,first_row integer,kind text,shingles blob);
create table anchors(anchor blob,seed_sha256 text);
create index anchor_lookup on anchors(anchor);
create table near_edges(left_row integer,right_row integer,intersection integer,union_count integer);
''')
  parents={}
  def find(x):
   while parents[x]!=x:parents[x]=parents[parents[x]];x=parents[x]
   return x
  def union(a,b):
   a,b=find(a),find(b);parents[max(a,b)]=min(a,b)
  holds=set(p['known_hold_row_ids']);oldsample=set(p['prior_review_row_ids']);counts=collections.Counter();cellcounts=collections.Counter();rid=0;last=start
  for batch in parquet.iter_batches(batch_size=64,use_threads=False):
   guard()
   for r in batch.to_pylist():
    reasons=[];lane=(r['audience'],r['format']) in [tuple(x) for x in p['lanes']]
    if not lane:reasons.append('outside_prospective_lane')
    if rid in holds:reasons.append('known_manual_hold')
    if lane:reasons.extend(structural_reasons(r['text']))
    normsha=h(normalize(r['text'])) if lane else None
    if lane and not reasons and db.execute('select 1 from documents where normalized_sha256=?',(normsha,)).fetchone():reasons.append('normalized_text_duplicate')
    if reasons:
     db.execute('insert into decisions values(?,?)',(rid,canonical(reasons)))
     for reason in reasons:counts[reason]+=1
    else:
     tokens=len(tok.encode(r['text']).ids);seed,kind=seed_relation(r['prompt']);seedsha=h(seed);prior=db.execute('select first_row from seeds where seed_sha256=?',(seedsha,)).fetchone()
     if prior:group=prior[0]
     else:
      group=rid;parents[group]=group;shingles=seed_shingles(seed,kind);anchors=shingles[:4];matches=set()
      for anchor in anchors:matches.update(x[0] for x in db.execute('select seed_sha256 from anchors where anchor=?',(anchor,)))
      if len(matches)>500:raise RuntimeError('seed relation candidate hub exceeds frozen500; no silent edge omission')
      newset=set(shingles)
      for other in sorted(matches):
       otherrow,blob=db.execute('select first_row,shingles from seeds where seed_sha256=?',(other,)).fetchone();oldset={blob[i:i+16] for i in range(0,len(blob),16)};inter=len(newset&oldset);total=len(newset|oldset)
       if total and 5*inter>=4*total:union(group,otherrow);db.execute('insert into near_edges values(?,?,?,?)',(otherrow,group,inter,total))
      db.execute('insert into seeds values(?,?,?,?)',(seedsha,group,kind,b''.join(shingles)))
      db.executemany('insert into anchors values(?,?)',[(anchor,seedsha) for anchor in anchors])
     docid=src['revision']+':'+src['path']+':'+str(rid)
     db.execute('insert into documents values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,docid,r['audience'],r['format'],r['seed_data'],r['text'],r['prompt'],h(r['text']),normsha,h(r['prompt']),tokens,tokens+1,seedsha,kind,group,h(canonical(r))))
     counts['retained_documents']+=1;counts['retained_gpt2_with_eot']+=tokens+1;cellcounts[canonical([r['audience'],r['format']])]+=1
    rid+=1
   db.commit()
   if time.monotonic()-last>=120:print(json.dumps({'phase':'candidate_projection','rows':rid,'retained':counts['retained_documents'],'seconds':time.monotonic()-start}),flush=True);last=time.monotonic()
  assert rid==parquet.metadata.num_rows
  for group in parents:
   root=find(group)
   if root!=group:db.execute('update documents set relation_group=? where seed_sha256 in(select seed_sha256 from seeds where first_row=?)',(root,group))
  db.commit();assert db.execute('pragma quick_check').fetchone()==('ok',)
  # Review sampling does not filter the candidates. Exclude all prior64 read rows from the fresh draw only.
  pool=[tuple(r) for r in db.execute('select row_id,gpt2_text_tokens,format from documents order by gpt2_text_tokens,row_id') if r[0] not in oldsample]
  assert len(pool)>=64;queues=collections.defaultdict(lambda:collections.defaultdict(list));seed=p['fresh_sample']['seed']
  for rank,(rowid,length,fmt) in enumerate(pool):queues[rank*4//len(pool)][fmt].append(rowid)
  selected=[];coverage={}
  for q in range(4):
   groups=queues[q];order=sorted(groups,key=lambda f:h(canonical(['cosmopedia-candidate-cells-v1',seed,q,f])))
   for fmt in groups:groups[fmt].sort(key=lambda r:h(canonical(['cosmopedia-candidate-row-v1',seed,r])),reverse=True)
   chosen=[]
   while len(chosen)<16:
    progressed=False
    for fmt in order:
     if groups[fmt]:chosen.append(groups[fmt].pop());progressed=True
     if len(chosen)==16:break
    assert progressed
   selected.extend((q,x) for x in chosen);coverage[str(q)]={'formats':order,'selected_rows':chosen}
  samples=[]
  for q,rowid in selected:
   db.row_factory=sqlite3.Row;r=dict(db.execute('select * from documents where row_id=?',(rowid,)).fetchone());r['quartile']=q;samples.append(r)
  db.row_factory=None;groups_count=db.execute('select count(distinct relation_group) from documents').fetchone()[0];edges_count=db.execute('select count(*) from near_edges').fetchone()[0];db.close();db=None
  with (out/'quality-sample.jsonl').open('x') as f:
   for r in samples:f.write(canonical(r)+'\n')
  write(out/'sample-manifest.json',{'state':'frozen_fresh64_before_manual_read_not_admitted','policy_sha256':sha(HERE/'policy.json'),'sample_sha256':sha(out/'quality-sample.jsonl'),'selection':p['fresh_sample'],'coverage':coverage,'records':[{k:v for k,v in r.items() if k not in ('text','prompt')} for r in samples]})
  guard();files={}
  for f in out.iterdir():guard();files[f.name]={'bytes':f.stat().st_size,'sha256':sha(f)}
  result.update(state='candidate_projection_with_frozen_sample_not_admitted',source_rows=rid,counts=dict(counts),lane_documents=dict(cellcounts),relation_groups=groups_count,verified_near_edges=edges_count,files=files,split_assigned=False,custody_applied=False,historical_dedup_applied=False,semantic_quality_verified=False)
 except BaseException as e:failure=e;result['error']=type(e).__name__+': '+str(e)
 finally:
  if db:db.close()
  signal.alarm(0);result.update(seconds=time.monotonic()-start,policy_sha256=sha(HERE/'policy.json'),builder_sha256=sha(pathlib.Path(__file__)))
  write(out/'receipt.json',result);print(json.dumps({'state':result['state'],'seconds':result['seconds']}),flush=True)
 if failure:raise failure
if __name__=='__main__':main()
