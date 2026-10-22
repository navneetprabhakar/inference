"""Five exact parent-authorized metadata/license transfers. No corpus bodies."""
import argparse,datetime,hashlib,json,os,shutil,signal,ssl,subprocess,sys,time,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parent;EXEC=HERE.parents[1];REPO=EXEC.parents[1]
sys.path.insert(0,str(EXEC));sys.path.insert(0,str(REPO/'src'))
from acquire_sources import ROOT,CONTRACT,IntakeLedger
PROPOSAL=HERE/'metadata-license-capture-proposal.json'
PROPOSAL_SHA='9176b0a94e611865fd7744e6b9a8ae80e66c991b36e010c9b9e50336067ab263'
DEST=HERE/'metadata-license-capture-v1';CAP=5000000;BODY_CAP=1347584;WORKER_SECONDS=110;EXTERNAL_SECONDS=120
SELF_SHA_FILE=HERE/'capture-code-pin.json'
def sha(b):return hashlib.sha256(b).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def strict_TLS():
 context=ssl.create_default_context();context.check_hostname=True;context.verify_mode=ssl.CERT_REQUIRED;context.minimum_version=ssl.TLSVersion.TLSv1_2
 return context
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**kw):raise ValueError('Redirect forbidden')
def size():return sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file())
def save(name,data):
 b=data if isinstance(data,bytes) else (json.dumps(data,indent=2)+'\n').encode()
 if size()+len(b)>CAP-524288:raise ValueError('Aggregate local output cap')
 with (DEST/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def terminal(name,data):
 slot=131072;p=DEST/name;b=(json.dumps(data,indent=2)+'\n').encode()
 if len(b)>slot:raise ValueError('Terminal slot overflow')
 if not p.exists():
  if size()+slot>CAP:raise ValueError('No terminal slot budget')
  with p.open('xb') as f:f.write(b' '*slot)
 with p.open('r+b') as f:f.write(b+b' '*(slot-len(b)));f.flush();os.fsync(f.fileno())
def pins():
 if sha(PROPOSAL.read_bytes())!=PROPOSAL_SHA:raise ValueError('Exact proposal pin mismatch')
 pin=json.loads(SELF_SHA_FILE.read_text())
 for filename,h in pin['input_code_sha256'].items():
  if sha(Path(filename).read_bytes())!=h:raise ValueError('Input code pin mismatch')
 proposal=json.loads(PROPOSAL.read_text())
 if len(proposal['items'])!=5 or sum(x['body_cap'] for x in proposal['items'])!=BODY_CAP:raise ValueError('Frozen five URL caps mismatch')
 for item in proposal['items']:
  if not item['url'].startswith(('https://raw.githubusercontent.com/openstax/osbooks-world-history/dbe4cb6de157b506f07fab8c52ffe80704578f69/','https://api.github.com/repos/openstax/osbooks-world-history/git/trees/8a4dd8ae49f82bc734713e30586a6e017ba51915?recursive=1')):raise ValueError('Unexpected metadata endpoint')
 return proposal,pin

def worker():
 if os.getppid()!=int(os.environ['METADATA_CAPTURE_PARENT_PID']):raise ValueError('Direct supervisor required')
 start=float(os.environ['METADATA_CAPTURE_SHARED_START']);proposal,pin=pins();ledger=None;receipts=[];started=time.monotonic()
 def guard(extra=0):
  if time.clock_gettime(time.CLOCK_MONOTONIC)-start>=WORKER_SECONDS:raise TimeoutError('Shared worker deadline')
  if size()+extra>CAP-524288:raise ValueError('Aggregate output cap')
  policy=json.loads((EXEC/'disk-budget.json').read_text());protected=policy['free_disk_floor_bytes']+policy['weights_checkpoints_reserved_bytes']+policy['scratch_cap_bytes']
  if shutil.disk_usage(ROOT).free<protected+extra:raise ValueError('Weights scratch freefloor')
 try:
  terminal('worker-result.json',{'status':'RUNNING_NOT_COMPLETE'})
  guard(BODY_CAP)
  policy=json.loads((EXEC/'disk-budget.json').read_text())
  footprint=sum(f.stat().st_size for f in ROOT.rglob('*') if f.is_file())
  if footprint+CAP>policy['processed_data_cap_bytes']:raise ValueError('Combined processed64GB preflight')
  context=strict_TLS()
  opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=context))
  ledger=IntakeLedger(ROOT/'charges',CONTRACT)
  save('preflight.json',{'utc':now(),'proposal_sha256':PROPOSAL_SHA,'code_pins':pin,'global_reserved_before':ledger.totals(),'strict_TLS':{'check_hostname':context.check_hostname,'verify_mode_CERT_REQUIRED':context.verify_mode==ssl.CERT_REQUIRED,'minimum_TLS':'TLSv1.2'},'limits':{'requests':5,'response_body_bytes':BODY_CAP,'output_bytes':CAP,'external_seconds':EXTERNAL_SECONDS},'no_retries_or_redirects':True})
  for i,item in enumerate(proposal['items']):
   guard(item['body_cap']);key=f'openstax-historical-metadata-license-v1-{i:03d}';url=item['url'];raw=bytearray();headers={};partial=DEST/(item['file']+'.partial')
   ledger.reserve(key,requests=1,body_bytes=item['body_cap'],rows=0,output_bytes=CAP if i==0 else 0)
   save(f'request-{i:03d}.json',{'key':key,'url':url,'body_cap':item['body_cap'],'charged_before_IO':True,'utc':now()})
   try:
    request=urllib.request.Request(url,headers={'User-Agent':'EnglishSLM-source-metadata-investigation/1.0','Accept-Encoding':'identity'})
    remaining=WORKER_SECONDS-(time.clock_gettime(time.CLOCK_MONOTONIC)-start)
    with opener.open(request,timeout=min(15,remaining)) as response,partial.open('xb') as f:
     headers=dict(response.headers.items())
     if response.geturl()!=url or response.status!=200:raise ValueError('Unexpected effective URL or status')
     if response.headers.get('Content-Encoding','identity').lower()!='identity':raise ValueError('Unrequested content encoding')
     length=response.headers.get('Content-Length')
     if length is not None and not 0<=int(length)<item['body_cap']:raise ValueError('Declared body reaches cap')
     while len(raw)<item['body_cap']:
      guard(65536);chunk=response.read(min(65536,item['body_cap']-len(raw)))
      if not chunk:break
      raw.extend(chunk);f.write(chunk);f.flush()
     if len(raw)>=item['body_cap']:raise ValueError('Body hits cap, no extra EOF probe')
     if length is not None and int(length)!=len(raw):raise ValueError('Truncated declared body')
     f.flush();os.fsync(f.fileno())
    body=bytes(raw);ledger.finish(key,raw=body);os.rename(partial,DEST/item['file'])
    receipt={'key':key,'url':url,'effective_URL':response.geturl(),'status':200,'headers':headers,'file':item['file'],'body_bytes':len(body),'body_sha256':sha(body),'reserved_body_bytes':item['body_cap'],'utc':now(),'charged_before_IO':True,'redirect':False,'TLS_certificate_and_hostname_verified':True}
    save(f'response-{i:03d}.receipt.json',receipt);receipts.append(receipt)
   except BaseException as e:
    if getattr(e,'headers',None) is not None:headers=dict(e.headers.items())
    row=ledger.db.execute('select state from attempts where key=?',(key,)).fetchone()
    if row and row[0]=='pending':ledger.finish(key,raw=None)
    save(f'response-{i:03d}.failure.json',{'status':'FAILED_NO_RETRY','key':key,'url':url,'received_bytes':len(raw),'received_prefix_sha256':sha(bytes(raw)),'headers':headers,'error':str(e),'exception':type(e).__name__});raise
  guard()
  result={'status':'COMPLETE_FIVE_METADATA_LICENSE_CAPTURES_NO_ADMISSION','receipts':receipts,'requests':5,'actual_response_bytes':sum(x['body_bytes'] for x in receipts),'reserved_response_bytes':BODY_CAP,'global_reserved_after':ledger.totals(),'elapsed_seconds':time.clock_gettime(time.CLOCK_MONOTONIC)-start,'new_admitted_documents':0,'new_admitted_tokens':0,'corpus_modules_or_media_downloaded':0}
  terminal('worker-result.json',result)
 except BaseException as e:
  terminal('worker-result.json',{'status':'TERMINAL_METADATA_CAPTURE_FAILED_NO_RETRY','error':str(e),'receipts':receipts,'new_admitted_documents':0,'new_admitted_tokens':0});raise
 finally:
  if ledger:ledger.close()
def main():
 proposal,pin=pins();DEST.mkdir(exist_ok=False);start=time.clock_gettime(time.CLOCK_MONOTONIC)
 terminal('supervisor-result.json',{'status':'RUNNING_NOT_COMPLETE'});terminal('worker-result.json',{'status':'NOT_STARTED_NOT_COMPLETE'})
 env=dict(os.environ,METADATA_CAPTURE_PARENT_PID=str(os.getpid()),METADATA_CAPTURE_SHARED_START=str(start));proc=None
 try:
  with (DEST/'worker.log').open('xb') as log:
   proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:code=proc.wait(timeout=max(.001,EXTERNAL_SECONDS-(time.clock_gettime(time.CLOCK_MONOTONIC)-start)));timed=False
   except subprocess.TimeoutExpired:
    timed=True;os.killpg(proc.pid,signal.SIGTERM)
    try:code=proc.wait(timeout=2)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);code=proc.wait(timeout=3)
  w=json.loads((DEST/'worker-result.json').read_text());success=not timed and code==0 and w['status']=='COMPLETE_FIVE_METADATA_LICENSE_CAPTURES_NO_ADMISSION' and size()<=CAP
  terminal('supervisor-result.json',{'status':'COMPLETE' if success else 'FAILED','worker_exit_code':code,'worker_pid':proc.pid,'external_timeout':timed,'elapsed_seconds':time.clock_gettime(time.CLOCK_MONOTONIC)-start,'worker_result_sha256':sha((DEST/'worker-result.json').read_bytes()),'retry':False,'new_admitted_documents':0,'new_admitted_tokens':0})
  raise SystemExit(0 if success else 1)
 except BaseException:
  if proc and proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
  raise
if __name__=='__main__':worker() if sys.argv[1:]==['--worker'] else main()
