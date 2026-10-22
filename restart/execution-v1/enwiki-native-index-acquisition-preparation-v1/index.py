"""One native multistream index download; no XML/parser/decompression/admission."""
import argparse,hashlib,importlib.util,json,os,pathlib,shutil,signal,subprocess,sys,time,urllib.request,urllib.error
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake';OUT=ROOT/'enwiki-native-index-20260801-v1'
NAME='enwiki-20260801-pages-articles-multistream-index.txt.bz2';URL='https://dumps.wikimedia.org/enwiki/20260801/'+NAME;SIZE=283588691;MD5='ddb7189ac212f0567376a4db47dabc48';SHA1='49d4f7e965c2311a16a8ace5de74addc4687785e'
KEY='enwiki-native-complete-index-20260801-once-v1';FREE=53474836480;BODY_CAP=300000000;OUTPUT_CAP=305000000
CAPS={'body_bytes':BODY_CAP,'output_bytes':OUTPUT_CAP,'worker_seconds':570,'external_seconds':600,'observed_RSS_bytes':1000000000,'requests':1,'retries':0,'decompressed_bytes':0}
SLOTS={'worker-result.json':65536,'supervisor-result.json':32768}
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):
 d=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):d.update(b)
 return d.hexdigest()
def size(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file())
def write(name,obj):
 b=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()
 if size(OUT)+len(b)>OUTPUT_CAP-1048576:raise ValueError('output_cap')
 with (OUT/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def terminal(name,obj):
 b=(json.dumps(obj,indent=2)+'\n').encode();n=SLOTS[name]
 if len(b)>n:raise ValueError('terminal_slot')
 with (OUT/name).open('r+b') as f:f.write(b+b' '*(n-len(b)));f.flush();os.fsync(f.fileno())
def inventory():
 paths=[HERE/n for n in ['index.py','code_guard.py','checks.py','profile.json']]+[BASE/'acquire_sources.py',REPO/'src/slm/data/intake_ledger.py',REPO/'src/slm/data/schema.py',BASE/'disk-budget.json',BASE/'authorization.json',BASE/'source-acquisition-authorization.json',ROOT/'gutenberg-preparation-parallel-v4/discover.py',pathlib.Path('/opt/homebrew/etc/ca-certificates/cert.pem'),ROOT/'enwiki-native-html-option-v1/acquisition-options.json',ROOT/'native-supply-investigation-v1/enwiki-dumpstatus.json',ROOT/'native-supply-investigation-v1/metadata-retrieval-receipts.json']
 return {str(p.resolve()) for p in paths}
def verify(code,prof):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=prof:raise ValueError('external_profile_pin')
 p=json.loads((HERE/'profile.json').read_text())
 if p['limits']!=CAPS or p['url']!=URL or p['name']!=NAME or p['expected_bytes']!=SIZE or p['publisher_MD5']!=MD5 or p['publisher_SHA1']!=SHA1:raise ValueError('fixed_index_identity_caps')
 options=json.loads((ROOT/'enwiki-native-html-option-v1/acquisition-options.json').read_text())
 actual=[f for f in options['native_XML_option']['files'] if f['name']==NAME]
 if sha(pathlib.Path(options['native_XML_option']['cached_metadata_file']))!=options['native_XML_option']['cached_metadata_SHA256'] or sha(pathlib.Path(options['native_XML_option']['metadata_retrieval_receipt_file']))!=options['native_XML_option']['metadata_retrieval_receipt_SHA256']:raise ValueError('retained_publisher_metadata_provenance')
 if len(actual)!=1 or actual[0]['absolute_URL']!=URL or actual[0]['size']!=SIZE or actual[0]['md5']!=MD5 or actual[0]['sha1']!=SHA1:raise ValueError('publisher_metadata_binding')
 return p

def dependencies():
 sys.path[:0]=[str(REPO/'src'),str(BASE)]
 from acquire_sources import IntakeLedger,CONTRACT
 path=ROOT/'gutenberg-preparation-parallel-v4/discover.py';spec=importlib.util.spec_from_file_location('pinned_TLS',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 return IntakeLedger,CONTRACT,m

def stream(response,target,start,check=lambda:None):
 n=0;digests=[hashlib.md5(),hashlib.sha1(),hashlib.sha256()]
 with target.open('xb') as f:
  try:
   while True:
    if clk()-start>=570:raise TimeoutError('worker_deadline')
    check();chunk=response.read1(min(1048576,SIZE+1-n))
    if not chunk:break
    if n+len(chunk)>BODY_CAP:raise ValueError('reserved_body_cap')
    f.write(chunk);n+=len(chunk)
    for h in digests:h.update(chunk)
    if n>SIZE:raise ValueError('exact_size_exceeded')
  finally:f.flush();os.fsync(f.fileno())
 actual=[d.hexdigest() for d in digests]
 if n!=SIZE or actual[0]!=MD5 or actual[1]!=SHA1:raise ValueError('size_or_publisher_checksum_mismatch')
 return n,actual

def worker(a):
 verify(a.code_pins_sha256,a.profile_sha256);start=float(a.start)
 if os.getppid()!=a.supervisor_pid:raise ValueError('parent_identity')
 Ledger,contract,tls=dependencies();ledger=None;reserved=False;partial=OUT/'index.partial'
 try:
  ledger=Ledger(ROOT/'charges',contract);ledger.reserve(KEY,requests=1,body_bytes=BODY_CAP,output_bytes=OUTPUT_CAP);reserved=True
  write('preflight.json',{'url':URL,'expected_bytes':SIZE,'publisher_MD5':MD5,'publisher_SHA1':SHA1,'allocation':CAPS,'global_reserved':ledger.totals(),'local_only':True,'protected_free_bytes':FREE,'no_XML_requested':True})
  class NoAuto(urllib.request.HTTPRedirectHandler):
   def redirect_request(self,*a,**kw):return None
  opener=urllib.request.build_opener(NoAuto(),urllib.request.HTTPSHandler(context=tls.trusted_context()))
  req=urllib.request.Request(URL,headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity'})
  try:response=opener.open(req,timeout=30)
  except urllib.error.HTTPError as e:response=e
  with response:
   write('response-headers.json',{'url':response.geturl(),'status':response.code,'headers':list(response.headers.items())})
   if response.code!=200 or response.geturl()!=URL:raise ValueError('non200_or_redirect_no_retry')
   if response.headers.get('Content-Encoding') not in [None,'identity']:raise ValueError('encoded_transfer')
   if response.headers.get('Content-Length') not in [None,str(SIZE)]:raise ValueError('advertised_length_mismatch')
   def check():
    ledger.check_time()
    if shutil.disk_usage(ROOT).free<FREE+1048576:raise ValueError('free_weights_scratch_floor')
    if size(OUT)+1048576>OUTPUT_CAP-1048576:raise ValueError('output_cap')
   n,hashes=stream(response,partial,start,check)
  # Existing bounded archive downloaders' streaming ledger completion convention.
  cur=ledger.db.execute('update attempts set state=?,actual_bytes=?,body_sha256=? where key=? and state=?',('complete',n,hashes[2],KEY,'pending'))
  if cur.rowcount!=1:raise ValueError('ledger_pending_completion_lost')
  os.rename(partial,OUT/NAME);fd=os.open(OUT,os.O_RDONLY);os.fsync(fd);os.close(fd)
  verify(a.code_pins_sha256,a.profile_sha256)
  terminal('worker-result.json',{'status':'COMPLETE_COMPRESSED_NATIVE_INDEX_ONLY_NO_ADMISSION','url':URL,'file':NAME,'bytes':n,'MD5':hashes[0],'SHA1':hashes[1],'local_SHA256':hashes[2],'publisher_checksums_match':True,'elapsed_seconds':clk()-start,'global_reserved':ledger.totals(),'source_archive_XML_requests':0,'index_decompressed_bytes':0,'new_admitted_documents':0,'new_admitted_tokens':0,'parser_created':False})
 except BaseException as e:
  if reserved and ledger.db.execute('select state from attempts where key=?',(KEY,)).fetchone()==('pending',):ledger.finish(KEY,raw=None)
  terminal('worker-result.json',{'status':'TERMINAL_PARTIAL_INDEX_NO_RETRY','error':type(e).__name__+':'+str(e)[:2000],'reserved':reserved,'partial_bytes':partial.stat().st_size if partial.exists() else 0,'partial_SHA256':sha(partial) if partial.exists() else None,'new_admitted_documents':0});raise
 finally:
  if ledger is not None:ledger.close()

def settle_owned(ledger):
 row=ledger.db.execute('select state from attempts where key=?',(KEY,)).fetchone()
 if row==('pending',):ledger.finish(KEY,raw=None);return 'failed_charge_retained'
 return row[0] if row else 'no_allocation'

def cleanup_ledger():
 try:
  L,C,T=dependencies();ledger=L(ROOT/'charges',C)
  try:return settle_owned(ledger)
  finally:ledger.close()
 except BaseException as e:return 'cleanup_hold:'+type(e).__name__+':'+str(e)[:300]

def kill(p):
 if p.poll() is None:
  try:os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 p.wait(timeout=3)
def supervise(a):
 start=clk();verify(a.code_pins_sha256,a.profile_sha256)
 if OUT.exists() or ROOT.is_symlink() or any(p.is_symlink() for p in ROOT.rglob('*')):raise ValueError('existing_output_or_intake_symlink')
 if size(ROOT)+OUTPUT_CAP>64000000000 or shutil.disk_usage(ROOT).free<FREE+OUTPUT_CAP:raise ValueError('combined_intake_or_disk_reserves')
 OUT.mkdir()
 for name,n in SLOTS.items():
  with (OUT/name).open('xb') as f:f.write(b' '*n);f.flush();os.fsync(f.fileno())
 child=None;peak=0;reason=None
 def stop(s,f):raise RuntimeError('external_signal_'+str(s))
 old={s:signal.signal(s,stop) for s in [signal.SIGTERM,signal.SIGINT]}
 try:
  child=subprocess.Popen([sys.executable,str(HERE/'index.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  write('ownership.json',{'supervisor_pid':os.getpid(),'worker_pid':child.pid,'shared_start':start,'code_pins_sha256':a.code_pins_sha256,'profile_sha256':a.profile_sha256})
  while child.poll() is None:
   if clk()-start>=570:reason='work570seconds';break
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rows=[tuple(map(int,l.split())) for l in ps.stdout.splitlines() if len(l.split())==3];owned={os.getpid()}
   while True:
    nxt=owned|{p for p,q,r in rows if q in owned}
    if nxt==owned:break
    owned=nxt
   rss=sum(r*1024 for p,q,r in rows if p in owned);peak=max(peak,rss)
   if rss>1000000000:reason='observed_RSS1GB';break
   if size(OUT)>OUTPUT_CAP or size(ROOT)>64000000000 or shutil.disk_usage(ROOT).free<FREE:reason='output_intake_or_free_cap';break
   time.sleep(.5)
  if reason:kill(child)
  else:child.wait(timeout=3)
  raw=(OUT/'worker-result.json').read_text();r=json.loads(raw) if raw.strip() else {};ok=child.returncode==0 and reason is None and r.get('status')=='COMPLETE_COMPRESSED_NATIVE_INDEX_ONLY_NO_ADMISSION' and clk()-start<600
  if ok and sha(OUT/NAME)!=r['local_SHA256']:ok=False;reason='terminal_rehash_mismatch'
  ledger_state=cleanup_ledger()
  terminal('supervisor-result.json',{'status':'COMPLETE_INDEX_ACQUISITION_NO_ADMISSION' if ok else 'PARTIAL_INDEX_NO_RETRY','reason':reason,'owned_ledger_terminal_state':ledger_state,'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'output_bytes':size(OUT),'worker_receipt_sha256':sha(OUT/'worker-result.json'),'new_admitted_documents':0,'new_admitted_tokens':0});return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  ledger_state=cleanup_ledger()
  terminal('supervisor-result.json',{'status':'PARTIAL_INDEX_NO_RETRY','reason':type(e).__name__+':'+str(e)[:2000],'owned_ledger_terminal_state':ledger_state,'elapsed_seconds':clk()-start,'new_admitted_documents':0});raise
 finally:
  for s,h in old.items():signal.signal(s,h)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--supervisor-pid',type=int);p.add_argument('--start');p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True);a=p.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a.code_pins_sha256,a.profile_sha256);print('PINNED_INDEX_PREPARED_NO_NETWORK')
