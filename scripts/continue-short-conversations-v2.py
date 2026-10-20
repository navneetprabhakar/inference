"""Continue distinct selected pages; retain failed requests and original limits."""
# Creator: Navneet Prabhakar
import hashlib,json,os,resource,shutil,urllib.error,urllib.parse
from pathlib import Path
from slm.data.intake_ledger import IntakeLedger
from slm.data.conversation_intake import fetch,validate_page
from slm.data.stream_hash import sha
OLD=Path('data/conversation-corpus-intake-v1');OUT=Path('data/conversation-corpus-continuation-v2')
CONFIG=Path('configs/conversation-corpus-continuation-v2.json')

def main():
 p=json.loads(CONFIG.read_text())
 for name,h in p['inputs'].items():
  if sha(name)!=h:raise ValueError('Retained continuation input changed: '+name)
 if OUT.exists():raise FileExistsError('No automatic duplicate continuation')
 failed=json.loads((OLD/'failure.json').read_text())
 if failed['error_type']!='HTTPError' or not any(str(x) in failed['message'] for x in (500,502,503,504)):raise ValueError('Only known transient gateway failure supports this continuation')
 original=json.loads(Path('configs/conversation-corpus-intake-v1.json').read_text());selection=json.loads((OLD/'selection.json').read_text())
 ledger=IntakeLedger(OLD/'ledger',original);OUT.mkdir();(OUT/'payloads').mkdir();prior=ledger.snapshot();states={x['key']:x['state'] for x in prior['attempts']}
 pending=[x for x in prior['attempts'] if x['state']=='pending']
 if pending:raise ValueError('Uncertain in-flight request must not be replayed')
 completed=[];skipped=[]
 for offset in selection['offsets']:
  state=states.get('train-page-'+str(offset))
  if state=='complete':completed.append(offset)
  elif state=='failed':skipped.append(offset)
 oldrows=[json.loads(x) for x in (OLD/'train.jsonl').read_text().splitlines()]
 if len(oldrows)!=100 or len(completed)!=1 or len(skipped)!=1:raise ValueError('Exact one-page/one-failure continuation required')
 (OUT/'process.json').write_text(json.dumps(dict(parent=os.getpid(),original_deadline=ledger.deadline,continuation_config_sha256=sha(CONFIG)))+'\n')
 try:
  with (OUT/'train.jsonl').open('x') as stream:
   for row in oldrows:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
   count=len(oldrows)
   for offset in selection['offsets']:
    if offset in completed or offset in skipped:continue
    ledger.check_time()
    if shutil.disk_usage(OUT).free<40*1024**3 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>8*1024**3:raise ValueError('Original disk/RSS guard')
    params=urllib.parse.urlencode(dict(dataset=original['source'],config='default',split='train',offset=offset,length=100))
    try:raw=fetch(ledger,'train-page-'+str(offset),'https://datasets-server.huggingface.co/rows?'+params,OUT/'payloads'/('train-'+str(offset)+'.json'),1024**2,rows=100,revision=original['revision'])
    except urllib.error.HTTPError as e:
     if e.code not in (500,502,503,504):raise
     skipped.append(offset)
     (OUT/'skipped-transports.json').write_text(json.dumps(skipped)+'\n')
     if len(skipped)>10:raise RuntimeError('Too many transport failures; no endless source attempts')
     continue
    rows=validate_page(raw,offset,100,original['revision'],460341);text=''.join(json.dumps(dict(official_split='train',row_index=offset+i,**r),ensure_ascii=False)+'\n' for i,r in enumerate(rows))
    ledger.reserve('publish-page-'+str(offset),output_bytes=1024**2)
    if len(text.encode())>1024**2:raise ValueError('Bounded publication required')
    stream.write(text);stream.flush();os.fsync(stream.fileno());ledger.finish('publish-page-'+str(offset),raw=b'');count+=100;completed.append(offset)
    (OUT/'progress.json').write_text(json.dumps(dict(train_rows=count,pages_complete=len(completed),pages_skipped=len(skipped),original_deadline=ledger.deadline))+'\n')
    if len(completed)%10==0:print('complete pages',len(completed),'rows',count,'skipped',len(skipped),flush=True)
  report=dict(creator='Navneet Prabhakar',complete=True,train_rows=count,pages_complete=len(completed),skipped_offsets=skipped,upstream_test_rows=24229,upstream_test_path=str(OLD/'upstream-test.jsonl'),upstream_test_sha256=sha(OLD/'upstream-test.jsonl'),train_sha256=sha(OUT/'train.jsonl'),original_immutable_failure_sha256=sha(OLD/'failure.json'),ledger=ledger.snapshot(),training_approved=False,scope='Same original selected pages/caps/deadline. Failed requests retained/charged and never retried; original successful page cloned, not refetched. Transport exclusions may bias retained sample. No admission.')
  (OUT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 except BaseException as e:
  (OUT/'failure.json').write_text(json.dumps(dict(complete=False,error_type=type(e).__name__,message=str(e),ledger=ledger.snapshot()),indent=2,sort_keys=True)+'\n');raise
 finally:ledger.close()
if __name__=='__main__':main()
