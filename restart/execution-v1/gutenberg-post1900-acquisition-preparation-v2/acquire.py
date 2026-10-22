"""Post1900 fixed20 body discovery, existing durable ledger and PG TLS helper; no admission."""
import argparse,datetime,hashlib,importlib.util,json,os,pathlib,re,shutil,signal,subprocess,sys,time,urllib.request,urllib.error
from urllib.parse import urljoin,urlsplit
import ssl,sqlite3,socket,http.client,platform,_ssl,_hashlib,_sqlite3,xml.etree.ElementTree,urllib.parse
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake'
CAPS={'bodies':20,'body_bytes':2400000,'output_bytes':50000000,'metadata_bytes':2000000,'physical_requests':60,'redirects_per_body':2,'pace_seconds':2,'body_seconds':60,'worker_seconds':1470,'external_seconds':1500,'observed_RSS_bytes':1000000000}
FREE=21474836480+16000000000+16000000000
PREFIX='gutenberg-post1900-fixed20-v2-'
OUT=ROOT/'gutenberg-post1900-cohort-raw-v2'
PROPOSAL=ROOT/'gutenberg-post1900-body-discovery-proposal-v1/proposal.json'
INPUT_RECORDS=BASE/'gutenberg-post1900-metadata-capacity-v1/records.json'
SLOTS={'worker-result.json':65536,'supervisor-result.json':32768}
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def size(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file())
def same_ebook(url,eid):
 u=urlsplit(url)
 return u.scheme=='https' and u.netloc in ['www.gutenberg.org','gutenberg.org'] and not u.query and not u.fragment and (u.path==f'/ebooks/{eid}.txt.utf-8' or u.path==f'/cache/epub/{eid}/pg{eid}.txt' or bool(re.fullmatch(r'/files/'+str(eid)+r'/(?:pg)?'+str(eid)+r'(?:-0|-[89])?\.txt',u.path)))
def redirect_decision(current,location,eid):
 # This predeclared mapping is applied only AFTER the exact Location is observed.
 # Absolute literal equality excludes ports/userinfo/queries/fragments/encoding tricks.
 expected=f'http://www.gutenberg.org/cache/epub/{eid}/pg{eid}.txt'
 resolved=urljoin(current,location)
 if location==expected:
  target='https'+location[4:]
  return {'captured_Location_verbatim':location,'resolved_Location':resolved,'allowed':True,'next_HTTPS_URL':target,'policy':'exact_same_ID_www_cache_path_scheme_only_upgrade','HTTP_transport_permitted':False}
 if urlsplit(resolved).scheme=='http':
  return {'captured_Location_verbatim':location,'resolved_Location':resolved,'allowed':False,'next_HTTPS_URL':None,'policy':'unknown_HTTP_Location_HELD_NO_FOLLOW','HTTP_transport_permitted':False}
 return {'captured_Location_verbatim':location,'resolved_Location':resolved,'allowed':same_ebook(resolved,eid),'next_HTTPS_URL':resolved if same_ebook(resolved,eid) else None,'policy':'existing_explicit_HTTPS_same_ID_redirect','HTTP_transport_permitted':False}
def disk(out,additional=0):
 if size(out)+additional>CAPS['output_bytes']:raise ValueError('output_cap')
 if shutil.disk_usage(ROOT).free<FREE+additional:raise ValueError('free_floor_weights_scratch')
def write(out,name,obj):
 b=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode();disk(out,len(b));p=out/name
 if sum(x.stat().st_size for x in out.iterdir() if x.is_file() and x.suffix not in ['.raw','.partial'])+len(b)>2000000:raise ValueError('metadata_cap')
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def terminal(out,name,obj):
 b=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode();n=SLOTS[name]
 if len(b)>n:raise ValueError('terminal_slot')
 with (out/name).open('r+b') as f:f.write(b+b' '*(n-len(b)));f.flush();os.fsync(f.fileno())
def runtime():
 return {'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'openssl':ssl.OPENSSL_VERSION,'sqlite':sqlite3.sqlite_version,'platform':platform.platform(),'native_module_origins':{m.__name__:m.__spec__.origin for m in [_ssl,_hashlib,_sqlite3]}}
def bound_inventory():
 paths=[HERE/n for n in ['acquire.py','code_guard.py','checks.py','profile.json']]+[BASE/'acquire_sources.py',REPO/'src/slm/data/intake_ledger.py',REPO/'src/slm/data/schema.py',BASE/'disk-budget.json',BASE/'authorization.json',BASE/'source-acquisition-authorization.json',ROOT/'gutenberg-preparation-parallel-v4/discover.py',pathlib.Path('/opt/homebrew/etc/ca-certificates/cert.pem'),PROPOSAL,INPUT_RECORDS]
 paths += [pathlib.Path(m.__file__) for m in [datetime,hashlib,importlib.util,json,pathlib,re,shutil,signal,subprocess,urllib.request,urllib.error,urllib.parse,ssl,sqlite3,sqlite3.dbapi2,socket,http.client,platform,xml.etree.ElementTree,_ssl,_hashlib,_sqlite3] if getattr(m,'__file__',None)]
 prior=ROOT/'gutenberg-first-prose-cohort-raw-v1'
 oldprofile=json.loads((BASE/'gutenberg-cohort-acquisition-preparation-v2/profile.json').read_text())
 paths += [BASE/'gutenberg-cohort-acquisition-preparation-v2/profile.json',prior/'worker-result.json',prior/'supervisor-result.json']+[prior/f"pg{r['ebook_ID']}-hop0.json" for r in oldprofile['records']]
 paths.append(pathlib.Path(sys.executable))
 return {str(p.resolve()) for p in paths}
def verify(code,profile_sha):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=profile_sha:raise ValueError('external_profile_pin')
 p=json.loads((HERE/'profile.json').read_text())
 if p['limits']!=CAPS or p['output']!=str(OUT) or p['ledger_prefix']!=PREFIX:raise ValueError('fixed_profile_caps_identity')
 proposal=json.loads(PROPOSAL.read_text())
 if p['records']!=proposal['selected_records'] or len(p['records'])!=20:raise ValueError('exact20proposal')
 if sha(INPUT_RECORDS)!=proposal['input_records_SHA256']:raise ValueError('proposal_source_metadata_pin')
 if len({r['ebook_ID'] for r in p['records']})!=20:raise ValueError('duplicate_ID')
 for r in p['records']:
  if r['source_URL']!=f"https://www.gutenberg.org/ebooks/{r['ebook_ID']}.txt.utf-8":raise ValueError('native_URL')
  if r['catalog_extent_bytes_not_body_verified']>CAPS['body_bytes']:raise ValueError('catalog_extent_above_bound')
 expected_mapping=[{'ebook_ID':r['ebook_ID'],'only_if_Location_actually_equals':f"http://www.gutenberg.org/cache/epub/{r['ebook_ID']}/pg{r['ebook_ID']}.txt",'then_next_HTTPS_URL':f"https://www.gutenberg.org/cache/epub/{r['ebook_ID']}/pg{r['ebook_ID']}.txt"} for r in p['records']]
 if p['conditional_per_ebook_upgrade_mapping']!=expected_mapping:raise ValueError('fixed20_conditional_upgrade_mapping')
 prior=ROOT/'gutenberg-first-prose-cohort-raw-v1';oldprofile=json.loads((BASE/'gutenberg-cohort-acquisition-preparation-v2/profile.json').read_text());w=json.loads((prior/'worker-result.json').read_text());supervisor=json.loads((prior/'supervisor-result.json').read_text())
 if supervisor['worker_receipt_sha256']!=sha(prior/'worker-result.json') or supervisor['worker_exit_code']!=0 or w['successful_raw_bodies']!=0 or w['failed_bodies']!=20:raise ValueError('prior_transport_observation_chain')
 for r in oldprofile['records']:
  eid=r['ebook_ID'];h=json.loads((prior/f'pg{eid}-hop0.json').read_text());locations=[v for k,v in h['headers'] if k.lower()=='location']
  if h['url']!=f'https://www.gutenberg.org/ebooks/{eid}.txt.utf-8' or h['status']!=302 or locations!=[f'http://www.gutenberg.org/cache/epub/{eid}/pg{eid}.txt']:raise ValueError('prior_exact_HTTP_cache_pattern')
 if p['HTTP_cache_upgrade_rule']!={'observed_Location_template':'http://www.gutenberg.org/cache/epub/<sameEID>/pg<sameEID>.txt','target_change':'scheme_only_http_to_https_after_observed_redirect','only_absolute_literal_www_same_ID_path':True,'HTTP_transport_allowed':False}:raise ValueError('fixed_upgrade_policy')
 if http.client._MAXLINE!=65536 or http.client._MAXHEADERS!=100:raise ValueError('HTTP_parser_bound_drift')
 return p
def helpers():
 sys.path[:0]=[str(REPO/'src'),str(BASE)]
 import acquire_sources
 from slm.data import intake_ledger
 if pathlib.Path(acquire_sources.__file__).resolve()!=BASE/'acquire_sources.py' or pathlib.Path(intake_ledger.__file__).resolve()!=REPO/'src/slm/data/intake_ledger.py':raise ValueError('runtime_import_origin')
 IntakeLedger,CONTRACT=acquire_sources.IntakeLedger,acquire_sources.CONTRACT
 path=ROOT/'gutenberg-preparation-parallel-v4/discover.py';spec=importlib.util.spec_from_file_location('frozen_pg_tls_helper',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 mod.trusted_context()
 return IntakeLedger,CONTRACT,mod
class BodyDeadline(Exception):pass
def alarm(signum,frame):raise BodyDeadline('absolute60second_body_deadline')
def response_open(opener,url,timeout):
 try:return opener.open(urllib.request.Request(url,headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity'}),timeout=timeout)
 except urllib.error.HTTPError as e:return e

def transfer(row,out,ledger,key,opener,state,started,open_fn=response_open):
 eid=row['ebook_ID'];url=row['source_URL'];path=out/f'pg{eid}.partial';hopreceipts=[];lastbytes=0;complete=False;error=None;begin=clk();current_hop=None;current_hop_IO_began=False
 def check():
  if clk()-begin>=60:raise BodyDeadline('body_deadline')
  if clk()-started>=1470:raise BodyDeadline('worker_deadline')
  ledger.check_time();disk(out)
 try:
  for hop in range(3):
   check()
   if not same_ebook(url,eid):raise ValueError('redirect_identity_or_host')
   if hop and url in [x['url'] for x in hopreceipts]:raise ValueError('redirect_loop')
   if state['last_request'] is not None:
    wait=max(0,2-(clk()-state['last_request']))
    if wait:time.sleep(wait)
   check()
   hopkey=key+'-hop'+str(hop)
   current_hop=None;current_hop_IO_began=False
   ledger.reserve(hopkey,requests=1)
   current_hop=hopkey
   write(out,f'pg{eid}-hop{hop}-attempt.json',{'url':url,'hop':hop,'ledger_key':hopkey,'status':'DURABLY_CHARGED_BEFORE_HTTP_IO'})
   state['last_request']=clk();state['requests']+=1
   if state['requests']>60:raise ValueError('physical_request_cap')
   current_hop_IO_began=True
   res=open_fn(opener,url,min(20,max(.01,60-(clk()-begin))))
   with res:
    ledger.finish(hopkey,raw=b'')
    headers=list(res.headers.items());header_blob=json.dumps(headers,ensure_ascii=False).encode()
    rec={'url':url,'hop':hop,'status':res.code,'headers':headers,'headers_json_sha256':hashlib.sha256(header_blob).hexdigest(),'started_shared_monotonic':state['last_request'],'redirect_response_body':'not_read_closed_without_body_allocation' if res.code in [301,302,303,307,308] else 'bounded_final_body'}
    if len(header_blob)>1000000:
     write(out,f'pg{eid}-hop{hop}-oversize-headers.json',{'status':res.code,'url':url,'exact_serialized_headers_prefix_hex':header_blob[:65536].hex(),'full_serialized_headers_sha256':hashlib.sha256(header_blob).hexdigest(),'full_serialized_headers_bytes':len(header_blob),'hold':'header_capture_bound_exceeded_no_body_read'})
     raise ValueError('headers_exceed_metadata_allowance')
    write(out,f'pg{eid}-hop{hop}.json',rec);hopreceipts.append({'url':url,'status':res.code})
    if res.geturl()!=url:raise ValueError('implicit_redirect')
    if res.code in [301,302,303,307,308]:
     if hop==2:raise ValueError('redirect_limit')
     locations=res.headers.get_all('Location',[])
     if len(locations)!=1 or not locations[0]:raise ValueError('redirect_requires_single_Location')
     location=locations[0]
     decision=redirect_decision(url,location,eid)
     write(out,f'pg{eid}-hop{hop}-redirect-decision.json',decision)
     if not decision['allowed']:raise ValueError('redirect_identity_or_host_or_unknown_HTTP')
     url=decision['next_HTTPS_URL']
     if not same_ebook(url,eid):raise ValueError('redirect_identity_or_host')
     continue
    # Preserve bounded response bytes even on status/content validation failures.
    error_status=None if res.code==200 else 'HTTP_status_'+str(res.code)
    if res.headers.get('Content-Encoding') not in [None,'identity']:error_status=error_status or 'encoded_body'
    if res.headers.get_content_type()!='text/plain':error_status=error_status or 'not_plain_text'
    length=res.headers.get('Content-Length');advertised=None
    if length is not None:
     try:advertised=int(length)
     except ValueError:error_status=error_status or 'invalid_content_length'
     if advertised is not None and not 0<=advertised<=2400000:error_status=error_status or 'advertised_over_cap'
    with path.open('xb') as f:
     try:
      while lastbytes<2400000:
       check();b=res.read1(min(65536,2400000-lastbytes))
       if not b:break
       disk(out,len(b));f.write(b);f.flush();lastbytes+=len(b)
     finally:f.flush();os.fsync(f.fileno())
    if lastbytes==2400000:raise ValueError('body_hits_cap_no_unreserved_EOF_probe')
    if advertised is not None and advertised!=lastbytes:error_status=error_status or 'content_length_mismatch'
    raw=path.read_bytes()
    try:raw.decode('utf-8-sig',errors='strict')
    except UnicodeDecodeError:error_status=error_status or 'invalid_UTF8'
    if b'\x00' in raw:error_status=error_status or 'NUL_bytes'
    if error_status:raise ValueError(error_status)
    ledger.finish(key,raw=raw);os.rename(path,out/f'pg{eid}.raw');fd=os.open(out,os.O_RDONLY);os.fsync(fd);os.close(fd);complete=True;break
  if not complete:raise ValueError('no_body_response')
 except BaseException as e:
  error=type(e).__name__+':'+str(e)[:500];hopfailure=None
  if current_hop is not None:
   pending=ledger.db.execute('select state from attempts where key=?',(current_hop,)).fetchone()
   if pending==('pending',):
    ledger.finish(current_hop,raw=None)
    hopfailure={'url':url,'hop':hop,'ledger_key':current_hop,'status':'FAILED_NO_RETRY_REQUEST_CHARGE_RETAINED','IO_began':current_hop_IO_began,'response_headers_available':False,'error':error}
  rowstate=ledger.db.execute('select state from attempts where key=?',(key,)).fetchone()
  if rowstate and rowstate[0]=='pending':ledger.finish(key,raw=None)
  if hopfailure is not None:write(out,f'pg{eid}-hop{hop}-failure.json',hopfailure)
 finally:
  p=out/(f'pg{eid}.raw' if complete else f'pg{eid}.partial')
  rec={'ebook_ID':eid,'original_selected_metadata_record':row,'ordinal':row['source_binding']['member_identity']['ordinal'],'family_component_ID':row['family_component_ID'],'frame_raw_hash':row['frame_raw_hash'],'source_binding':row['source_binding'],'requested_native_URL':row['source_URL'],'metadata_genre_proxy':row['primary_metadata_stratum'],'status':'RAW_DISCOVERY_COMPLETE_NOT_ADMITTED' if complete else 'FAILED_PARTIAL_NO_RETRY','error':error,'hops':hopreceipts,'received_bytes':p.stat().st_size if p.exists() else 0,'raw_or_partial_sha256':sha(p) if p.exists() else None,'body_file':p.name if p.exists() else None,'elapsed_seconds':clk()-begin,'new_admitted_documents':0}
  write(out,f'pg{eid}-receipt.json',rec)
 return rec

def settle_pending(ledger,prefix):
 keys=[k for k, in ledger.db.execute("select key from attempts where state='pending' and key like ?",(prefix+'%',))]
 for key in keys:ledger.finish(key,raw=None)
 return keys

def reserve_metadata(ledger):ledger.reserve(PREFIX+'metadata',output_bytes=2000000,body_bytes=2000000)
def require_metadata_pending(ledger):
 row=ledger.db.execute('select charge,state from attempts where key=?',(PREFIX+'metadata',)).fetchone()
 if row is None or row[1]!='pending' or json.loads(row[0])!={'requests':0,'body_bytes':2000000,'rows':0,'output_bytes':2000000}:raise ValueError('supervisor_exact_metadata_precharge_required')
def supervisor_reserve_metadata():
 L,C,T=helpers();l=L(ROOT/'charges',C)
 try:reserve_metadata(l)
 finally:l.close()
def cleanup_owned():
 try:
  L,C,T=helpers();l=L(ROOT/'charges',C)
  try:
   settled=settle_pending(l,PREFIX);metadata=l.db.execute('select state from attempts where key=?',(PREFIX+'metadata',)).fetchone()
   pending=l.db.execute("select count(*) from attempts where state='pending' and key like ?",(PREFIX+'%',)).fetchone()[0]
   return {'settled_failed_no_refund':settled,'metadata_state':metadata[0] if metadata else None,'pending':pending,'reservations_retained':True}
  finally:l.close()
 except BaseException as e:return {'cleanup_hold':type(e).__name__+':'+str(e)[:300]}

def worker(args):
 p=verify(args.code_pins_sha256,args.profile_sha256);out=pathlib.Path(p['output']);start=float(args.start)
 if os.getppid()!=args.supervisor_pid:raise ValueError('parent_identity')
 Ledger,contract,helper=helpers()
 try:ledger=Ledger(ROOT/'charges',contract)
 except BaseException as e:
  terminal(out,'worker-result.json',{'status':'PROFILE_TERMINAL_PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'new_admitted_documents':0});raise
 records=[];state={'requests':0,'last_request':None};prefix=PREFIX
 previous=signal.signal(signal.SIGALRM,alarm)
 try:
  # Every finite allowance charged durably before the first HTTP operation.
  require_metadata_pending(ledger)
  for r in p['records']:ledger.reserve(prefix+str(r['ebook_ID']),body_bytes=2400000,output_bytes=2400000)
  write(out,'reservation.json',{'keys':[prefix+'metadata']+[prefix+str(r['ebook_ID']) for r in p['records']],'global_reserved_after_charge':ledger.totals(),'maximum_future_physical_requests':60,'physical_requests_reserved_so_far':0,'body_output_reserved':50000000,'no_refund_or_retry':True})
  class ExplicitRedirect(urllib.request.HTTPRedirectHandler):
   def redirect_request(self,*a,**kw):return None
  opener=urllib.request.build_opener(ExplicitRedirect(),urllib.request.HTTPSHandler(context=helper.trusted_context()))
  for r in p['records']:
   if clk()-start>=1470:raise BodyDeadline('worker_deadline')
   signal.setitimer(signal.ITIMER_REAL,60)
   try:records.append(transfer(r,out,ledger,prefix+str(r['ebook_ID']),opener,state,start))
   finally:signal.setitimer(signal.ITIMER_REAL,0)
  verify(args.code_pins_sha256,args.profile_sha256)
  ledger.finish(prefix+'metadata',raw=b'')
  terminal(out,'worker-result.json',{'status':'FINITE20_ATTEMPTS_TERMINAL_NO_ADMISSION','successful_raw_bodies':sum(r['error'] is None for r in records),'failed_bodies':sum(r['error'] is not None for r in records),'physical_requests':state['requests'],'records':[{'ebook_ID':r['ebook_ID'],'status':r['status'],'bytes':r['received_bytes'],'sha256':r['raw_or_partial_sha256']} for r in records],'global_reserved':ledger.totals(),'elapsed_seconds':clk()-start,'new_admitted_documents':0,'new_admitted_tokens':0})
 except BaseException as e:
  settled=settle_pending(ledger,prefix)
  terminal(out,'worker-result.json',{'status':'PROFILE_TERMINAL_PARTIAL_NO_RETRY','unattempted_or_uncertain_allocations_failed_no_refund':settled,'error':type(e).__name__+':'+str(e)[:1000],'completed_attempts':len(records),'physical_requests':state['requests'],'global_reserved':ledger.totals(),'new_admitted_documents':0});raise
 finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous);ledger.close()

def tree(ps,root):
 rows=[tuple(map(int,l.split())) for l in ps.splitlines() if len(l.split())==3];parents={p:q for p,q,r in rows};rss={p:r*1024 for p,q,r in rows};owned={root}
 if root not in rss:raise ValueError('missing_root_process')
 while True:
  nxt=owned|{p for p,q in parents.items() if q in owned}
  if nxt==owned:return sum(rss[p] for p in owned)
  owned=nxt

def kill(child):
 if child.poll() is None:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 child.wait(timeout=5)
def supervise(args):
 start=clk();p=verify(args.code_pins_sha256,args.profile_sha256);helpers();out=pathlib.Path(p['output'])
 if out!=OUT or out.exists():raise ValueError('fixed_output_no_retry')
 if ROOT.is_symlink() or any(x.is_symlink() for x in ROOT.rglob('*')):raise ValueError('intake_symlink')
 diskpolicy=json.loads((BASE/'disk-budget.json').read_text())
 if diskpolicy['weights_checkpoints_reserved_bytes']!=16000000000 or diskpolicy['scratch_cap_bytes']!=16000000000 or diskpolicy['free_disk_floor_bytes']!=21474836480 or diskpolicy['raw_download_cap_bytes']!=80000000000 or diskpolicy['processed_data_cap_bytes']!=64000000000:raise ValueError('storage_policy_drift')
 if size(ROOT)+50000000>min(diskpolicy['processed_data_cap_bytes'],diskpolicy['raw_download_cap_bytes']):raise ValueError('combined_intake_cap')
 if shutil.disk_usage(ROOT).free<FREE+50000000:raise ValueError('preflight_free_reserves')
 child=None;peak=0;reason=None;metadata_charged=False
 def stop(s,f):raise RuntimeError('supervisor_signal_'+str(s))
 handlers={s:signal.signal(s,stop) for s in [signal.SIGINT,signal.SIGTERM,signal.SIGALRM]}
 signal.setitimer(signal.ITIMER_REAL,1500)
 try:
  supervisor_reserve_metadata();metadata_charged=True
  out.mkdir()
  for name,n in SLOTS.items():
   with (out/name).open('xb') as f:f.write(b' '*n);f.flush();os.fsync(f.fileno())
  child=subprocess.Popen([sys.executable,str(HERE/'acquire.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',args.code_pins_sha256,'--profile-sha256',args.profile_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  write(out,'ownership.json',{'supervisor_pid':os.getpid(),'worker_pid':child.pid,'start_shared_monotonic':start,'limits':CAPS,'code_pins_sha256':args.code_pins_sha256,'profile_sha256':args.profile_sha256})
  while child.poll() is None:
   elapsed=clk()-start
   if elapsed>=1470:reason='worker1470_cap';break
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rss=tree(ps.stdout,os.getpid());peak=max(peak,rss)
   if rss>1000000000:reason='observed_RSS_cap';break
   disk(out)
   if size(ROOT)>64000000000:reason='combined_intake64GB';break
   time.sleep(.5)
  if reason:kill(child)
  else:child.wait(timeout=5)
  w=json.loads((out/'worker-result.json').read_text());done=child.returncode==0 and w.get('status')=='FINITE20_ATTEMPTS_TERMINAL_NO_ADMISSION' and w.get('successful_raw_bodies',-1)+w.get('failed_bodies',-1)==20 and clk()-start<1500
  cleanup=cleanup_owned()
  if cleanup.get('cleanup_hold') or cleanup.get('pending')!=0 or cleanup.get('metadata_state')!='complete':done=False;reason=reason or 'owned_ledger_cleanup_or_metadata_hold'
  verify(args.code_pins_sha256,args.profile_sha256)
  terminal(out,'supervisor-result.json',{'owned_ledger_terminal':cleanup,'status':'FINITE_PROFILE_TERMINAL_NO_ADMISSION' if done else 'PROFILE_PARTIAL_NO_RETRY','reason':reason,'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'output_bytes':size(out),'worker_receipt_sha256':sha(out/'worker-result.json'),'new_admitted_documents':0,'new_admitted_tokens':0});return 0 if done else 1
 except BaseException as e:
  if child is not None:kill(child)
  cleanup=cleanup_owned() if metadata_charged else {'not_allocated':True}
  rec={'status':'PROFILE_PARTIAL_NO_RETRY','reason':type(e).__name__+':'+str(e)[:1500],'owned_ledger_terminal':cleanup,'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'new_admitted_documents':0}
  if (out/'supervisor-result.json').exists():terminal(out,'supervisor-result.json',rec)
  elif out.exists():write(out,'failure-before-slots.json',rec)
  raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  for s,h in handlers.items():signal.signal(s,h)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--worker',action='store_true');ap.add_argument('--code-pins-sha256',required=True);ap.add_argument('--profile-sha256',required=True);ap.add_argument('--supervisor-pid',type=int);ap.add_argument('--start');a=ap.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a.code_pins_sha256,a.profile_sha256);helpers();print('PREPARED_VERIFIED_ALL_RUNTIME_IMPORTS_NO_NETWORK')
