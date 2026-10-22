"""Bounded exact162 historical OpenStax native XML acquisition. No admission."""
import argparse,datetime,hashlib,json,math,os,shutil,signal,ssl,subprocess,sys,time,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;REPO=EXEC.parents[1]
sys.path.insert(0,str(EXEC));sys.path.insert(0,str(REPO/'src'))
from acquire_sources import ROOT,CONTRACT,IntakeLedger
POLICY=HERE/'policy.json';PINS=HERE/'code-pins.json'
EXPECTED_POLICY_SHA='7a8a5126dc31cff7d4e5638d31aa77599bc5f5a66febf80962fd69db9a8855c3'
DEST=ROOT/'openstax-world-history-native-source-v1';CAP=32000000;WORKER_SECONDS=570;EXTERNAL_SECONDS=600;TERMINAL_HEADROOM=524288

def sha(b):return hashlib.sha256(b).hexdigest()
def git_blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def clock():
 x=time.clock_gettime(time.CLOCK_MONOTONIC)
 if not math.isfinite(x) or x<0:raise ValueError('Invalid shared clock')
 return x
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Redirect forbidden')
def strict_TLS():
 c=ssl.create_default_context();c.check_hostname=True;c.verify_mode=ssl.CERT_REQUIRED;c.minimum_version=ssl.TLSVersion.TLSv1_2;return c

def output_size():return sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file())
def ensure_output(additional):
 if additional<0 or output_size()+additional>CAP-TERMINAL_HEADROOM:raise ValueError('Aggregate prewrite output bound')
def save(name,data):
 b=data if isinstance(data,bytes) else (json.dumps(data,indent=2)+'\n').encode();ensure_output(len(b))
 with (DEST/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def terminal(name,data):
 slot=131072;p=DEST/name;b=(json.dumps(data,indent=2)+'\n').encode()
 if len(b)>slot:raise ValueError('Terminal slot bound')
 if not p.exists():
  if output_size()+slot>CAP:raise ValueError('Terminal preallocation bound')
  with p.open('xb') as f:f.write(b' '*slot)
 with p.open('r+b') as f:f.write(b+b' '*(slot-len(b)));f.flush();os.fsync(f.fileno())

def verify_policy(policy):
 items=policy['items'];limits=policy['limits']
 if len(items)!=162 or len({i['module_ID'] for i in items})!=162 or len({i['native_path'] for i in items})!=162:raise ValueError('Exact unique162 frame required')
 if sum(i['expected_bytes'] for i in items)!=5565778 or sum(i['body_cap'] for i in items)!=5565940 or sum(i['body_cap'] for i in items)>6000000:raise ValueError('Frozen source byte totals')
 if sum(len(i['collection_appearances']) for i in items)!=165:raise ValueError('Shared collection appearances must survive')
 for item in items:
  mid=item['module_ID'];path='modules/'+mid+'/index.cnxml'
  if item['native_path']!=path or item['url']!='https://raw.githubusercontent.com/openstax/osbooks-world-history/'+policy['commit']+'/'+path:raise ValueError('Exact native module URL only')
  if item['body_cap']!=item['expected_bytes']+1 or item['expected_bytes']<=0 or len(item['expected_Git_blob_SHA1'])!=40:raise ValueError('Expected size-plus-one and Gitblob required')
 return policy

def pins():
 if sha(POLICY.read_bytes())!=EXPECTED_POLICY_SHA:raise ValueError('Frozen policy pin mismatch')
 pin=json.loads(PINS.read_text())
 for name,h in pin['input_code_SHA256'].items():
  if sha(Path(name).read_bytes())!=h:raise ValueError('Code or global policy pin mismatch')
 policy=verify_policy(json.loads(POLICY.read_text()))
 for name,h in policy['input_evidence_SHA256'].items():
  if sha(Path(name).read_bytes())!=h:raise ValueError('Historical source evidence pin mismatch')
 return policy,pin

def check_spacing(last_start,current):
 if last_start is not None and current-last_start<1:raise ValueError('One request per second serial guard')
def verify_body(raw,item):
 if len(raw)!=item['expected_bytes']:raise ValueError('Exact native file length mismatch')
 if git_blob(raw)!=item['expected_Git_blob_SHA1']:raise ValueError('Exact native Gitblob SHA1 mismatch')
 return {'body_bytes':len(raw),'body_SHA256':sha(raw),'Git_blob_SHA1':git_blob(raw),'expected_source_match':True}

def read_response(response,item,handle,guard):
 if response.geturl()!=item['url'] or response.status!=200:raise ValueError('Unexpected effective URL or status')
 if response.headers.get('Content-Encoding','identity').lower()!='identity':raise ValueError('Unrequested content encoding')
 length=response.headers.get('Content-Length')
 if length is not None and int(length)!=item['expected_bytes']:raise ValueError('Declared exact native length mismatch')
 raw=bytearray()
 while len(raw)<item['body_cap']:
  guard(min(65536,item['body_cap']-len(raw)))
  chunk=response.read(min(65536,item['body_cap']-len(raw)))
  if not chunk:break
  raw.extend(chunk);handle.write(chunk);handle.flush()
 if len(raw)>=item['body_cap']:raise ValueError('Response hits size-plus-one cap; no unreserved EOF probe')
 handle.flush();os.fsync(handle.fileno());return bytes(raw)

def worker():
 if os.getppid()!=int(os.environ['OPENSTAX162_PARENT_PID']):raise ValueError('Live direct supervisor required')
 start=float(os.environ['OPENSTAX162_SHARED_START']);policy,pin=pins();ledger=None;receipts=[];last_start=None
 def guard(additional=0):
  if not 0<=clock()-start<WORKER_SECONDS:raise TimeoutError('Shared worker deadline')
  ensure_output(additional)
  dp=json.loads((EXEC/'disk-budget.json').read_text());protected=dp['free_disk_floor_bytes']+dp['weights_checkpoints_reserved_bytes']+dp['scratch_cap_bytes']
  if shutil.disk_usage(ROOT).free<protected+additional:raise ValueError('Protected weights scratch freefloor')
 try:
  terminal('worker-result.json',{'status':'RUNNING_NOT_COMPLETE'})
  guard(CAP-TERMINAL_HEADROOM-output_size())
  disk=json.loads((EXEC/'disk-budget.json').read_text());footprint=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())
  if footprint+CAP>disk['processed_data_cap_bytes']:raise ValueError('Combined64GB processed preflight')
  ledger=IntakeLedger(ROOT/'charges',CONTRACT)
  context=strict_TLS();opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=context))
  save('preflight.json',{'utc':now(),'policy_SHA256':EXPECTED_POLICY_SHA,'code_pins':pin,'global_reserved_before':ledger.totals(),'strict_TLS_certificate_hostname_validation':True,'minimum_TLS':'TLSv1.2','native_source_files':162,'collection_appearances':165,'no_eligibility_or_rights_clearance':True})
  # Frozen source frame preserves the three shared book appearances.
  save('source-frame.json',policy)
  for index,item in enumerate(policy['items']):
   guard(item['body_cap'])
   if last_start is not None:
    delay=max(0,1-(clock()-last_start))
    if delay:time.sleep(delay)
   guard();request_start=clock();check_spacing(last_start,request_start)
   key=f'openstax-worldhistory-2024-native162-v1-{item["module_ID"]}'
   ledger.reserve(key,requests=1,body_bytes=item['body_cap'],rows=1,output_bytes=CAP if index==0 else 0)
   save(f'request-{index:03d}.json',{'key':key,'url':item['url'],'body_cap':item['body_cap'],'expected_bytes':item['expected_bytes'],'charged_before_IO':True,'pre_IO_reservation_shared_clock':request_start,'utc':now()})
   headers={};partial=DEST/(item['module_ID']+'.cnxml.partial');raw=b''
   try:
    request=urllib.request.Request(item['url'],headers={'User-Agent':'EnglishSLM-native-source-acquisition/1.0','Accept-Encoding':'identity'})
    timeout=min(15,WORKER_SECONDS-(clock()-start))
    request_start=clock();check_spacing(last_start,request_start);last_start=request_start
    with opener.open(request,timeout=timeout) as response,partial.open('xb') as handle:
     headers=dict(response.headers.items());raw=read_response(response,item,handle,guard)
    ledger.finish(key,raw=raw);os.rename(partial,DEST/(item['module_ID']+'.cnxml'))
    # Record transport truth before source integrity validation. A mismatch
    # remains visible and stops the run; it is never retried or admitted.
    receipt={'key':key,'url':item['url'],'effective_URL':response.geturl(),'headers':headers,'body_bytes':len(raw),'body_SHA256':sha(raw),'Git_blob_SHA1':git_blob(raw),'expected_source_match':len(raw)==item['expected_bytes'] and git_blob(raw)==item['expected_Git_blob_SHA1'],'reserved_body_bytes':item['body_cap'],'module_ID':item['module_ID'],'native_path':item['native_path'],'collection_appearances':item['collection_appearances'],'charged_before_IO':True,'request_start_shared_clock':request_start,'utc':now(),'strict_TLS_certificate_hostname_validation':True,'redirect':False,'license_and_quality_review':'PENDING_NOT_CLEARED','training_admitted':False}
    save(f'response-{index:03d}.receipt.json',receipt);receipts.append(receipt);verify_body(raw,item)
    print(json.dumps({'completed_source_files':len(receipts),'actual_bytes':sum(x['body_bytes'] for x in receipts),'last_module':item['module_ID'],'rights_and_quality_clearance':False}),flush=True)
   except BaseException as error:
    if getattr(error,'headers',None) is not None:headers=dict(error.headers.items())
    state=ledger.db.execute('select state from attempts where key=?',(key,)).fetchone()
    if state and state[0]=='pending':ledger.finish(key,raw=None)
    save(f'response-{index:03d}.failure.json',{'status':'TERMINAL_FAILED_NO_RETRY','key':key,'url':item['url'],'headers':headers,'error':str(error),'exception_type':type(error).__name__,'partial_file_bytes':partial.stat().st_size if partial.exists() else 0,'partial_file_SHA256':sha(partial.read_bytes()) if partial.exists() else None,'source_integrity_not_accepted':True});raise
  guard()
  if len(receipts)!=162 or sum(r['body_bytes'] for r in receipts)!=5565778:raise ValueError('Complete exact source count/bytes required')
  terminal('worker-result.json',{'status':'COMPLETE162_NATIVE_SOURCE_FILES_NOT_CLEARED_OR_ADMITTED','source_files':162,'collection_appearances':165,'actual_response_bytes':5565778,'reserved_response_bytes':5565940,'source_frame_SHA256':sha((DEST/'source-frame.json').read_bytes()),'receipt_manifest_SHA256':sha(json.dumps(receipts,sort_keys=True).encode()),'global_reserved_after':ledger.totals(),'elapsed_seconds':clock()-start,'new_admitted_documents':0,'new_admitted_tokens':0,'models_initialized':0,'rights_and_quality_clearance':False})
 except BaseException as error:
  terminal('worker-result.json',{'status':'TERMINAL_NATIVE_SOURCE_ACQUISITION_FAILED_NO_RETRY','error':str(error),'completed_transport_receipts':len(receipts),'actual_bytes_in_completed_receipts':sum(r['body_bytes'] for r in receipts),'elapsed_seconds':clock()-start,'new_admitted_documents':0,'new_admitted_tokens':0});raise
 finally:
  if ledger:ledger.close()

def execute():
 policy,pin=pins();DEST.mkdir(exist_ok=False);start=clock();proc=None
 terminal('supervisor-result.json',{'status':'RUNNING_NOT_COMPLETE'});terminal('worker-result.json',{'status':'NOT_STARTED_NOT_COMPLETE'})
 env=dict(os.environ,OPENSTAX162_PARENT_PID=str(os.getpid()),OPENSTAX162_SHARED_START=str(start))
 try:
  with (DEST/'worker.log').open('xb') as log:
   proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:code=proc.wait(timeout=max(.001,EXTERNAL_SECONDS-(clock()-start)));timed=False
   except subprocess.TimeoutExpired:
    timed=True;os.killpg(proc.pid,signal.SIGTERM)
    try:code=proc.wait(timeout=2)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);code=proc.wait(timeout=3)
  w=json.loads((DEST/'worker-result.json').read_text());success=code==0 and not timed and w['status']=='COMPLETE162_NATIVE_SOURCE_FILES_NOT_CLEARED_OR_ADMITTED' and output_size()<CAP
  terminal('supervisor-result.json',{'status':'COMPLETE' if success else 'FAILED','worker_exit_code':code,'worker_pid':proc.pid,'external_timeout':timed,'elapsed_seconds':clock()-start,'worker_result_SHA256':sha((DEST/'worker-result.json').read_bytes()),'retry':False,'new_admitted_documents':0,'new_admitted_tokens':0})
  raise SystemExit(0 if success else 1)
 finally:
  if proc and proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');args=p.parse_args();policy,pin=pins()
 if args.execute:execute()
 else:print(json.dumps({'status':'READY_NOT_EXECUTED','limits':policy['limits'],'output':str(DEST)}))
if __name__=='__main__':worker() if sys.argv[1:]==['--worker'] else main()
