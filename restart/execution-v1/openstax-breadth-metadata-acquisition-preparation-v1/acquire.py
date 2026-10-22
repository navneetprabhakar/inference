"""Fixed nine metadata responses only. No modules/media/PDF/tree traversal/admission."""
import argparse,hashlib,json,re,os,pathlib,shutil,signal,subprocess,sys,time,ssl,sqlite3,platform,importlib.util,urllib.request,urllib.error,http.client
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake';OUT=ROOT/'openstax-breadth-nine-metadata-v1';PROPOSAL=ROOT/'openstax-breadth-investigation-v1/metadata-only-proposal.json';TLS=ROOT/'gutenberg-preparation-parallel-v4/discover.py';CA=pathlib.Path('/opt/homebrew/etc/ca-certificates/cert.pem')
ITEMS=[{'key': 'us-history-exact-commit', 'url': 'https://api.github.com/repos/openstax/osbooks-us-history/commits/046331cfcea0ac1b1a8fd461b3e6aae638845af3', 'response_body_cap': 65536}, {'key': 'us-history-exact-license', 'url': 'https://raw.githubusercontent.com/openstax/osbooks-us-history/046331cfcea0ac1b1a8fd461b3e6aae638845af3/LICENSE', 'response_body_cap': 32768}, {'key': 'us-history-exact-container', 'url': 'https://raw.githubusercontent.com/openstax/osbooks-us-history/046331cfcea0ac1b1a8fd461b3e6aae638845af3/META-INF/books.xml', 'response_body_cap': 16384}, {'key': 'us-history-exact-collection', 'url': 'https://raw.githubusercontent.com/openstax/osbooks-us-history/046331cfcea0ac1b1a8fd461b3e6aae638845af3/collections/us-history.collection.xml', 'response_body_cap': 131072}, {'key': 'osbooks-writing-guide-license-history-first5', 'url': 'https://api.github.com/repos/openstax/osbooks-writing-guide/commits?path=LICENSE&per_page=5', 'response_body_cap': 131072}, {'key': 'osbooks-introduction-philosophy-license-history-first5', 'url': 'https://api.github.com/repos/openstax/osbooks-introduction-philosophy/commits?path=LICENSE&per_page=5', 'response_body_cap': 131072}, {'key': 'osbooks-introduction-sociology-license-history-first5', 'url': 'https://api.github.com/repos/openstax/osbooks-introduction-sociology/commits?path=LICENSE&per_page=5', 'response_body_cap': 131072}, {'key': 'osbooks-introduction-anthropology-license-history-first5', 'url': 'https://api.github.com/repos/openstax/osbooks-introduction-anthropology/commits?path=LICENSE&per_page=5', 'response_body_cap': 131072}, {'key': 'osbooks-business-ethics-license-history-first5', 'url': 'https://api.github.com/repos/openstax/osbooks-business-ethics/commits?path=LICENSE&per_page=5', 'response_body_cap': 131072}]
CAPS={'requests':9,'sum_response_caps':901120,'conservative_EOF_probe_reservation_bytes':901129,'output_bytes':8000000,'external_seconds':120,'worker_seconds':110,'minimum_start_spacing_seconds':1,'serial_only':True,'attempts_each':1,'redirects':False,'retries':0,'book_module_media_or_PDF_bodies':0}
KEY='openstax-breadth-nine-metadata-v1-output';REQUEST_KEYS=[KEY+'-request-'+r['key'] for r in ITEMS];OWNED_KEYS=[KEY]+REQUEST_KEYS;FREE=53474836480;SLOTS={'supervisor-result.json':32768,'worker-result.json':65536};RESERVE=131072
class ProfileDeadline(RuntimeError):pass
class RequestFailure(ValueError):pass
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(65536),b''):h.update(b)
 return h.hexdigest()
def size(p):return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
def runtime():return {'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'platform':platform.platform(),'OpenSSL':ssl.OPENSSL_VERSION,'sqlite':sqlite3.sqlite_version}
def inventory():
 paths=[HERE/n for n in ['acquire.py','checks.py','code_guard.py','profile.json']]+[PROPOSAL,PROPOSAL.parent/'investigation.json',PROPOSAL.parent/'manifest.json',BASE/'acquire_sources.py',BASE/'authorization.json',BASE/'source-acquisition-authorization.json',BASE/'disk-budget.json',REPO/'src/slm/data/intake_ledger.py',REPO/'src/slm/data/schema.py',TLS,CA,pathlib.Path(sys.executable)]
 for m in [ssl,sqlite3,hashlib,json,subprocess,signal,urllib.request,urllib.error,http.client]:
  if getattr(m,'__file__',None):paths.append(pathlib.Path(m.__file__))
 return {str(p.resolve()) for p in paths}
def verify(code,profile):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=profile:raise ValueError('external_profile_digest')
 p=json.loads((HERE/'profile.json').read_text());q=json.loads(PROPOSAL.read_text())
 if p['limits']!=CAPS or p['items']!=ITEMS or q['items']!=ITEMS or q['limits']!=CAPS or p['output']!=str(OUT) or p['proposal_SHA256']!=sha(PROPOSAL):raise ValueError('fixed_exact_nine_metadata_scope')
 if len(ITEMS)!=9 or sum(r['response_body_cap'] for r in ITEMS)!=901120 or len(set(r['url'] for r in ITEMS))!=9:raise ValueError('nine_unique_bounded_requests')
 return p
def helpers():
 sys.path[:0]=[str(BASE),str(REPO/'src')]
 import acquire_sources
 from slm.data import intake_ledger
 if pathlib.Path(acquire_sources.__file__).resolve()!=BASE/'acquire_sources.py' or pathlib.Path(intake_ledger.__file__).resolve()!=REPO/'src/slm/data/intake_ledger.py':raise ValueError('ledger_import_origin')
 spec=importlib.util.spec_from_file_location('pinned_metadata_TLS',TLS);tls=importlib.util.module_from_spec(spec);spec.loader.exec_module(tls);tls.trusted_context()
 return acquire_sources.IntakeLedger,acquire_sources.CONTRACT,tls
def disk(additional=0,preflight=False):
 if additional<0 or size(OUT)+additional>(CAPS['output_bytes'] if preflight else CAPS['output_bytes']-RESERVE) or size(ROOT)+additional>64000000000 or shutil.disk_usage(ROOT).free<FREE+additional:raise ValueError('output_intake_weights_scratch_freefloor')
def save(name,obj):
 b=obj if isinstance(obj,bytes) else (json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode();disk(len(b))
 with (OUT/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def terminal(name,obj):
 b=(json.dumps(obj,indent=2)+'\n').encode();n=SLOTS[name]
 if len(b)>n:raise ValueError('fixed_terminal_slot')
 with (OUT/name).open('r+b') as f:f.write(b+b' '*(n-len(b)));f.flush();os.fsync(f.fileno())
def guard(start):
 if clk()-start>=110:raise ProfileDeadline('worker110_seconds')
 disk();
def settle(ledger):
 changed=[]
 for key in OWNED_KEYS:
  row=ledger.db.execute('select state from attempts where key=?',(key,)).fetchone()
  if row==('pending',):ledger.finish(key,raw=None);changed.append(key)
 states={key:row[0] for key in OWNED_KEYS if (row:=ledger.db.execute('select state from attempts where key=?',(key,)).fetchone())}
 return {'states':states,'settled_failed_no_refund':changed,'pending_owned':sum(v=='pending' for v in states.values())}
def cleanup():
 try:
  L,C,T=helpers();ledger=L(ROOT/'charges',C)
  try:return settle(ledger)
  finally:ledger.close()
 except BaseException as e:return {'cleanup_hold':type(e).__name__+':'+str(e)[:300]}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k):return None
def attempt(item,ledger,opener,state,start):
 guard(start)
 if state['requests']>=9:raise ValueError('request_cap')
 if state['last_start'] is not None:
  delay=max(0,1-(clk()-state['last_start']))
  if delay:time.sleep(delay)
 guard(start);key=KEY+'-request-'+item['key'];cap=item['response_body_cap'];ledger.reserve(key,requests=1,body_bytes=cap+1,output_bytes=0)
 rec={'key':key,'URL':item['url'],'response_body_cap':cap,'EOF_probe_reserved':1,'physical_open_entered':False,'received_body_bytes':0,'status':'FAILED_METADATA_ATTEMPT_NO_RETRY','new_admitted_documents':0};partial=OUT/(item['key']+'.partial-metadata');raw=bytearray();fatal=None
 try:
  before=clk()
  if state['last_start'] is not None and before-state['last_start']<1:raise ValueError('serial_start_spacing')
  state['last_start']=before;state['requests']+=1;rec.update(physical_open_entered=True,physical_start_monotonic=before)
  req=urllib.request.Request(item['url'],headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity'})
  try:response=opener.open(req,timeout=30)
  except urllib.error.HTTPError as e:response=e
  with response:
   headers=b''.join((k+': '+v+'\r\n').encode('latin1') for k,v in response.headers.items());ev={'status':response.code,'effective_URL':response.geturl(),'header_bytes':len(headers),'header_SHA256':hashlib.sha256(headers).hexdigest(),'prefix_hex':headers[:65536].hex(),'prefix_only':len(headers)>65536}
   save(item['key']+'.headers.json',ev);rec['header_receipt']=item['key']+'.headers.json'
   if len(headers)>65536 or response.code!=200 or response.geturl()!=item['url']:raise RequestFailure('bounded_headers_exact200_URL_no_redirect')
   ce=response.headers.get_all('Content-Encoding',[]);length=response.headers.get_all('Content-Length',[])
   if ce not in [[],['identity']] or len(length)>1 or (length and (not length[0].isascii() or not length[0].isdecimal() or int(length[0])>cap)):raise RequestFailure('identity_encoding_or_content_length_cap')
   with partial.open('xb') as f:
    try:
     while True:
      guard(start);ledger.check_time();n=min(65536,cap+1-len(raw))
      if n<=0:raise RequestFailure('body_cap_plus_probe_exceeded')
      disk(n);chunk=response.read1(n)
      if not chunk:break
      if len(chunk)>n:raise RequestFailure('response_read_overrequest')
      raw.extend(chunk);state['body_bytes']+=len(chunk);rec['received_body_bytes']=len(raw)
      if f.write(chunk)!=len(chunk):raise OSError('short_metadata_write')
      if len(raw)>cap or state['body_bytes']>901129:raise RequestFailure('metadata_body_cap_probe_retained')
    finally:f.flush();os.fsync(f.fileno())
   if length and len(raw)!=int(length[0]):raise RequestFailure('advertised_length_mismatch')
  ledger.finish(key,raw=bytes(raw));final=OUT/(item['key']+'.metadata');os.rename(partial,final);rec.update(status='COMPLETE_BOUNDED_METADATA_RESPONSE_NOT_LICENSE_CLEARANCE',file=final.name,SHA256=hashlib.sha256(raw).hexdigest())
 except BaseException as e:
  if ledger.db.execute('select state from attempts where key=?',(key,)).fetchone()==('pending',):ledger.finish(key,raw=None)
  rec['error']=type(e).__name__+':'+str(e)[:1200]
  if partial.exists():rec.update(file=partial.name,SHA256=sha(partial),retained_partial_bytes=partial.stat().st_size)
  if not isinstance(e,(RequestFailure,urllib.error.URLError,TimeoutError)):fatal=e
  if clk()-start>=110:fatal=e
 finally:
  state['current_attempt']=rec
 if fatal is not None:raise fatal
 save(item['key']+'.receipt.json',rec);return rec

def worker(a):
 start=float(a.start);ledger=None;records=[];state={'requests':0,'body_bytes':0,'last_start':None,'current_attempt':None};old={}
 def stop(s,f):raise ProfileDeadline('worker_deadline_or_signal')
 try:
  for s in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[s]=signal.signal(s,stop)
  remaining=110-(clk()-start)
  if remaining<=0:raise ProfileDeadline('expired_before_worker_preflight')
  signal.setitimer(signal.ITIMER_REAL,remaining);verify(a.code_pins_sha256,a.profile_sha256)
  if os.getppid()!=a.supervisor_pid:raise ValueError('live_owned_parent_required')
  L,C,T=helpers();ledger=L(ROOT/'charges',C)
  row=ledger.db.execute('select charge,state from attempts where key=?',(KEY,)).fetchone()
  if row is None or row[1]!='pending' or json.loads(row[0])!={'requests':0,'body_bytes':0,'rows':0,'output_bytes':8000000}:raise ValueError('exact_output_precharge_required')
  opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=T.trusted_context()))
  save('preflight.json',{'proposal_SHA256':sha(PROPOSAL),'strict_TLS_CERT_REQUIRED_hostname':True,'CA_SHA256':T.CA_SHA256,'limits':CAPS,'no_license_clearance':True,'no_module_media_PDF_fetch':True})
  for item in ITEMS:records.append(attempt(item,ledger,opener,state,start))
  guard(start);verify(a.code_pins_sha256,a.profile_sha256);ledger.finish(KEY,raw=b'')
  terminal('worker-result.json',{'status':'FINITE_NINE_METADATA_ATTEMPTS_TERMINAL_NO_ADMISSION','records':records,'physical_requests':state['requests'],'actual_response_body_bytes':state['body_bytes'],'successes':sum(r['status'].startswith('COMPLETE') for r in records),'failed':sum(not r['status'].startswith('COMPLETE') for r in records),'elapsed_seconds':clk()-start,'global_reserved':ledger.totals(),'new_admitted_documents':0,'new_admitted_tokens':0})
 except BaseException as e:
  signal.setitimer(signal.ITIMER_REAL,0)
  settled=settle(ledger) if ledger is not None else {'not_opened':True}
  terminal('worker-result.json',{'status':'PARTIAL_METADATA_PROFILE_NO_RETRY','error':type(e).__name__+':'+str(e)[:1200],'completed_records':len(records),'physical_requests':state['requests'],'actual_response_body_bytes':state['body_bytes'],'last_attempt':state['current_attempt'],'owned_settlement':settled,'new_admitted_documents':0});raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  if ledger is not None:ledger.close()
  for s,h in old.items():signal.signal(s,h)

def process_tree_rss(snapshot,root,required_worker=None):
 if not isinstance(snapshot,str) or len(snapshot)>1048576:raise ValueError('invalid_or_unbounded_RSS_snapshot')
 rows={}
 for line in snapshot.splitlines():
  if not line.strip():continue
  fields=line.split()
  if len(fields)!=3 or any(re.fullmatch('[0-9]+',v) is None for v in fields):raise ValueError('malformed_RSS_snapshot')
  pid,ppid,rss=map(int,fields)
  if pid<=0 or pid==ppid or pid in rows:raise ValueError('invalid_duplicate_or_selfparent_RSS_PID')
  rows[pid]=(ppid,rss)
 if root not in rows or rows[root][1]<=0:raise ValueError('missing_or_zero_root_RSS')
 owned={root}
 while True:
  n=owned|{p for p,(q,r) in rows.items() if q in owned}
  if n==owned:break
  owned=n
 if required_worker is not None and (required_worker not in owned or rows[required_worker][1]<=0):raise ValueError('missing_unowned_or_zero_live_worker_RSS')
 return sum(rows[p][1]*1024 for p in owned)
def kill(child):
 if child.poll() is None:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 child.wait(timeout=3)
def supervise(a):
 start=clk();child=None;created=False;charged=False;peak=0;old={}
 def stop(s,f):raise ProfileDeadline('external120_seconds_or_signal')
 try:
  for s in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[s]=signal.signal(s,stop)
  signal.setitimer(signal.ITIMER_REAL,120-(clk()-start));verify(a.code_pins_sha256,a.profile_sha256);L,C,T=helpers()
  if OUT.exists() or OUT.is_symlink() or ROOT.is_symlink():raise ValueError('once_only_output_or_root_symlink')
  policy=json.loads((BASE/'disk-budget.json').read_text())
  if any(policy[k]!=v for k,v in [('raw_download_cap_bytes',80000000000),('processed_data_cap_bytes',64000000000),('weights_checkpoints_reserved_bytes',16000000000),('scratch_cap_bytes',16000000000),('free_disk_floor_bytes',21474836480)]):raise ValueError('storage_policy_drift')
  disk(8000000,preflight=True)
  # Global existing IntakLedger takes LOCK_EX|LOCK_NB. Busywriter refuses BEFORE output or GET.
  ledger=L(ROOT/'charges',C)
  try:ledger.reserve(KEY,requests=0,body_bytes=0,output_bytes=8000000);charged=True
  finally:ledger.close()
  OUT.mkdir();created=True
  for name,n in SLOTS.items():
   with (OUT/name).open('xb') as f:f.write(b' '*n);f.flush();os.fsync(f.fileno())
  child=subprocess.Popen([sys.executable,str(HERE/'acquire.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  save('ownership.json',{'supervisor_pid':os.getpid(),'worker_pid':child.pid,'shared_start':start,'code_pins_sha256':a.code_pins_sha256,'profile_sha256':a.profile_sha256,'exact_owned_keys':OWNED_KEYS})
  while child.poll() is None:
   if clk()-start>=110:raise ProfileDeadline('shared_worker110_seconds')
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
   rss=process_tree_rss(ps.stdout,os.getpid(),child.pid if child.poll() is None else None);peak=max(peak,rss)
   if rss>1000000000:raise ValueError('RSS1GB')
   disk();time.sleep(.1)
  child.wait(timeout=3);w=json.loads((OUT/'worker-result.json').read_text());ok=child.returncode==0 and w.get('status')=='FINITE_NINE_METADATA_ATTEMPTS_TERMINAL_NO_ADMISSION' and w.get('physical_requests')==9 and len(w.get('records',[]))==9 and w.get('actual_response_body_bytes',901130)<=901129
  if ok:
   if [r['key'] for r in w['records']]!=REQUEST_KEYS:raise ValueError('exact_nine_attempt_order')
   for item,r in zip(ITEMS,w['records']):
    if r['URL']!=item['url'] or r['received_body_bytes']>item['response_body_cap']+1:raise ValueError('terminal_response_scope')
    if 'file' in r and sha(OUT/r['file'])!=r['SHA256']:raise ValueError('independent_metadata_file_hash')
  settled=cleanup()
  if settled.get('cleanup_hold') or settled.get('pending_owned')!=0 or (ok and (set(settled['states'])!=set(OWNED_KEYS) or settled['states'].get(KEY)!='complete')):ok=False
  verify(a.code_pins_sha256,a.profile_sha256)
  if clk()-start>=120:raise ProfileDeadline('elapsed_before_supervisor_complete')
  terminal('supervisor-result.json',{'status':'FINITE_METADATA_PROFILE_TERMINAL_NO_ADMISSION' if ok else 'PARTIAL_METADATA_PROFILE_NO_RETRY','worker_exit_code':child.returncode,'worker_receipt_SHA256':sha(OUT/'worker-result.json'),'owned_ledger':settled,'peak_observed_process_tree_RSS_bytes':peak,'elapsed_seconds':clk()-start,'output_bytes':size(OUT),'new_admitted_documents':0,'new_admitted_tokens':0});return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  settled=cleanup() if charged else {'not_allocated':True}
  if created:
   rec={'status':'PARTIAL_METADATA_PROFILE_NO_RETRY','error':type(e).__name__+':'+str(e)[:1200],'child_reaped':child is None or child.poll() is not None,'owned_ledger':settled,'new_admitted_documents':0}
   if (OUT/'supervisor-result.json').exists():terminal('supervisor-result.json',rec)
   else:save('failure-before-slots.json',rec)
  raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  for s,h in old.items():signal.signal(s,h)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--supervisor-pid',type=int);p.add_argument('--start');p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True);a=p.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a.code_pins_sha256,a.profile_sha256);helpers();print('PREPARED_FIXED9_METADATA_NO_NETWORK_OR_GLOBAL_LEDGER_WRITES')
