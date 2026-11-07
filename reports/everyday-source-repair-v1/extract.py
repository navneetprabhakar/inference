"""Bounded full-history review extraction; no private reads, filtering or admission."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['TOKENIZERS_PARALLELISM']='false'
import argparse,collections,hashlib,json,pathlib,resource,shutil,signal,sqlite3,sys,time,traceback
R=pathlib.Path(__file__).resolve().parents[2];H=pathlib.Path(__file__).parent

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def hashjson(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def read(p):return json.loads(p.read_text())
def excluded_ids(root):
 ex=set(read(root/'data/sft-readiness-v3/custody.json')['excluded_doc_ids'])|set(read(root/'data/sft-readiness-v3/quality-review.json')['proposed_excluded_doc_ids'])
 for v in (4,5,6):
  for row in read(root/f'data/sft-readiness-v{v}/excluded.json'):
   # Reconsider only the named blanket reason, never an actual substantive reason.
   if set(row['rules'])-{'deferred_small_cohort'}:ex.add(row['doc_id'])
  if v in (4,5):ex.update(read(root/f'data/sft-readiness-v{v}/review.json')['proposed_additional_excluded_doc_ids'])
 return ex

def main(path,expected):
 if sys.flags.optimize:raise RuntimeError('assertions must be enabled; do not use python -O')
 import pyarrow.parquet as pq
 path=pathlib.Path(path).resolve();assert sha(path)==expected;p=read(path);assert p['state']=='prospective_full_history_review_intake_not_admitted';D=R/p['output'];assert not D.exists();start=time.monotonic();os.nice(10)
 def deadline(*a):raise TimeoutError('review intake deadline')
 signal.signal(signal.SIGALRM,deadline);signal.alarm(p['limits']['seconds'])
 def check():
  assert not any(x.exists() for x in (R/'runs/STOP',H/'STOP',D/'STOP')),'STOP';assert time.monotonic()-start<p['limits']['seconds'],'wall';assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<p['limits']['rss_bytes'],'RSS';assert shutil.disk_usage(R).free>=p['limits']['free_disk_bytes'],'disk'
  if D.exists():assert sum(x.stat().st_size for x in D.iterdir() if x.is_file())<p['limits']['output_bytes'],'output'
 for n,h in p['pins'].items():check();assert sha(R/n)==h,n
 for item in p['files']:
  f=pathlib.Path(item['path']);check();assert f.stat().st_size==item['bytes'] and sha(f)==item['sha256'];assert sha(f.parent/'receipt.json')==item['receipt_sha256']
 proof=read(R/'data/sft-readiness-v3/candidate-verification.json');manifest=read(R/'data/sft-readiness-v3/partial-candidate-manifest.json');integrity=read(R/'data/sft-readiness-v3/source-integrity.json')
 assert proof['state']=='PASS_pre_host_policy_not_admitted' and not proof.get('failures',[])
 assert proof['database_sha256']==manifest['database']['sha256']==p['pins']['data/sft-readiness-v3/candidates.sqlite']
 assert manifest['policy_sha256']==integrity['policy_sha256']==p['pins']['data/sft-readiness-v3/policy.json']
 assert manifest['source_integrity_sha256']==p['pins']['data/sft-readiness-v3/source-integrity.json']
 source=sqlite3.connect(f'file:{R}/data/sft-readiness-v3/candidates.sqlite?mode=ro',uri=True);source.row_factory=sqlite3.Row;old={r['doc_id']:dict(r) for r in source.execute('select * from documents where source=?',(p['source'],))};source.close();assert len(old)==811 and {r['split'] for r in old.values()}=={'train'}
 known=excluded_ids(R);bad=set(old)&known;assert len(bad)==41 and len(set(old)-known)==770
 D.mkdir();db=sqlite3.connect(D/'review.sqlite');db.execute('pragma synchronous=FULL');db.execute('create table histories(doc_id text primary key,source_sha256 text,source_path text,row_index integer,raw_row_sha256 text,messages_json text,history_sha256 text,status text,old_selected_history_sha256 text,old_family text,old_whole integer)');counts=collections.Counter();seen=set();failure=None
 try:
  with (D/'review-queue.jsonl').open('x') as review:
   for item in p['files']:
    rownum=-1
    for batch in pq.ParquetFile(item['path']).iter_batches(batch_size=16,use_threads=False):
     check()
     for row in batch.to_pylist():
      rownum+=1
      if row['source']!=p['source']:continue
      did=item['sha256']+':'+str(rownum);messages=row['messages'];assert isinstance(messages,list) and messages and all(isinstance(m,dict) and isinstance(m.get('content'),str) and isinstance(m.get('role'),str) for m in messages),'raw schema'
      status='excluded' if did in known else 'old_train' if did in old else 'unknown';history_sha=hashjson(messages);prior=old.get(did);seen.add(did);counts[status]+=1
      db.execute('insert into histories values(?,?,?,?,?,?,?,?,?,?,?)',(did,item['sha256'],item['path'],rownum,hashjson(row),canon(messages),history_sha,status,hashjson(json.loads(prior['selected_history_json'])) if prior else None,prior['family'] if prior else None,prior['whole'] if prior else None))
      review.write(canon(dict(doc_id=did,history_sha256=history_sha,status=status,messages=messages,task_key=None,substantive_user_turn_indices=[],requested_operation=None,fact_schema=None,state_events=[],quality_decision=None,reason=None,semantic_review_sha256=None))+'\n')
     db.commit()
  assert set(old)<=seen and sum(counts.values())==1130 and counts['old_train']==770 and counts['excluded']==41 and counts['unknown']==319,dict(counts)
  assert db.execute('pragma quick_check').fetchone()[0]=='ok';db.close()
  for n,h in p['pins'].items():check();assert sha(R/n)==h,n
  for item in p['files']:check();assert sha(pathlib.Path(item['path']))==item['sha256']
 except BaseException as e:failure=dict(type=type(e).__name__,reason=str(e),traceback=traceback.format_exc());db.close()
 hashes={}
 if failure is None:
  try:
   check();hashes=dict(database_sha256=sha(D/'review.sqlite'),queue_sha256=sha(D/'review-queue.jsonl'));check()
  except BaseException as e:failure=dict(type=type(e).__name__,reason=str(e),traceback=traceback.format_exc())
 if failure is not None:
  # No further guarded work or expensive hashing after failure. Preserve original
  # exception in a bounded failure-only receipt; it can never look complete.
  signal.alarm(0)
 receipt=dict(state='partial_review_intake' if failure else 'full_history_review_queue_not_admitted',failure=failure,training_admitted=False,policy_sha256=expected,counts=dict(counts),**hashes,seconds=time.monotonic()-start,known_excluded_doc_ids=sorted(bad),limitations='All full histories are review material;319 unknown quarantined,770 oldtrain only upperbound. New root custody and separately approved quality/framing policy required before candidate selection. No dev created.')
 with (D/'receipt.json').open('x') as f:json.dump(receipt,f,indent=2)
 signal.alarm(0)
 if failure:raise RuntimeError(failure)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('policy');p.add_argument('--sha256',required=True);a=p.parse_args();main(a.policy,a.sha256)
