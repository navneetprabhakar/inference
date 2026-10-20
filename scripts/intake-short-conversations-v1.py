"""Acquire distributed official-train pages and protect the complete upstream test."""
# Creator: Navneet Prabhakar
import hashlib,json,os,resource,shutil,time,urllib.parse
from pathlib import Path
import pyarrow.parquet as pq
from slm.data.intake_ledger import IntakeLedger
from slm.data.conversation_intake import fetch,validate_page
from slm.data.stream_hash import sha
ROOT=Path('data/conversation-corpus-intake-v1');CONFIG=Path('configs/conversation-corpus-intake-v1.json')

def guard(ledger):
 ledger.check_time()
 if shutil.disk_usage(ROOT).free<40*1024**3:raise ValueError('40GiB free-space reserve required')
 if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>8*1024**3:raise ValueError('8GiB RSS stop')

def main():
 p=json.loads(CONFIG.read_text())
 if (ROOT/'train.jsonl').exists() or (ROOT/'intake-start.json').exists():raise FileExistsError('Retain previous intake; no automatic restart')
 census=json.loads((ROOT/'census.json').read_text())
 if not census['complete'] or sha(ROOT/'payloads/tree.json')!=census['tree_sha256']:raise ValueError('Pinned census required')
 tree=json.loads((ROOT/'payloads/tree.json').read_text());metadata=json.loads((ROOT/'payloads/metadata.json').read_text())
 splits={x['name']:x['num_examples'] for x in metadata['cardData']['dataset_info']['splits']}
 if splits!={'train':460341,'test':24229}:raise ValueError('Frozen source inventory differs')
 test=next(x for x in tree if x['path']=='data/test-00000-of-00001.parquet')
 ledger=IntakeLedger(ROOT/'ledger',p);(ROOT/'intake-start.json').write_text(json.dumps(dict(parent=os.getpid(),deadline=ledger.deadline,config_sha256=sha(CONFIG)))+'\n')
 try:
  guard(ledger);testpath=ROOT/'payloads/upstream-test.parquet'
  raw=fetch(ledger,'upstream-test-file','https://huggingface.co/datasets/'+p['source']+'/resolve/'+p['revision']+'/'+test['path'],testpath,test['size'])
  if hashlib.sha256(raw).hexdigest()!=test['lfs']['oid']:raise ValueError('Full upstream test LFS digest differs')
  del raw
  ledger.reserve('upstream-test-decode',rows=splits['test'],output_bytes=128*1024**2)
  pf=pq.ParquetFile(testpath)
  if pf.metadata.num_rows!=splits['test'] or sum(pf.metadata.row_group(i).total_byte_size for i in range(pf.num_row_groups))>128*1024**2:raise ValueError('Finite declared complete test required')
  count=written=0
  with (ROOT/'upstream-test.jsonl').open('x') as stream:
   for batch in pf.iter_batches(batch_size=256):
    guard(ledger)
    for row in batch.to_pylist():
     line=json.dumps(dict(official_split='test',row_index=count,**row),ensure_ascii=False)+'\n';written+=len(line.encode())
     if written>128*1024**2:raise ValueError('Bounded test output required')
     stream.write(line);count+=1
  if count!=splits['test']:raise ValueError('Full test protection required')
  ledger.finish('upstream-test-decode',raw=b'')
  offsets=sorted(range(200,460300,100),key=lambda n:hashlib.sha256((p['selection_seed']+'|'+str(n)).encode()).digest())[:200]
  (ROOT/'selection.json').write_text(json.dumps(dict(seed=p['selection_seed'],offsets=offsets,length=100,exclude_original_prefix=200,whole_test_rows=count),indent=2)+'\n')
  count=0
  with (ROOT/'train.jsonl').open('x') as stream:
   for page,offset in enumerate(offsets):
    guard(ledger);params=urllib.parse.urlencode(dict(dataset=p['source'],config='default',split='train',offset=offset,length=100))
    raw=fetch(ledger,'train-page-'+str(offset),'https://datasets-server.huggingface.co/rows?'+params,ROOT/'payloads'/('train-'+str(offset)+'.json'),1024**2,rows=100,revision=p['revision'])
    rows=validate_page(raw,offset,100,p['revision'],splits['train']);ledger.reserve('publish-page-'+str(offset),output_bytes=1024**2)
    text=''.join(json.dumps(dict(official_split='train',row_index=offset+i,**r),ensure_ascii=False)+'\n' for i,r in enumerate(rows))
    if len(text.encode())>1024**2:raise ValueError('Bounded page publication required')
    stream.write(text);stream.flush();os.fsync(stream.fileno());ledger.finish('publish-page-'+str(offset),raw=b'');count+=len(rows)
    (ROOT/'progress.json').write_text(json.dumps(dict(pages=page+1,train_rows=count,upstream_test_rows=splits['test']))+'\n')
    if (page+1)%10==0:print('pages',page+1,'rows',count,flush=True)
  report=dict(creator='Navneet Prabhakar',complete=True,train_rows=count,upstream_test_rows=splits['test'],selection_sha256=sha(ROOT/'selection.json'),train_sha256=sha(ROOT/'train.jsonl'),upstream_test_sha256=sha(ROOT/'upstream-test.jsonl'),ledger=ledger.snapshot(),training_approved=False,scope='Distributed20Kofficial-train candidates, full24229upstream-test protection, no row truncation. Not source/corpus training admission. Original200prefix excluded and prior nonapprovals remain binding.')
  (ROOT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 except BaseException as e:
  (ROOT/'failure.json').write_text(json.dumps(dict(complete=False,error_type=type(e).__name__,message=str(e),ledger=ledger.snapshot(),no_automatic_retry=True),indent=2,sort_keys=True)+'\n');raise
 finally:ledger.close()
if __name__=='__main__':main()
