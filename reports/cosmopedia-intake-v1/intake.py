"""Bounded single-shard CPU inventory and frozen quality sample. Never admission."""
import os
os.environ['TOKENIZERS_PARALLELISM']='false'
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[key]='1'
import collections,hashlib,json,pathlib,resource,shutil,signal,sqlite3,sys,time,unicodedata,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2]; HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def hashtext(s):return hashlib.sha256(s.encode()).hexdigest()
def write(p,x):
 with p.open('x') as f:json.dump(x,f,indent=2,ensure_ascii=False);f.write('\n')
def main():
 import pyarrow.parquet as pq
 from tokenizer import load
 p=json.loads((HERE/'plan.json').read_text());out=ROOT/p['output'];started=time.monotonic();failure=None;result={'state':'incomplete_not_admitted','training_admitted':False};db=None
 def alarm(*args):raise TimeoutError('30 minute hard wall limit')
 signal.signal(signal.SIGALRM,alarm);signal.alarm(p['limits']['wall_seconds']);os.nice(10)
 def guard():
  if any(x.exists() for x in (ROOT/'runs/STOP',HERE/'STOP',out/'STOP')):raise RuntimeError('STOP')
  if time.monotonic()-started>=p['limits']['wall_seconds']:raise TimeoutError('wall cap')
  if shutil.disk_usage(ROOT).free<p['limits']['disk_floor_bytes']:raise RuntimeError('disk floor')
  rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
  if rss>p['limits']['rss_bytes']:raise RuntimeError('RSS cap')
  if out.exists() and sum(f.stat().st_size for f in out.iterdir() if f.is_file())>p['limits']['additional_bytes']:raise RuntimeError('output cap')
 guard()
 for rel,h in p['pins'].items():assert digest(ROOT/rel)==h,rel
 assert p['state']=='prepared_for_root_review_not_executed'
 assert not out.exists(),'fresh output only; preserve partial failure for root review'
 assert shutil.disk_usage(ROOT).free>=p['limits']['disk_floor_bytes']+p['limits']['additional_bytes'],'worst-case disk reserve'
 out.mkdir(parents=True)
 try:
  src=p['source'];assert src['bytes']<=p['limits']['compressed_bytes']
  partial=out/'source.parquet.partial';raw=out/'source.parquet';h=hashlib.sha256();n=0
  with urllib.request.urlopen(urllib.request.Request(src['url'],headers={'User-Agent':'bounded-local-corpus-intake/1.0'}),timeout=30) as inp,partial.open('xb') as dest:
   header=inp.headers.get('Content-Length')
   if header is not None:assert int(header)==src['bytes'],'unexpected download length'
   while True:
    guard();chunk=inp.read(1024**2)
    if not chunk:break
    n+=len(chunk)
    if n>src['bytes']:raise RuntimeError('source byte cap')
    dest.write(chunk);h.update(chunk)
  assert n==src['bytes'] and h.hexdigest()==src['sha256'],'exact source identity'
  partial.rename(raw);guard();tok=load();parquet=pq.ParquetFile(raw)
  assert set(parquet.schema_arrow.names)==set(p['expected_columns']),'source schema drift'
  result['source_schema']=str(parquet.schema_arrow);db=sqlite3.connect(out/'inventory.sqlite');db.execute('pragma journal_mode=DELETE');db.execute('pragma temp_store=MEMORY')
  db.execute('create table documents(row_id integer primary key,doc_id text unique,audience text,format text,seed_data text,publisher_tokens integer,gpt2_text_tokens integer,gpt2_with_eot integer,text_sha256 text,normalized_sha256 text,prompt_sha256 text)')
  counts=collections.defaultdict(lambda:{'documents':0,'gpt2_text_tokens':0,'gpt2_with_eot':0});rowid=0;last=started
  for batch in parquet.iter_batches(batch_size=128,use_threads=False):
   guard()
   for r in batch.to_pylist():
    assert all(isinstance(r[k],str) for k in ('text','prompt','audience','format','seed_data'))
    ids=tok.encode(r['text']).ids;assert all(0<=v<50256 for v in ids)
    docid=src['revision']+':'+src['path']+':'+str(rowid)
    norm=' '.join(unicodedata.normalize('NFKC',r['text']).lower().split())
    db.execute('insert into documents values(?,?,?,?,?,?,?,?,?,?,?)',(rowid,docid,r['audience'],r['format'],r['seed_data'],int(r['token_length']),len(ids),len(ids)+1,hashtext(r['text']),hashtext(norm),hashtext(r['prompt'])))
    c=counts[canonical([r['audience'],r['format']])];c['documents']+=1;c['gpt2_text_tokens']+=len(ids);c['gpt2_with_eot']+=len(ids)+1;rowid+=1
   db.commit()
   if time.monotonic()-last>=120:print(json.dumps({'phase':'inventory','rows':rowid,'seconds':time.monotonic()-started}),flush=True);last=time.monotonic()
  assert rowid==parquet.metadata.num_rows
  # Global rank quartiles by actual GPT2 length, then round robin hash-ordered audience/format cells.
  cells=collections.defaultdict(lambda:collections.defaultdict(list))
  for rank,(rid,a,f,ntext) in enumerate(db.execute('select row_id,audience,format,gpt2_text_tokens from documents order by gpt2_text_tokens,row_id')):
   q=min(3,rank*4//rowid);priority=hashtext(canonical(['cosmopedia-quality-v1',p['sample']['seed'],rid]));cells[q][(a,f)].append((priority,rid))
  selected=[];coverage={}
  for q in range(4):
   groups=cells[q];order=sorted(groups,key=lambda c:hashtext(canonical(['cosmopedia-cell-v1',p['sample']['seed'],q,list(c)])))
   for c in groups:groups[c].sort(reverse=True)
   chosen=[]
   while len(chosen)<16:
    progressed=False
    for cell in order:
     if groups[cell]:chosen.append(groups[cell].pop()[1]);progressed=True
     if len(chosen)==16:break
    if not progressed:raise RuntimeError('insufficient sample population')
   selected.extend((q,rid) for rid in chosen);coverage[str(q)]={'population_cells':len(order),'sampled_cells':len({tuple(db.execute('select audience,format from documents where row_id=?',(rid,)).fetchone()) for rid in chosen})}
  assert len(selected)==len({rid for q,rid in selected})==64
  selectedmap={rid:q for q,rid in selected};sample=[];rid=0
  for batch in parquet.iter_batches(batch_size=128,use_threads=False):
   guard()
   for r in batch.to_pylist():
    if rid in selectedmap:
     row=db.execute('select * from documents where row_id=?',(rid,)).fetchone();meta=dict(zip([c[1] for c in db.execute('pragma table_info(documents)')],row));sample.append(dict(meta,quartile=selectedmap[rid],raw=r))
    rid+=1
  sample.sort(key=lambda x:(x['quartile'],selected.index((x['quartile'],x['row_id']))))
  with (out/'quality-sample.jsonl').open('x') as f:
   for r in sample:f.write(canonical(r)+'\n')
  write(out/'sample-manifest.json',{'state':'frozen_for_manual_quality_review_not_admitted','selection':p['sample'],'source_sha256':src['sha256'],'plan_sha256':digest(HERE/'plan.json'),'coverage':coverage,'records':[{k:v for k,v in r.items() if k!='raw'} for r in sample],'sample_sha256':digest(out/'quality-sample.jsonl')})
  duplicate_groups=db.execute('select count(*) from (select normalized_sha256 from documents group by normalized_sha256 having count(*)>1)').fetchone()[0]
  assert db.execute("pragma quick_check").fetchone()==("ok",),"SQLite integrity"
  db.close();db=None;guard()
  fileproofs={}
  for f in out.iterdir():
   guard()
   if f.is_file():fileproofs[f.name]={'bytes':f.stat().st_size,'sha256':src['sha256'] if f.name=='source.parquet' else digest(f)}
  guard();result['files']=fileproofs
  result.update(state='PASS_bounded_source_inventory_not_admitted',rows=rowid,counts_by_audience_format=dict(counts),gpt2_text_tokens=sum(c['gpt2_text_tokens'] for c in counts.values()),gpt2_with_eot=sum(c['gpt2_with_eot'] for c in counts.values()),internal_duplicate_groups=duplicate_groups,eligible_training_tokens=None,quality_review_complete=False,custody_applied=False,historical_dedup_applied=False,split_assigned=False,pending=['manual64documentqualityreview','historical+public+private rootcustody','source-topic/family split','independent candidateverification','trainingadmission'])
 except BaseException as e:
  failure=e;result.update(state='FAIL_incomplete_intake_not_admitted',error=type(e).__name__+': '+str(e))
 finally:
  if db:db.close()
  signal.alarm(0);result.update(seconds=time.monotonic()-started,plan_sha256=digest(HERE/'plan.json'))
  if 'files' not in result:result['partial_files']={f.name:{'bytes':f.stat().st_size,'sha256':None} for f in out.iterdir() if f.is_file()}
  write(out/'receipt.json',result);print(json.dumps({k:result[k] for k in ('state','seconds')}),flush=True)
 if failure:raise failure
if __name__=='__main__':main()
