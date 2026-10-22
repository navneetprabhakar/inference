"""One proposed65-range tail: coordinator-only ledger, atmost2requests, no retries/copy."""
import argparse,concurrent.futures,hashlib,http.client,importlib.util,json,os,pathlib,platform,shutil,signal,sqlite3,ssl,subprocess,sys,threading,time,urllib.request
import transport_core as core
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake';OUT=ROOT/'enwiki-native-segmented-tail-20260801-v1'
PRIOR=ROOT/'enwiki-native-full-XML-20260801-v3';PREFIX=PRIOR/'assembled.partial';SIZE=26668484995;PREFIX_SIZE=17988844772;REMAIN=SIZE-PREFIX_SIZE
URL='https://dumps.wikimedia.org/enwiki/20260801/enwiki-20260801-pages-articles-multistream.xml.bz2';ETAG='"6a738a16-63590c983"';MD5='b6c5a530175db4f5a46cc1439cdac27d';SHA1='dd27f408e60d3bc864d42547fb0a0d7408249c13';PREFIX_SHA='28c687b269c4e46e28c1068d7cd7c9579fbb3f03a73c3924bb014f081e58c00b'
ORIGINAL_DEADLINE=2903237.67775;WORK=7140;EXTERNAL=7200;OUTPUT=9000000000;COMBINED=64000000000;FREE=53474836480;RSS=1000000000;WIDTH=134217728
KEY='enwiki-native-segmented-tail-20260801-v1';SLOTS={'worker-result.json':65536,'supervisor-result.json':65536,'progress.json':16384}
TLS=ROOT/'gutenberg-preparation-parallel-v4/discover.py';CA=pathlib.Path('/opt/homebrew/etc/ca-certificates/cert.pem');OPTIONS=ROOT/'enwiki-native-html-option-v1/acquisition-options.json'
CAPS={'part_bytes':WIDTH,'parts':65,'body_reserved':8679640288,'output_bytes':OUTPUT,'combined_local_intake_bytes':COMBINED,'global_output_ledger_bytes':80000000000,'worker_seconds':WORK,'external_seconds':EXTERNAL,'tree_RSS_bytes':RSS,'max_concurrent_requests':2,'minimum_start_gap_seconds':1,'header_bytes':65536,'socket_stall_seconds':30,'retries':0,'redirects':0,'decompressed_bytes':0}
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def size(root):return sum(p.stat().st_size for p in pathlib.Path(root).rglob('*') if p.is_file())
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def deps():
 sys.path[:0]=[str(REPO/'src'),str(BASE)]
 import acquire_sources
 from slm.data import intake_ledger
 if pathlib.Path(acquire_sources.__file__).resolve()!=BASE/'acquire_sources.py' or pathlib.Path(intake_ledger.__file__).resolve()!=REPO/'src/slm/data/intake_ledger.py':raise ValueError('ledger_import_origin')
 tls=load('segmented_pinned_TLS',TLS);tls.trusted_context();return acquire_sources.IntakeLedger,acquire_sources.CONTRACT,tls

def runtime():
 import _ssl,_hashlib,_sqlite3
 return {'python':sys.version,'launcher':sys.executable,'binary':str(pathlib.Path(sys.executable).resolve()),'platform':platform.platform(),'openssl':ssl.OPENSSL_VERSION,'SQLite':sqlite3.sqlite_version,'native_origins':{m.__name__:m.__spec__.origin for m in [_ssl,_hashlib,_sqlite3]}}
def inventory():
 import concurrent.futures.thread,queue,_ssl,_hashlib,_sqlite3
 paths=[HERE/n for n in ['segmented.py','transport_core.py','checks.py','profile.json','primary-evidence.json','runtime.json']]+[BASE/'acquire_sources.py',REPO/'src/slm/data/intake_ledger.py',REPO/'src/slm/data/schema.py',BASE/'disk-budget.json',BASE/'authorization.json',BASE/'source-acquisition-authorization.json',TLS,CA,OPTIONS,ROOT/'native-supply-investigation-v1/enwiki-dumpstatus.json',ROOT/'native-supply-investigation-v1/metadata-retrieval-receipts.json',BASE/'enwiki-native-full-acquisition-preparation-v3/profile.json',BASE/'enwiki-native-full-acquisition-preparation-v3/code-pins.json',BASE/'enwiki-recovery-v3-terminal-independent-verification-v1/verification.json',BASE/'wikibooks-current20-native-source-capture-preparation-v2/supervisor_core.py']+[PRIOR/n for n in ['worker-result.json','supervisor-result.json','ownership.json','response-headers.json','prefix-copy.json']]
 for m in [argparse,concurrent.futures,hashlib,http.client,json,os,pathlib,platform,shutil,signal,sqlite3,sqlite3.dbapi2,ssl,subprocess,threading,time,urllib.request]:
  if getattr(m,'__file__',None):paths.append(pathlib.Path(m.__file__))
 paths += [pathlib.Path(m.__file__) for m in [concurrent.futures.thread,queue,_ssl,_hashlib,_sqlite3] if getattr(m,"__file__",None)]+[pathlib.Path(sys.executable).resolve()]
 return {str(p.resolve()) for p in paths}
def prefix_metadata(p):
 w=json.loads((PRIOR/'worker-result.json').read_text());s=json.loads((PRIOR/'supervisor-result.json').read_text());o=json.loads((PRIOR/'ownership.json').read_text());head=json.loads((PRIOR/'response-headers.json').read_text())
 if w['status']!='TERMINAL_PARTIAL_XML_NO_RETRY' or not w['prefix_hash_covers_entire_partial'] or w['partial_bytes']!=PREFIX_SIZE or w['complete_recorded_prefix']['SHA256']!=PREFIX_SHA or s['worker_exit_code']!=1 or s['owned_ledger']['state']!='failed':raise ValueError('terminal_failed_v3_prefix_binding')
 if sha(PRIOR/'worker-result.json')!=s['worker_receipt_SHA256'] or PREFIX.is_symlink() or core.stat_id(PREFIX)!=p['prefix']['stat']:raise ValueError('prefix_receipt_stat')
 for k in ['supervisor_pid','worker_pid']:
  try:os.kill(o[k],0)
  except ProcessLookupError:pass
  else:raise ValueError('prior_PID_still_present')
 raw=bytes.fromhex(head['prefix_hex'])
 if head['status']!=206 or head['effective_URL']!=URL or head['prefix_only'] or hashlib.sha256(raw).hexdigest()!=head['headers_SHA256'] or b'ETag: '+ETAG.encode()+b'\r\n' not in raw:raise ValueError('terminal_ETag_URL')
 return w['complete_recorded_prefix']
def verify(a):
 if sha(HERE/'code-pins.json')!=a.code_pins_sha256 or sha(HERE/'profile.json')!=a.profile_sha256:raise ValueError('external_code_profile_pins')
 pins=json.loads((HERE/'code-pins.json').read_text())['SHA256'];p=json.loads((HERE/'profile.json').read_text())
 if set(pins)!=inventory() or p['limits']!=CAPS or p['ranges']!=core.partition(PREFIX_SIZE,SIZE,WIDTH) or p['output']!=str(OUT) or p['URL']!=URL or p['ETag']!=ETAG or p['original_monotonic_deadline']!=ORIGINAL_DEADLINE or p['prefix']['SHA256']!=PREFIX_SHA or p['prefix']['bytes']!=PREFIX_SIZE or p['prefix']['path']!=str(PREFIX) or p['publisher_MD5']!=MD5 or p['publisher_SHA1']!=SHA1:raise ValueError('exact_inventory_policy_ranges')
 for f,h in pins.items():
  q=pathlib.Path(f)
  if q.is_symlink() or not q.is_file() or sha(q)!=h:raise ValueError('input_pin_changed:'+f)
 if runtime()!=json.loads((HERE/'runtime.json').read_text()):raise ValueError('runtime_changed')
 if http.client._MAXHEADERS!=100 or http.client._MAXLINE!=65536:raise ValueError('HTTP_parser_bounds')
 options=json.loads(OPTIONS.read_text())['native_XML_option'];files=[f for f in options['files'] if f['name']=='enwiki-20260801-pages-articles-multistream.xml.bz2']
 if len(files)!=1 or (files[0]['absolute_URL'],files[0]['size'],files[0]['md5'],files[0]['sha1'])!=(URL,SIZE,MD5,SHA1) or options['source_job_status']!='done':raise ValueError('publisher_identity')
 metadata=json.loads(pathlib.Path(options['cached_metadata_file']).read_text());found=[job['files'][files[0]['name']] for job in metadata['jobs'].values() if files[0]['name'] in job.get('files',{})]
 if sha(pathlib.Path(options['cached_metadata_file']))!=options['cached_metadata_SHA256'] or len(found)!=1 or (found[0]['size'],found[0]['md5'],found[0]['sha1'],found[0]['url'])!=(SIZE,MD5,SHA1,'/enwiki/20260801/'+files[0]['name']):raise ValueError('official_cached_dumpstatus')
 prefix_metadata(p);deps();return p

def arm(seconds):
 def stop(s,f):raise TimeoutError('deadline_or_signal')
 for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:signal.signal(sig,stop)
 if seconds<=0:raise TimeoutError('original_or_job_deadline_expired')
 signal.setitimer(signal.ITIMER_REAL,seconds)
def remaining(start,worker=False):return min((WORK if worker else EXTERNAL)-(clk()-start),ORIGINAL_DEADLINE-clk()-(10 if worker else 0))
def storage(additional=0,whole=True):
 if size(OUT)+additional>OUTPUT-1048576:raise ValueError('output9GB_prewrite')
 if whole and size(ROOT)+additional>COMBINED:raise ValueError('combined_local64GB')
 if shutil.disk_usage(ROOT).free<FREE+additional:raise ValueError('weights_scratch_freefloor')
def write(name,obj):
 raw=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode();storage(len(raw),False)
 with (OUT/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def slot(name,obj):
 raw=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode();n=SLOTS[name]
 if len(raw)>n:raise ValueError('terminal_slot')
 with (OUT/name).open('r+b') as f:f.write(raw+b' '*(n-len(raw)));f.flush();os.fsync(f.fileno())
def settle_pending(ledger):
 settled=[]
 for key in [KEY+'-output']+[KEY+f'-range-{i:03}' for i in range(65)]:
  row=ledger.db.execute('select state from attempts where key=?',(key,)).fetchone()
  if row and row[0]=='pending':ledger.finish(key,raw=None);settled.append(key)
 return settled
def streamed_complete(ledger,key,receipt):
 row=ledger.db.execute('select charge,state from attempts where key=?',(key,)).fetchone();charge=json.loads(row[0]) if row else None
 if row is None or row[1]!='pending' or receipt['bytes']+1!=charge['body_bytes'] or charge['requests']!=1 or charge['output_bytes']!=0 or (len(receipt['SHA256'])!=64 or any(c not in '0123456789abcdef' for c in receipt['SHA256'])):raise ValueError('streamed_success_charge')
 cur=ledger.db.execute('update attempts set state=?,actual_bytes=?,body_sha256=? where key=? and state=?',('complete',receipt['bytes'],receipt['SHA256'],key,'pending'))
 if cur.rowcount!=1:raise ValueError('streamed_complete_exactonce')

def transfer(part,gate,tls,stop,start):
 i=part['ordinal'];state={'ordinal':i,'bytes':0,'SHA256':hashlib.sha256(b'').hexdigest()};path=OUT/f'part-{i:03}.partial';response=None
 def guard():
  if stop.is_set() or remaining(start,True)<=0:raise TimeoutError('cancel_or_shared_worker_deadline')
  storage(min(core.CHUNK,part['bytes']+1-state['bytes']),False)
 try:
  request=urllib.request.Request(URL,headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity','Range':f"bytes={part['start']}-{part['end']}",'If-Match':ETAG})
  opener=urllib.request.build_opener(tls.NoRedirect(),urllib.request.HTTPSHandler(context=tls.trusted_context()))
  response,when=gate.open(opener,request,guard);state['request_invocation_monotonic']=when;raw,headers=core.header_packet(response);write(f'part-{i:03}.headers.json',headers);core.validate(response,raw,part,URL,SIZE,ETAG)
  def progress(n,h):state.update(bytes=n,SHA256=h)
  result=core.receive(response,path,part['bytes'],guard,progress);state.update(result,status='COMPLETE_EXACT_RANGE_TRANSPORT',start=part['start'],end=part['end'],path=str(path));return state
 except BaseException as e:
  state.update(status='FAILED_NO_RETRY',error=type(e).__name__+':'+str(e)[:1000],partial_path=str(path),partial_exists=path.exists());return state
 finally:
  if response is not None:response.close()

def coordinator(a):
 arm(remaining(a.start,True));ledger=None;stop=threading.Event();pool=None
 try:
  p=verify(a)
  if os.getppid()!=a.supervisor_pid:raise ValueError('parent_PID')
  L,C,tls=deps();ledger=L(ROOT/'charges',C);allocation=ledger.db.execute('select charge,state from attempts where key=?',(KEY+'-output',)).fetchone()
  if allocation is None or allocation[1]!='pending' or json.loads(allocation[0])!={'requests':0,'body_bytes':0,'rows':0,'output_bytes':OUTPUT}:raise ValueError('exact_precharged_output_required')
  def guard():
   if remaining(a.start,True)<=0:raise TimeoutError('shared_worker_deadline')
  # No whole archive copy: verify frozen operational prefix before first GET.
  prefix=core.hash_components([p['prefix']],guard)
  prior=prefix_metadata(p)
  if (prefix['bytes'],prefix['MD5'],prefix['SHA1'],prefix['SHA256'])!=(PREFIX_SIZE,prior['MD5'],prior['SHA1'],PREFIX_SHA):raise ValueError('operational_prefix_full_hash')
  write('prefix-verification.json',prefix);gate=core.StartGate();pool=concurrent.futures.ThreadPoolExecutor(max_workers=2);running={};next_part=0;complete={};failure=None
  while running or (next_part<65 and failure is None):
   guard();ledger.check_time()
   while len(running)<2 and next_part<65 and failure is None:
    part=p['ranges'][next_part];key=KEY+f'-range-{next_part:03}';ledger.reserve(key,requests=1,body_bytes=part['bytes']+1,output_bytes=0);write(f'part-{next_part:03}.precharge.json',{'ledger_key':key,'range':part,'durable_before_HTTP':True});future=pool.submit(transfer,part,gate,tls,stop,a.start);running[future]=(part,key);next_part+=1
   done,_=concurrent.futures.wait(running,timeout=.2,return_when=concurrent.futures.FIRST_COMPLETED)
   for future in done:
    part,key=running.pop(future);receipt=future.result();i=part['ordinal']
    if receipt['status']=='COMPLETE_EXACT_RANGE_TRANSPORT':
     if core.stat_id(pathlib.Path(receipt['path']))!=receipt['stat'] or sha(receipt['path'])!=receipt['SHA256']:raise ValueError('coordinator_part_file_rehash')
     streamed_complete(ledger,key,receipt);complete[i]=receipt
    else:
     ledger.finish(key,raw=None);failure=failure or receipt['error'];stop.set()
    write(f'part-{i:03}.receipt.json',receipt)
   slot('progress.json',{'completed_parts':len(complete),'charged_parts':next_part,'planned_parts':65,'completed_response_bytes':sum(v['bytes'] for v in complete.values()),'elapsed_seconds':clk()-a.start,'partial_not_published':True})
  pool.shutdown(wait=True,cancel_futures=True);pool=None
  if failure or len(complete)!=65:raise ValueError('range_failure_no_retry:'+str(failure))
  starts=sorted(gate.starts)
  if len(starts)!=65 or any(b-a<1 for a,b in zip(starts,starts[1:])):raise ValueError('HTTP_start_spacing')
  components=[p['prefix']]+[{'path':complete[i]['path'],'bytes':complete[i]['bytes'],'SHA256':complete[i]['SHA256'],'stat':complete[i]['stat']} for i in range(65)];whole=core.hash_components(components,guard)
  if (whole['bytes'],whole['MD5'],whole['SHA1'])!=(SIZE,MD5,SHA1):raise ValueError('worker_virtual_publisher_checksums')
  verify(a);write('worker-candidate-segments.json',{'status':'WORKER_VERIFIED_NOT_PUBLISHED_UNTIL_INDEPENDENT_SUPERVISOR','URL':URL,'ETag':ETAG,'publisher_bytes':SIZE,'publisher_MD5':MD5,'publisher_SHA1':SHA1,'local_SHA256':whole['SHA256'],'components':whole['components'],'HTTP_starts_monotonic':starts,'no_full_copy':True});slot('worker-result.json',{'status':'COMPLETE_WORKER_VIRTUAL_CHECKSUMS_PENDING_INDEPENDENT_PUBLICATION','parts':65,'response_bytes':REMAIN,'body_reserved':REMAIN+65,'virtual_bytes':SIZE,'MD5':MD5,'SHA1':SHA1,'SHA256':whole['SHA256'],'candidate_manifest_SHA256':sha(OUT/'worker-candidate-segments.json'),'new_admitted_documents':0})
 except BaseException as e:
  stop.set()
  if pool is not None:pool.shutdown(wait=False,cancel_futures=True)
  if ledger is not None:settle_pending(ledger)
  slot('worker-result.json',{'status':'TERMINAL_PARTIAL_NO_RETRY_NO_PUBLICATION','error':type(e).__name__+':'+str(e)[:1500],'new_admitted_documents':0});raise
 finally:
  if ledger is not None:ledger.close()
  signal.setitimer(signal.ITIMER_REAL,0)

def kill(child):
 if child.poll()is None:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 child.wait(timeout=5)
def supervise(a):
 start=clk();arm(remaining(start));created=False;allocated=False;child=None;peak=0;ledger=None
 try:
  p=verify(a)
  if OUT.exists() or OUT.is_symlink():raise ValueError('existing_output_no_replay')
  if size(ROOT)+OUTPUT>COMBINED or shutil.disk_usage(ROOT).free<FREE+OUTPUT:raise ValueError('whole_intake_storage_headroom')
  L,C,_=deps();ledger=L(ROOT/'charges',C);totals=ledger.totals()
  if ledger.db.execute("select count(*) from attempts where state='pending'").fetchone()[0]:raise ValueError('another_pending_global_operation')
  if totals['body_bytes']+REMAIN+65>C['limits']['body_bytes'] or totals['output_bytes']+OUTPUT>C['limits']['output_bytes'] or totals['requests']+65>C['limits']['requests']:raise ValueError('global_80GB_budget')
  ledger.reserve(KEY+'-output',requests=0,body_bytes=0,output_bytes=OUTPUT);allocated=True;ledger.close();ledger=None
  OUT.mkdir(exist_ok=False);created=True
  for name,n in SLOTS.items():(OUT/name).write_bytes(b' '*n)
  with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen([sys.executable,'-B',str(HERE/'segmented.py'),'--coordinator','--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256,'--start',str(start),'--supervisor-pid',str(os.getpid())],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  write('ownership.json',{'supervisor_pid':os.getpid(),'coordinator_pid':child.pid,'shared_start':start,'original_deadline':ORIGINAL_DEADLINE,'code_pins_SHA256':a.code_pins_sha256,'profile_SHA256':a.profile_sha256,'output_allocation_key':KEY+'-output'})
  rss=load('segmented_RSS_guard',BASE/'wikibooks-current20-native-source-capture-preparation-v2/supervisor_core.py')
  while child.poll()is None:
   if remaining(start,True)<=0:raise TimeoutError('coordinator_shared_deadline')
   peak=max(peak,rss.tree_rss(os.getpid()))
   if peak>RSS:raise ValueError('process_tree_RSS1GB')
   storage();time.sleep(.5)
  child.wait(timeout=5);worker=json.loads((OUT/'worker-result.json').read_text())
  if child.returncode!=0 or worker['status']!='COMPLETE_WORKER_VIRTUAL_CHECKSUMS_PENDING_INDEPENDENT_PUBLICATION':raise ValueError('coordinator_not_complete')
  L,C,_=deps();ledger=L(ROOT/'charges',C)
  for part in p['ranges']:
   i=part['ordinal'];row=ledger.db.execute('select charge,state,actual_bytes,body_sha256 from attempts where key=?',(KEY+f'-range-{i:03}',)).fetchone();receipt=json.loads((OUT/f'part-{i:03}.receipt.json').read_text())
   if row is None or row[1:]!=('complete',part['bytes'],receipt['SHA256']) or json.loads(row[0])!={'requests':1,'body_bytes':part['bytes']+1,'rows':0,'output_bytes':0}:raise ValueError('exact65_ledger_transport_receipts')
  candidate=json.loads((OUT/'worker-candidate-segments.json').read_text());components=candidate['components']
  expected_paths=[str(PREFIX)]+[str(OUT/f'part-{i:03}.partial') for i in range(65)]
  if [e['path'] for e in components]!=expected_paths or [e['bytes'] for e in components]!=[PREFIX_SIZE]+[e['bytes'] for e in p['ranges']]:raise ValueError('frozen_component_order_no_extra_paths')
  last_resource_check=0
  def guard():
   nonlocal peak,last_resource_check
   if remaining(start)<=0:raise TimeoutError('independent_verification_deadline')
   if clk()-last_resource_check>=1:
    peak=max(peak,rss.tree_rss(os.getpid()));last_resource_check=clk()
    if peak>RSS:raise ValueError('independent_supervisor_RSS')
    storage()
  # Supervisor streams bytes itself after coordinator is reaped, without copying.
  independent=core.hash_components(components,guard)
  if (independent['bytes'],independent['MD5'],independent['SHA1'],independent['SHA256'])!=(SIZE,MD5,SHA1,worker['SHA256']) or independent['components'][0]['SHA256']!=PREFIX_SHA:raise ValueError('independent_publisher_whole_virtual_checksum')
  verify(a);storage();peak=max(peak,rss.tree_rss(os.getpid()))
  if peak>RSS:raise ValueError('final_supervisor_RSS')
  ledger.finish(KEY+'-output',raw=b'');ledger.close();ledger=None
  final={'status':'COMPLETE_VIRTUAL_ARCHIVE_WORKER_AND_INDEPENDENT_SUPERVISOR_VERIFIED','URL':URL,'ETag':ETAG,'bytes':SIZE,'publisher_MD5':MD5,'publisher_SHA1':SHA1,'local_SHA256':independent['SHA256'],'ordered_components':independent['components'],'no_concatenated_full_file_created':True,'no_decompression_or_usable_data_claim':True,'worker_receipt_SHA256':sha(OUT/'worker-result.json'),'new_admitted_documents':0};write('virtual-archive-manifest.pending.json',final);os.replace(OUT/'virtual-archive-manifest.pending.json',OUT/'virtual-archive-manifest.json');fd=os.open(OUT,os.O_RDONLY);os.fsync(fd);os.close(fd)
  slot('supervisor-result.json',{'status':'COMPLETE_VIRTUAL_ARCHIVE_NO_ADMISSION','coordinator_exit_code':0,'coordinator_reaped':True,'elapsed_seconds':clk()-start,'peak_tree_RSS_bytes':peak,'output_bytes':size(OUT),'virtual_manifest_SHA256':sha(OUT/'virtual-archive-manifest.json'),'independent_checksums':{k:independent[k] for k in ['bytes','MD5','SHA1','SHA256']},'all_charges_preserved':True,'new_admitted_documents':0})
 except BaseException as e:
  if child is not None:kill(child)
  if allocated:
   if ledger is not None:ledger.close();ledger=None
   L,C,_=deps();ledger=L(ROOT/'charges',C);settled=settle_pending(ledger);ledger.close();ledger=None
  else:settled=[]
  if created:
   custody=[]
   L,C,_=deps();audit_ledger=L(ROOT/'charges',C)
   try:
    for i in range(65):
     key=KEY+f'-range-{i:03}';row=audit_ledger.db.execute('select charge,state,actual_bytes,body_sha256 from attempts where key=?',(key,)).fetchone();part=OUT/f'part-{i:03}.partial'
     if row is not None:custody.append({'key':key,'charge':json.loads(row[0]),'ledger_state':row[1],'actual_successful_bytes':row[2],'body_SHA256_if_complete':row[3],'retained_partial_stat':core.stat_id(part) if part.exists() else None,'per_attempt_receipt_exists':(OUT/f'part-{i:03}.receipt.json').exists(),'failed_full_body_hash_unknown_if_no_receipt':row[1]!='complete' and not (OUT/f'part-{i:03}.receipt.json').exists()})
   finally:audit_ledger.close()
   write('post-reap-attempt-custody.json',{'all_local_parts_preserved':True,'no_failed_reservation_refunded':True,'attempts':custody})
   record={'status':'TERMINAL_PARTIAL_NO_RETRY_NO_COMPLETE_ARCHIVE','error':type(e).__name__+':'+str(e)[:1500],'coordinator_reaped':child is None or child.poll()is not None,'pending_exact_keys_settled_failed':settled,'new_admitted_documents':0}
   if (OUT/'supervisor-result.json').exists():slot('supervisor-result.json',record)
   else:write('supervisor-result.json',record)
  raise
 finally:
  if ledger is not None:ledger.close()
  signal.setitimer(signal.ITIMER_REAL,0)
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--coordinator',action='store_true');p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True);p.add_argument('--start',type=float);p.add_argument('--supervisor-pid',type=int);a=p.parse_args()
 if a.coordinator:coordinator(a)
 elif a.execute:supervise(a)
 else:
  arm(min(120,ORIGINAL_DEADLINE-clk()))
  try:verify(a);print('READY_NO_NETWORK_OR_PREFIX_BODY_READ')
  finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':main()
