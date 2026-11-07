"""Independent exhaustive CPU source/index/sample proof; never semantic admission.
Does not import intake.py; only runs after its terminal complete receipt exists.
"""
import os
os.environ['TOKENIZERS_PARALLELISM']='false'
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[name]='1'
import collections,hashlib,json,pathlib,resource,shutil,signal,sqlite3,sys,time,unicodedata
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
def sha(path):
 with path.open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def string_sha(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()
def require(condition,message):
 if not condition:raise ValueError(message)
def main():
 import pyarrow.parquet as pq
 from tokenizer import load
 start=time.monotonic();plan=json.loads((HERE/'plan.json').read_text());out=ROOT/plan['output'];receipt_path=out/'receipt.json'
 require(receipt_path.exists(),'wait for complete intake; do not open live SQLite')
 initial_receipt_sha=sha(receipt_path);receipt=json.loads(receipt_path.read_text());require(receipt['state']=='PASS_bounded_source_inventory_not_admitted','intake not complete')
 require(not (HERE/'independent-inventory-verification.json').exists(),'preserve existing verifier receipt')
 def timeout(*args):raise TimeoutError('independent CPU verifier wall cap')
 signal.signal(signal.SIGALRM,timeout);signal.alarm(1800);os.nice(10)
 def guard():
  require(not any(p.exists() for p in (ROOT/'runs/STOP',HERE/'STOP',out/'STOP')),'STOP')
  require(time.monotonic()-start<1800,'wall cap');require(shutil.disk_usage(ROOT).free>=20*1024**3,'disk floor')
  require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<=1536*1024**2,'RSS cap')
 proofs={};db=None;failure=None;result={'state':'FAIL_independent_inventory_not_admitted','training_admitted':False,'semantic_quality_verified':False}
 try:
  guard();require(receipt['plan_sha256']==sha(HERE/'plan.json'),'receipt plan binding')
  for path,expected in plan['pins'].items():guard();require(sha(ROOT/path)==expected,'pinned dependency '+path)
  for name,entry in receipt['files'].items():
   guard();path=out/name;require(path.parent==out and path.stat().st_size==entry['bytes'],'receipt size/path');require(sha(path)==entry['sha256'],'receipt content '+name);proofs[name]=entry['sha256']
  src=plan['source'];raw=out/'source.parquet';require(raw.stat().st_size==src['bytes'] and proofs['source.parquet']==src['sha256'],'official source hash')
  tree=json.loads((HERE/'source-tree.json').read_text());files=[f for f in tree if f['type']=='file'];smallest=min(files,key=lambda f:(f['size'],f['path']))
  require(len(files)==104 and smallest['path']==src['path'] and smallest['lfs']['oid']==src['sha256'] and smallest['size']==src['bytes'],'metadata-only smallest whole-shard selection')
  require(src['bytes']<=plan['limits']['compressed_bytes'],'compressed limit');require(sum(p.stat().st_size for p in out.iterdir() if p.is_file())<=plan['limits']['additional_bytes'],'total output limit')
  db=sqlite3.connect('file:'+str(out/'inventory.sqlite')+'?mode=ro',uri=True);require(db.execute('pragma quick_check').fetchone()==('ok',),'SQLite integrity')
  cols=[r[1] for r in db.execute('pragma table_info(documents)')];require(cols==['row_id','doc_id','audience','format','seed_data','publisher_tokens','gpt2_text_tokens','gpt2_with_eot','text_sha256','normalized_sha256','prompt_sha256'],'inventory schema')
  stored=iter(db.execute('select * from documents order by row_id'));parquet=pq.ParquetFile(raw);require(set(parquet.schema_arrow.names)==set(plan['expected_columns']),'parquet fields')
  sample=[json.loads(line) for line in (out/'quality-sample.jsonl').read_text().splitlines()];require(len(sample)==64 and len({r['row_id'] for r in sample})==64,'64 unique samples');byid={r['row_id']:r for r in sample}
  samplemanifest=json.loads((out/'sample-manifest.json').read_text());require(samplemanifest['source_sha256']==src['sha256'] and samplemanifest['plan_sha256']==sha(HERE/'plan.json') and samplemanifest['sample_sha256']==proofs['quality-sample.jsonl'],'sample proof bindings');require(samplemanifest['selection']==plan['sample'],'frozen sample algorithm')
  tok=load();counts=collections.defaultdict(lambda:{'documents':0,'gpt2_text_tokens':0,'gpt2_with_eot':0});lengths=[];n=0;last=start;matched=0
  for batch in parquet.iter_batches(batch_size=64,use_threads=False):
   guard()
   for record in batch.to_pylist():
    ids=tok.encode(record['text']).ids;require(all(0<=x<50256 for x in ids),'ordinary GPT2 text IDs')
    key=src['revision']+':'+src['path']+':'+str(n);expected=(n,key,record['audience'],record['format'],record['seed_data'],int(record['token_length']),len(ids),len(ids)+1,string_sha(record['text']),string_sha(' '.join(unicodedata.normalize('NFKC',record['text']).lower().split())),string_sha(record['prompt']))
    require(next(stored,None)==expected,'inventory/source/token mismatch row '+str(n));lengths.append((len(ids),n,record['audience'],record['format']))
    c=counts[canonical([record['audience'],record['format']])];c['documents']+=1;c['gpt2_text_tokens']+=len(ids);c['gpt2_with_eot']+=len(ids)+1
    if n in byid:
     item=byid[n];require(item['raw']==record,'sample original full record');require({k:item[k] for k in cols}==dict(zip(cols,expected)),'sample index identity');matched+=1
    n+=1
   if time.monotonic()-last>=120:print(json.dumps({'phase':'independent_inventory','verified_rows':n,'seconds':time.monotonic()-start}),flush=True);last=time.monotonic()
  require(next(stored,None) is None and n==parquet.metadata.num_rows==receipt['rows'],'complete inventory and source');require(matched==64,'every sample matched');require(dict(counts)==receipt['counts_by_audience_format'],'aggregate cells')
  for field in ('gpt2_text_tokens','gpt2_with_eot'):require(sum(c[field] for c in counts.values())==receipt[field],'aggregate '+field)
  # Separate selection implementation: sort complete rank list; queues with forward cursors.
  groups=collections.defaultdict(lambda:collections.defaultdict(list));seed=plan['sample']['seed']
  for rank,(_,rid,aud,fmt) in enumerate(sorted(lengths)):
   quartile=rank*4//n;groups[quartile][(aud,fmt)].append(rid)
  chosen=[];coverage={}
  for quartile in range(4):
   queues=groups[quartile];cell_order=sorted(queues,key=lambda cell:string_sha(canonical(['cosmopedia-cell-v1',seed,quartile,list(cell)])))
   for cell in queues:queues[cell].sort(key=lambda rid:string_sha(canonical(['cosmopedia-quality-v1',seed,rid])))
   positions={cell:0 for cell in queues};selected=[];used=set()
   while len(selected)<16:
    progress=False
    for cell in cell_order:
     pos=positions[cell]
     if pos<len(queues[cell]):selected.append(queues[cell][pos]);positions[cell]+=1;used.add(cell);progress=True
     if len(selected)==16:break
    require(progress,'enough population')
   chosen.extend((quartile,rid) for rid in selected);coverage[str(quartile)]={'population_cells':len(queues),'sampled_cells':len(used)}
  require(chosen==[(r['quartile'],r['row_id']) for r in sample],'independent deterministic stratified selection/order');require(coverage==samplemanifest['coverage'],'sample coverage');require(samplemanifest['records']==[{k:v for k,v in r.items() if k!='raw'} for r in sample],'manifest all sampled metadata')
  duplicate_groups=db.execute('select count(*) from (select normalized_sha256 from documents group by normalized_sha256 having count(*)>1)').fetchone()[0];require(duplicate_groups==receipt['internal_duplicate_groups'],'duplicate group count')
  require(receipt['eligible_training_tokens'] is None and all(receipt[k] is False for k in ('training_admitted','quality_review_complete','custody_applied','historical_dedup_applied','split_assigned')),'no premature eligibility claims')
  db.close();db=None;guard();require(sha(out/'inventory.sqlite')==proofs['inventory.sqlite'] and sha(receipt_path)==initial_receipt_sha,'inventory unchanged')
  result.update(state='PASS_independent_inventory_and_sample_not_admitted',verified_rows=n,verified_sample_rows=64,counts_by_audience_format=dict(counts),gpt2_text_tokens=receipt['gpt2_text_tokens'],gpt2_with_eot=receipt['gpt2_with_eot'],coverage=coverage,failures=[])
 except BaseException as exc:
  failure=exc;result['failures']=[type(exc).__name__+': '+str(exc)]
 finally:
  if db:db.close()
  signal.alarm(0);result.update(seconds=time.monotonic()-start,plan_sha256=sha(HERE/'plan.json'),intake_receipt_sha256=sha(receipt_path),verifier_sha256=sha(pathlib.Path(__file__)),source_and_artifact_hashes=proofs,scope='Independent exhaustive byte/source-row/GPT2-count/sample-selection verification; no semantic quality, split, historical dedup or root custody claim.')
  with (HERE/'independent-inventory-verification.json').open('x') as handle:json.dump(result,handle,indent=2);handle.write('\n')
  print(json.dumps({k:result[k] for k in ('state','seconds')}),flush=True)
 if failure:raise failure
if __name__=='__main__':main()
