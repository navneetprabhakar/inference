"""Bounded exact selected native XML block acquisition, not article extraction."""
import argparse,hashlib,importlib.util,json,os,pathlib,shutil,signal,subprocess,sys,time,urllib.request,urllib.error
import range_core as core
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake';OUT=ROOT/'enwiki-native-20row-ranges-20260801-v2'
FREE=53474836480;OUTPUT_CAP=core.LIMITS['output_bytes'];SLOTS={'worker-result.json':65536,'supervisor-result.json':32768}
OUTPUT_KEY='enwiki-native-row20-range-profile-output-v2-once'
INDEX_CODE=BASE/'enwiki-native-index-acquisition-preparation-v1/index.py'
spec=importlib.util.spec_from_file_location('reviewed_index_download',INDEX_CODE);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
# Reuse exact reviewed storage/terminal/TLS/ledger/process helpers; no index fetch.
old.OUT=OUT;old.OUTPUT_CAP=OUTPUT_CAP
clk=old.clk;sha=old.sha;size=old.size;write=old.write;terminal=old.terminal;kill=old.kill;dependencies=old.dependencies
ASSESS=ROOT/'enwiki-native-index-assessment-v1';OPTIONS=ROOT/'enwiki-native-html-option-v1/acquisition-options.json'
def inventory():
 return {str(p.resolve()) for p in [HERE/n for n in ['ranges.py','range_core.py','checks.py','code_guard.py','profile.json','selection-freeze.json']]+[INDEX_CODE,ASSESS/'selection.json',ASSESS/'result.json',ASSESS/'supervisor.json',BASE/'enwiki-native-index-assessment-preparation-v1/profile.json',BASE/'enwiki-native-index-assessment-parent-dispatch-v1/review.json',BASE/'acquire_sources.py',REPO/'src/slm/data/intake_ledger.py',REPO/'src/slm/data/schema.py',BASE/'disk-budget.json',BASE/'authorization.json',BASE/'source-acquisition-authorization.json',ROOT/'gutenberg-preparation-parallel-v4/discover.py',pathlib.Path('/opt/homebrew/etc/ca-certificates/cert.pem'),OPTIONS,ROOT/'native-supply-investigation-v1/enwiki-dumpstatus.json',ROOT/'native-supply-investigation-v1/metadata-retrieval-receipts.json']}
def verify(code,prof):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=prof:raise ValueError('external_profile_pin')
 p=json.loads((HERE/'profile.json').read_text());plan=json.loads((HERE/'selection-freeze.json').read_text());selection=json.loads((ASSESS/'selection.json').read_text());result=json.loads((ASSESS/'result.json').read_text());supervisor=json.loads((ASSESS/'supervisor.json').read_text())
 if p['limits']!=core.LIMITS or p['publisher_XML_bytes']!=core.XML_BYTES or p['URL']!=core.URL:raise ValueError('fixed_caps_URL')
 allocation=p['output_allocation']
 if allocation['key']!=OUTPUT_KEY or allocation['requests']!=0 or allocation['body_bytes']!=0 or allocation['output_bytes']!=OUTPUT_CAP:raise ValueError('fixed_output_allocation')
 if result['status']!='COMPLETE_ONE_PASS_INDEX_ASSESSMENT_ROW_SAMPLE_NO_ADMISSION' or supervisor['status']!='COMPLETE_NATIVE_INDEX_ROWS_ONLY_NO_ADMISSION' or supervisor['worker_exit_code']!=0 or supervisor['result_sha256']!=sha(ASSESS/'result.json') or result['selection_sha256']!=sha(ASSESS/'selection.json'):raise ValueError('complete_index_receipt_chain')
 if not result['all_BZ2_EOF_CRC_verified'] or not result['source_index_unchanged'] or result['source_SHA256']!=selection['source_SHA256'] or not result['publisher_MD5_match'] or not result['publisher_SHA1_match']:raise ValueError('index_integrity_evidence')
 if core.freeze(selection)!=plan:raise ValueError('exact20_frozen_range_plan')
 options=json.loads(OPTIONS.read_text());entries=[f for f in options['native_XML_option']['files'] if f['absolute_URL']==core.URL]
 if len(entries)!=1 or entries[0]['size']!=core.XML_BYTES:raise ValueError('observed_publisher_XML_URL_size')
 if sha(pathlib.Path(options['native_XML_option']['cached_metadata_file']))!=options['native_XML_option']['cached_metadata_SHA256'] or sha(pathlib.Path(options['native_XML_option']['metadata_retrieval_receipt_file']))!=options['native_XML_option']['metadata_retrieval_receipt_SHA256']:raise ValueError('retained_publisher_metadata_binding')
 return plan

def key(block):return 'enwiki-native-row20-range-v1-'+str(block['start'])+'-'+str(block['end_exclusive'])
def check(start,ledger,additional=0):
 if clk()-start>=570:raise TimeoutError('worker_deadline')
 ledger.check_time()
 if size(OUT)+additional>OUTPUT_CAP-1048576:raise ValueError('aggregate_output_prewrite_cap')
 if shutil.disk_usage(ROOT).free<FREE+additional:raise ValueError('protected_weights_scratch_floor')
def reserve_output(ledger):
 ledger.reserve(OUTPUT_KEY,requests=0,body_bytes=0,rows=0,output_bytes=OUTPUT_CAP)
def require_pending_output(ledger):
 row=ledger.db.execute('select charge,state from attempts where key=?',(OUTPUT_KEY,)).fetchone()
 expected={'requests':0,'body_bytes':0,'rows':0,'output_bytes':OUTPUT_CAP}
 if row is None or row[1]!='pending' or json.loads(row[0])!=expected:raise ValueError('exact_pending_supervisor_output_allocation_required')
def supervisor_reserve_output():
 L,C,T=dependencies();ledger=L(ROOT/'charges',C)
 try:reserve_output(ledger)
 finally:ledger.close()
def settle_output(ledger,success):
 row=ledger.db.execute('select state from attempts where key=?',(OUTPUT_KEY,)).fetchone()
 if row==('pending',):ledger.finish(OUTPUT_KEY,raw=b'' if success else None)
def cleanup_ledger():
 try:
  L,C,T=dependencies();ledger=L(ROOT/'charges',C)
  try:
   plan=json.loads((HERE/'selection-freeze.json').read_text());states=[]
   for k in [OUTPUT_KEY]+[key(b) for b in plan['distinct_ranges']]:
    state=ledger.db.execute('select state from attempts where key=?',(k,)).fetchone()
    if state==('pending',):ledger.finish(k,raw=None);state=('failed',)
    if state:states.append({'key':k,'state':state[0]})
   return states
  finally:ledger.close()
 except BaseException as e:return {'cleanup_hold':type(e).__name__+':'+str(e)[:300]}
def worker(a):
 plan=verify(a.code_pins_sha256,a.profile_sha256);start=float(a.start);ledger=None;active=None;completed=[];last_request=None
 if os.getppid()!=a.supervisor_pid:raise ValueError('parent_identity')
 try:
  Ledger,contract,tls=dependencies();ledger=Ledger(ROOT/'charges',contract)
  require_pending_output(ledger)
  write('all20-selection-and-holds.json',plan)
  write('preflight.json',{'plan_SHA256':sha(HERE/'selection-freeze.json'),'limits':core.LIMITS,'global_reserved_before':ledger.totals(),'protected_free_bytes':FREE,'publisher_full_XML_checksums_verified':False})
  opener=urllib.request.build_opener(tls.NoRedirect(),urllib.request.HTTPSHandler(context=tls.trusted_context()))
  for i,b in enumerate(plan['distinct_ranges']):
   if b['status']=='HELD_OVERSIZE_NO_REPLACEMENT':continue
   check(start,ledger)
   if last_request is not None:
    while clk()-last_request<1:check(start,ledger);time.sleep(max(0,min(.05,1-(clk()-last_request))))
   active=key(b);ledger.reserve(active,requests=1,body_bytes=b['reservation_bytes'],output_bytes=b['reservation_bytes']+10000)
   request={'key':active,'URL':core.URL,'Range':b['Range'],'reservation_bytes':b['reservation_bytes'],'charged_before_IO':True,'redirects':False,'retries':False,'selected_row_ordinals':b['selected_row_ordinals'],'request_start_monotonic':clk()}
   write(f'range-{i:02d}-request.json',request)
   req=urllib.request.Request(core.URL,headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity','Range':b['Range']})
   last_request=clk()
   try:response=opener.open(req,timeout=min(30,570-(clk()-start)))
   except urllib.error.HTTPError as e:response=e
   partial=OUT/f'range-{i:02d}.bz2.partial'
   with response:
    write(f'range-{i:02d}-headers.json',{'status':response.code,'URL':response.geturl(),'headers':list(response.headers.items()),'request_open_monotonic':last_request})
    core.validate_response(response,b)
    n,h=core.stream(response,partial,b,lambda additional=0:check(start,ledger,additional))
   raw=partial.read_bytes()
   if len(raw)!=n or hashlib.sha256(raw).hexdigest()!=h:raise ValueError('local_range_hash_changed')
   ledger.finish(active,raw=raw);del raw
   final=OUT/f'range-{i:02d}.bz2';os.rename(partial,final)
   receipt={'key':active,'URL':core.URL,'Range':b['Range'],'bytes':n,'local_SHA256':h,'selected_row_ordinals':b['selected_row_ordinals'],'strict_TLS_CERT_REQUIRED_hostname':True,'CA_bundle_SHA256':tls.CA_SHA256,'publisher_XML_checksum_verified':False,'BZ2_CRC_or_EOF_verified':False,'XML_parsed':False,'redirects':False,'retries':False,'file':final.name}
   write(f'range-{i:02d}-receipt.json',receipt);completed.append(receipt);active=None
  verify(a.code_pins_sha256,a.profile_sha256)
  terminal('worker-result.json',{'status':'COMPLETE_BOUNDED_NATIVE_RANGE_DISCOVERY_NO_ADMISSION','completed_ranges':completed,'selected_rows':20,'distinct_ranges':len(plan['distinct_ranges']),'oversize_held_ranges':sum(b['status']=='HELD_OVERSIZE_NO_REPLACEMENT' for b in plan['distinct_ranges']),'reserved_body_bytes':plan['reserved_body_bytes'],'elapsed_seconds':clk()-start,'global_reserved':ledger.totals(),'publisher_XML_checksum_verified':False,'new_admitted_documents':0,'new_admitted_tokens':0,'XML_parser_created':False,'profile_output_allocation_key':OUTPUT_KEY,'profile_output_reserved_bytes':OUTPUT_CAP})
  settle_output(ledger,True)
 except BaseException as e:
  if ledger is not None:settle_output(ledger,False)
  if ledger is not None and active and ledger.db.execute('select state from attempts where key=?',(active,)).fetchone()==('pending',):ledger.finish(active,raw=None)
  terminal('worker-result.json',{'status':'TERMINAL_PARTIAL_NATIVE_RANGES_NO_RETRY','error':type(e).__name__+':'+str(e)[:2000],'active_key':active,'completed_ranges':completed,'partial_files':[{ 'file':p.name,'bytes':p.stat().st_size,'SHA256':sha(p)} for p in OUT.glob('*.partial')],'new_admitted_documents':0,'new_admitted_tokens':0});raise
 finally:
  if ledger is not None:ledger.close()

def supervise(a):
 start=clk();verify(a.code_pins_sha256,a.profile_sha256)
 if OUT.exists() or ROOT.is_symlink() or any(p.is_symlink() for p in ROOT.rglob('*')):raise ValueError('existing_output_or_intake_symlink')
 if size(ROOT)+OUTPUT_CAP>64000000000 or shutil.disk_usage(ROOT).free<FREE+OUTPUT_CAP:raise ValueError('combined_intake_or_disk_reserves')
 OUT.mkdir()
 child=None;peak=0;reason=None;output_charged=False
 def stop(s,f):raise RuntimeError('external_signal_'+str(s))
 old={s:signal.signal(s,stop) for s in [signal.SIGTERM,signal.SIGINT]}
 try:
  supervisor_reserve_output();output_charged=True
  for name,n in SLOTS.items():
   with (OUT/name).open('xb') as f:f.write(b' '*n);f.flush();os.fsync(f.fileno())
  child=subprocess.Popen([sys.executable,str(HERE/'ranges.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
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
  raw=(OUT/'worker-result.json').read_text();r=json.loads(raw) if raw.strip() else {};ok=child.returncode==0 and reason is None and r.get('status')=='COMPLETE_BOUNDED_NATIVE_RANGE_DISCOVERY_NO_ADMISSION' and clk()-start<600
  if ok and any(sha(OUT/b['file'])!=b['local_SHA256'] or (OUT/b['file']).stat().st_size!=b['bytes'] for b in r['completed_ranges']):ok=False;reason='terminal_range_rehash_mismatch'
  ledger_state=cleanup_ledger()
  if not isinstance(ledger_state,list) or not any(x['key']==OUTPUT_KEY and x['state']=='complete' for x in ledger_state):ok=False;reason=reason or 'output_allocation_not_complete'
  terminal('supervisor-result.json',{'status':'COMPLETE_NATIVE_RANGE_DISCOVERY_NO_ADMISSION' if ok else 'PARTIAL_NATIVE_RANGES_NO_RETRY','reason':reason,'owned_ledger_terminal_state':ledger_state,'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'output_bytes':size(OUT),'worker_receipt_sha256':sha(OUT/'worker-result.json'),'new_admitted_documents':0,'new_admitted_tokens':0});return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  ledger_state=cleanup_ledger()
  if output_charged:
   receipt={'status':'PARTIAL_NATIVE_RANGES_NO_RETRY','reason':type(e).__name__+':'+str(e)[:2000],'owned_ledger_terminal_state':ledger_state,'elapsed_seconds':clk()-start,'new_admitted_documents':0}
   if (OUT/'supervisor-result.json').exists():terminal('supervisor-result.json',receipt)
   else:write('supervisor-result.json',receipt)
  raise
 finally:
  for s,h in old.items():signal.signal(s,h)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--supervisor-pid',type=int);p.add_argument('--start');p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True);a=p.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a.code_pins_sha256,a.profile_sha256);print('PINNED_RANGES_PREPARED_NO_NETWORK')
