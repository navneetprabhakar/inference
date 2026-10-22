"""One proposed full native XML acquisition. No request without --execute and pins."""
import argparse,hashlib,importlib.util,json,os,pathlib,shutil,signal,subprocess,sys,time,urllib.request,urllib.error,http.client,ssl,sqlite3,socket,platform,_ssl,_hashlib,_sqlite3
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake';OUT=ROOT/'enwiki-native-full-XML-20260801-v1'
NAME='enwiki-20260801-pages-articles-multistream.xml.bz2';URL='https://dumps.wikimedia.org/enwiki/20260801/'+NAME
SIZE=26668484995;MD5='b6c5a530175db4f5a46cc1439cdac27d';SHA1='dd27f408e60d3bc864d42547fb0a0d7408249c13'
KEY='enwiki-full-native-XML-20260801-once-v1';BODY_CAP=SIZE+1;OUTPUT_CAP=26700000000;FREE=53474836480;COMBINED_CAP=64000000000
WORK=28680;EXTERNAL=28800;RSS=1000000000;HEADERS=65536;CHUNK=1048576;META_RESERVE=1048576
CAPS={'body_bytes':BODY_CAP,'output_bytes':OUTPUT_CAP,'worker_seconds':WORK,'external_seconds':EXTERNAL,'observed_RSS_bytes':RSS,'requests':1,'retries':0,'redirects':0,'header_bytes':HEADERS,'socket_stall_seconds':30,'decompressed_bytes':0}
SLOTS={'worker-result.json':65536,'supervisor-result.json':32768,'progress.json':16384}
OPTIONS=ROOT/'enwiki-native-html-option-v1/acquisition-options.json'
TLS_PATH=ROOT/'gutenberg-preparation-parallel-v4/discover.py';CA=pathlib.Path('/opt/homebrew/etc/ca-certificates/cert.pem')
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):
 d=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(CHUNK),b''):d.update(b)
 return d.hexdigest()
def size(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file())
def runtime():return {'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'openssl':ssl.OPENSSL_VERSION,'sqlite':sqlite3.sqlite_version,'platform':platform.platform(),'native_module_origins':{m.__name__:m.__spec__.origin for m in [_ssl,_hashlib,_sqlite3]}}
def inventory():
 paths=[HERE/n for n in ['archive.py','code_guard.py','checks.py','profile.json']]+[BASE/'acquire_sources.py',REPO/'src/slm/data/intake_ledger.py',REPO/'src/slm/data/schema.py',BASE/'disk-budget.json',BASE/'authorization.json',BASE/'source-acquisition-authorization.json',TLS_PATH,CA,OPTIONS,ROOT/'native-supply-investigation-v1/enwiki-dumpstatus.json',ROOT/'native-supply-investigation-v1/metadata-retrieval-receipts.json',ROOT/'enwiki-native-index-20260801-v1/worker-result.json',ROOT/'enwiki-native-index-20260801-v1/supervisor-result.json',ROOT/'enwiki-native-index-assessment-v1/selection.json',ROOT/'enwiki-native-index-assessment-v1/result.json',ROOT/'enwiki-native-index-assessment-v1/supervisor.json',ROOT/'enwiki-native-20row-ranges-20260801-v2/worker-result.json',ROOT/'enwiki-native-20row-ranges-20260801-v2/supervisor-result.json',ROOT/'enwiki-native-20row-capture-v1/result.json',ROOT/'enwiki-native-20row-capture-v1/supervisor.json']
 paths += [pathlib.Path(m.__file__) for m in [urllib.request,urllib.error,http.client,ssl,sqlite3,sqlite3.dbapi2,socket,hashlib,subprocess,signal,platform,_ssl,_hashlib,_sqlite3] if getattr(m,'__file__',None)]
 paths.append(pathlib.Path(sys.executable))
 return {str(p.resolve()) for p in paths}
def verify(code,prof):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=prof:raise ValueError('external_profile_pin')
 p=json.loads((HERE/'profile.json').read_text())
 if p['limits']!=CAPS or p['URL']!=URL or p['name']!=NAME or p['expected_bytes']!=SIZE or p['publisher_MD5']!=MD5 or p['publisher_SHA1']!=SHA1 or p['output']!=str(OUT):raise ValueError('fixed_archive_identity_caps')
 policy=json.loads((BASE/'disk-budget.json').read_text())
 if policy['raw_download_cap_bytes']!=80000000000 or policy['processed_data_cap_bytes']!=COMBINED_CAP or sum(policy[k] for k in ['weights_checkpoints_reserved_bytes','scratch_cap_bytes','free_disk_floor_bytes'])!=FREE:raise ValueError('fixed_storage_policy')
 options=json.loads(OPTIONS.read_text())['native_XML_option'];entries=[f for f in options['files'] if f['name']==NAME]
 if len(entries)!=1 or entries[0]['absolute_URL']!=URL or entries[0]['size']!=SIZE or entries[0]['md5']!=MD5 or entries[0]['sha1']!=SHA1 or options['source_job_status']!='done':raise ValueError('publisher_option_identity')
 if sha(pathlib.Path(options['cached_metadata_file']))!=options['cached_metadata_SHA256'] or sha(pathlib.Path(options['metadata_retrieval_receipt_file']))!=options['metadata_retrieval_receipt_SHA256']:raise ValueError('retained_metadata_chain')
 official=json.loads(pathlib.Path(options['cached_metadata_file']).read_text());found=[j['files'][NAME] for j in official['jobs'].values() if NAME in j.get('files',{})]
 if len(found)!=1 or any(found[0][k]!=v for k,v in [('size',SIZE),('md5',MD5),('sha1',SHA1)]) or found[0]['url']!='/enwiki/20260801/'+NAME:raise ValueError('official_dumpstatus_binding')
 if http.client._MAXLINE!=65536 or http.client._MAXHEADERS!=100:raise ValueError('HTTP_parser_bound_drift')
 return p

def dependencies():
 sys.path[:0]=[str(REPO/'src'),str(BASE)]
 import acquire_sources
 from slm.data import intake_ledger
 if pathlib.Path(acquire_sources.__file__).resolve()!=BASE/'acquire_sources.py' or pathlib.Path(intake_ledger.__file__).resolve()!=REPO/'src/slm/data/intake_ledger.py':raise ValueError('import_origin')
 spec=importlib.util.spec_from_file_location('pinned_archive_TLS',TLS_PATH);tls=importlib.util.module_from_spec(spec);spec.loader.exec_module(tls)
 # Preflight TLS trust even for nonexecuting command. No socket is opened.
 tls.trusted_context()
 return acquire_sources.IntakeLedger,acquire_sources.CONTRACT,tls

def check_storage(additional=0,check_intake=True):
 if additional<0 or size(OUT)+additional>OUTPUT_CAP-META_RESERVE:raise ValueError('profile_output_cap')
 if check_intake and size(ROOT)+additional>COMBINED_CAP:raise ValueError('conservative_combined_raw_processed_cap')
 if shutil.disk_usage(ROOT).free<FREE+additional:raise ValueError('weights_scratch_free_floor')
def write(name,obj):
 b=(json.dumps(obj,indent=2,ensure_ascii=False)+'\n').encode();check_storage(len(b))
 with (OUT/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def terminal(name,obj):
 b=(json.dumps(obj,indent=2,ensure_ascii=False)+'\n').encode();n=SLOTS[name]
 if len(b)>n:raise ValueError('fixed_terminal_slot')
 with (OUT/name).open('r+b') as f:f.write(b+b' '*(n-len(b)));f.flush();os.fsync(f.fileno())
def reserve(ledger):ledger.reserve(KEY,requests=1,body_bytes=BODY_CAP,output_bytes=OUTPUT_CAP)
def require_pending(ledger):
 row=ledger.db.execute('select charge,state from attempts where key=?',(KEY,)).fetchone()
 if row is None or row[1]!='pending' or json.loads(row[0])!={'requests':1,'body_bytes':BODY_CAP,'rows':0,'output_bytes':OUTPUT_CAP}:raise ValueError('exact_precharged_profile_required')
def settle(ledger):
 row=ledger.db.execute('select state,actual_bytes,body_sha256 from attempts where key=?',(KEY,)).fetchone()
 if row and row[0]=='pending':ledger.finish(KEY,raw=None);row=('failed',None,None)
 return {'key':KEY,'state':row[0],'actual_bytes':row[1],'body_sha256':row[2],'conservative_reservations_retained':True} if row else {'key':KEY,'state':'never_allocated'}
def cleanup():
 try:
  L,C,T=dependencies();ledger=L(ROOT/'charges',C)
  try:return settle(ledger)
  finally:ledger.close()
 except BaseException as e:return {'state':'cleanup_hold','error':type(e).__name__+':'+str(e)[:300]}
def header_evidence(response):
 # http.client itself caps100 lines of<=64KiB; aggregate bounded further before any body read.
 raw=b''.join((k+': '+v+'\r\n').encode('latin-1') for k,v in response.headers.items())
 ev={'status':response.code,'effective_URL':response.geturl(),'parsed_header_bytes':len(raw),'headers_SHA256':hashlib.sha256(raw).hexdigest(),'prefix_hex':raw[:HEADERS].hex(),'prefix_only':len(raw)>HEADERS}
 return raw,ev
def validate_response(response,rawheaders):
 if len(rawheaders)>HEADERS:raise ValueError('aggregate_header_bound')
 if response.code!=200 or response.geturl()!=URL:raise ValueError('exact_200_URL_required_no_redirect')
 h=response.headers
 if h.get_all('Content-Length',[])!=[str(SIZE)]:raise ValueError('exact_single_content_length')
 if h.get_all('Content-Encoding',[]) not in [[],['identity']]:raise ValueError('content_encoding')
 if h.get_all('Transfer-Encoding',[]) or h.get_all('Content-Range',[]):raise ValueError('unexpected_transfer_or_range')
def stream(response,target,start,state,check=lambda n:None,progress=lambda state:None):
 state.update(bytes=0,MD5=hashlib.md5(b'').hexdigest(),SHA1=hashlib.sha1(b'').hexdigest(),SHA256=hashlib.sha256(b'').hexdigest())
 ds=[hashlib.md5(),hashlib.sha1(),hashlib.sha256()];next_progress=64*1024**2
 with target.open('xb') as f:
  try:
   while True:
    if clk()-start>=WORK:raise TimeoutError('worker_deadline')
    n=state['bytes'];check(min(CHUNK,SIZE+1-n));b=response.read1(min(CHUNK,SIZE+1-n))
    if not b:break
    if n+len(b)>BODY_CAP:raise ValueError('response_body_bound')
    written=f.write(b)
    if written!=len(b):raise OSError('short_local_write')
    for h in ds:h.update(b)
    state.update(bytes=n+len(b),MD5=ds[0].hexdigest(),SHA1=ds[1].hexdigest(),SHA256=ds[2].hexdigest())
    if state['bytes']>=next_progress:f.flush();progress(dict(state));next_progress=state['bytes']+64*1024**2
    if state['bytes']>SIZE:raise ValueError('publisher_size_exceeded_EOFprobe_retained')
  finally:f.flush();os.fsync(f.fileno())
 if state['bytes']!=SIZE or state['MD5']!=MD5 or state['SHA1']!=SHA1:raise ValueError('publisher_size_or_MD5_SHA1_mismatch')
 return dict(state)
def kill(p):
 if p.poll() is None:
  try:os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 p.wait(timeout=3)
def process_RSS():
 p=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rows=[tuple(map(int,l.split())) for l in p.stdout.splitlines() if len(l.split())==3];owned={os.getpid()}
 while True:
  more=owned|{p for p,q,r in rows if q in owned}
  if more==owned:break
  owned=more
 return sum(r*1024 for p,q,r in rows if p in owned)
def worker(a):
 verify(a.code_pins_sha256,a.profile_sha256);start=float(a.start);ledger=None;state={};partial=OUT/'archive.partial'
 if os.getppid()!=a.supervisor_pid:raise ValueError('supervisor_parent_identity')
 def deadline(s,f):raise TimeoutError('worker_alarm')
 signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,max(.001,WORK-(clk()-start)))
 try:
  L,C,tls=dependencies();ledger=L(ROOT/'charges',C);require_pending(ledger)
  write('preflight.json',{'URL':URL,'publisher_size':SIZE,'publisher_MD5':MD5,'publisher_SHA1':SHA1,'limits':CAPS,'global_reserved':ledger.totals(),'CA_SHA256':tls.CA_SHA256,'CERT_REQUIRED_hostname':True,'no_decompression':True})
  opener=urllib.request.build_opener(tls.NoRedirect(),urllib.request.HTTPSHandler(context=tls.trusted_context()))
  req=urllib.request.Request(URL,headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity'})
  try:response=opener.open(req,timeout=30)
  except urllib.error.HTTPError as e:response=e
  with response:
   raw,ev=header_evidence(response);write('response-headers.json',ev);validate_response(response,raw)
   def check(n):ledger.check_time();check_storage(n,False)
   result=stream(response,partial,start,state,check,lambda s:terminal('progress.json',{'status':'TRANSFER_PREFIX_ONLY_NOT_FINAL','elapsed_seconds':clk()-start,**s}))
  verify(a.code_pins_sha256,a.profile_sha256)
  os.rename(partial,OUT/NAME);fd=os.open(OUT,os.O_RDONLY);os.fsync(fd);os.close(fd)
  cur=ledger.db.execute('update attempts set state=?,actual_bytes=?,body_sha256=? where key=? and state=?',('complete',result['bytes'],result['SHA256'],KEY,'pending'))
  if cur.rowcount!=1:raise ValueError('pending_ledger_completion_lost')
  terminal('worker-result.json',{'status':'COMPLETE_PUBLISHER_VERIFIED_COMPRESSED_XML_ONLY_NO_ADMISSION','URL':URL,'file':NAME,**result,'publisher_checksums_match':True,'elapsed_seconds':clk()-start,'global_reserved':ledger.totals(),'decompressed_bytes':0,'new_admitted_documents':0,'new_admitted_tokens':0})
 except BaseException as e:
  if ledger is not None:settle(ledger)
  n=partial.stat().st_size if partial.exists() else None
  terminal('worker-result.json',{'status':'TERMINAL_PARTIAL_XML_NO_RETRY','error':type(e).__name__+':'+str(e)[:2000],'partial_bytes':n,'complete_recorded_prefix':state,'prefix_hash_covers_entire_partial':n is not None and n==state.get('bytes'),'published_final_exists':(OUT/NAME).exists(),'new_admitted_documents':0});raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  if ledger is not None:ledger.close()
def verify_final_file(path,expected,start):
 ds=[hashlib.md5(),hashlib.sha1(),hashlib.sha256()];n=0;last_observation=-1;peak=0
 with path.open('rb') as f:
  while True:
   if clk()-start>=EXTERNAL-5:raise TimeoutError('supervisor_rehash_external_bound')
   check_storage(check_intake=False)
   if clk()-last_observation>=1:
    peak=max(peak,process_RSS());last_observation=clk();check_storage()
    if peak>RSS:raise ValueError('supervisor_rehash_RSS')
   b=f.read(CHUNK)
   if not b:break
   n+=len(b)
   if n>SIZE:raise ValueError('terminal_size_exceeded')
   for d in ds:d.update(b)
 hs=[d.hexdigest() for d in ds]
 if n!=SIZE or hs!=[MD5,SHA1,expected]:raise ValueError('supervisor_independent_file_hash')
 return {'bytes':n,'MD5':hs[0],'SHA1':hs[1],'SHA256':hs[2],'peak_observed_process_tree_RSS_bytes':peak}
def supervise(a):
 start=clk();verify(a.code_pins_sha256,a.profile_sha256);dependencies()
 if OUT.exists() or ROOT.is_symlink() or any(p.is_symlink() for p in ROOT.rglob('*')):raise ValueError('existing_output_or_intake_symlink')
 if size(ROOT)+OUTPUT_CAP>COMBINED_CAP or shutil.disk_usage(ROOT).free<FREE+OUTPUT_CAP:raise ValueError('combined_intake_or_disk_reserves')
 child=None;peak=0;reason=None;charged=False;old={}
 def stop(s,f):raise RuntimeError('external_signal_'+str(s))
 for s in [signal.SIGTERM,signal.SIGINT,signal.SIGALRM]:old[s]=signal.signal(s,stop)
 signal.setitimer(signal.ITIMER_REAL,EXTERNAL)
 try:
  # One reservation covers all output, terminal slots, exactly one physical request,
  # exact body plus one EOF probe. Closed before filesystem mutation/child launch.
  L,C,T=dependencies();ledger=L(ROOT/'charges',C)
  try:reserve(ledger);charged=True
  finally:ledger.close()
  OUT.mkdir()
  for name,n in SLOTS.items():
   with (OUT/name).open('xb') as f:f.write(b' '*n);f.flush();os.fsync(f.fileno())
  child=subprocess.Popen([sys.executable,str(HERE/'archive.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  write('ownership.json',{'supervisor_pid':os.getpid(),'worker_pid':child.pid,'shared_start':start,'code_pins_sha256':a.code_pins_sha256,'profile_sha256':a.profile_sha256,'ledger_key':KEY})
  while child.poll() is None:
   if clk()-start>=WORK:reason='worker_time_ceiling';break
   rss=process_RSS();peak=max(peak,rss)
   if rss>RSS:reason='observed_process_tree_RSS';break
   try:check_storage()
   except ValueError as e:reason=str(e);break
   time.sleep(1)
  if reason:kill(child)
  else:child.wait(timeout=3)
  raw=(OUT/'worker-result.json').read_text();r=json.loads(raw) if raw.strip() else {}
  ok=child.returncode==0 and reason is None and r.get('status')=='COMPLETE_PUBLISHER_VERIFIED_COMPRESSED_XML_ONLY_NO_ADMISSION'
  hashes=verify_final_file(OUT/NAME,r['SHA256'],start) if ok else None
  if hashes:peak=max(peak,hashes['peak_observed_process_tree_RSS_bytes'])
  state=cleanup()
  if state.get('state')!='complete' or state.get('actual_bytes')!=SIZE or (ok and state.get('body_sha256')!=hashes['SHA256']):ok=False;reason=reason or 'ledger_terminal_mismatch'
  verify(a.code_pins_sha256,a.profile_sha256)
  terminal('supervisor-result.json',{'status':'COMPLETE_XML_ARCHIVE_ACQUISITION_NO_ADMISSION' if ok else 'PARTIAL_XML_NO_RETRY','reason':reason,'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'independent_final_file_verification':hashes,'owned_ledger':state,'output_bytes':size(OUT),'worker_receipt_SHA256':sha(OUT/'worker-result.json'),'new_admitted_documents':0,'new_admitted_tokens':0})
  return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  state=cleanup() if charged else {'state':'not_allocated'}
  if OUT.exists():
   record={'status':'PARTIAL_XML_NO_RETRY','reason':type(e).__name__+':'+str(e)[:2000],'owned_ledger':state,'elapsed_seconds':clk()-start,'partial_bytes':(OUT/'archive.partial').stat().st_size if (OUT/'archive.partial').exists() else None,'partial_full_hash_unknown_after_forced_death':True,'new_admitted_documents':0}
   if (OUT/'supervisor-result.json').exists():terminal('supervisor-result.json',record)
   else:write('failure-before-slots.json',record)
  raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  for s,h in old.items():signal.signal(s,h)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--supervisor-pid',type=int);p.add_argument('--start');p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True);a=p.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a.code_pins_sha256,a.profile_sha256);dependencies();print('PINNED_FULL_XML_ACQUISITION_PREPARED_NO_NETWORK')
