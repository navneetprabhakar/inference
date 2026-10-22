"""Finite20 body discovery, existing durable ledger and PG TLS helper; no admission."""
import argparse,datetime,hashlib,importlib.util,json,os,pathlib,re,shutil,signal,subprocess,sys,time,urllib.request,urllib.error
from urllib.parse import urljoin,urlsplit
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake'
CAPS={'bodies':20,'body_bytes':2400000,'output_bytes':50000000,'metadata_bytes':2000000,'physical_requests':60,'redirects_per_body':2,'pace_seconds':2,'body_seconds':60,'worker_seconds':1470,'external_seconds':1500,'observed_RSS_bytes':1000000000}
FREE=21474836480+16000000000+16000000000
SLOTS={'worker-result.json':65536,'supervisor-result.json':32768}
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def size(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file())
def same_ebook(url,eid):
 u=urlsplit(url)
 return u.scheme=='https' and u.netloc in ['www.gutenberg.org','gutenberg.org'] and not u.query and not u.fragment and (u.path==f'/ebooks/{eid}.txt.utf-8' or u.path==f'/cache/epub/{eid}/pg{eid}.txt' or bool(re.fullmatch(r'/files/'+str(eid)+r'/(?:pg)?'+str(eid)+r'(?:-0|-[89])?\.txt',u.path)))
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
def bound_inventory():
 return {str(p.resolve()) for p in [HERE/n for n in ['acquire.py','code_guard.py','checks.py','profile.json']]+[BASE/'acquire_sources.py',REPO/'src/slm/data/intake_ledger.py',REPO/'src/slm/data/schema.py',BASE/'disk-budget.json',BASE/'authorization.json',BASE/'source-acquisition-authorization.json',ROOT/'gutenberg-preparation-parallel-v4/discover.py',pathlib.Path('/opt/homebrew/etc/ca-certificates/cert.pem'),ROOT/'gutenberg-first-prose-cohort-proposal-v1/proposal.json']}
def verify(code,profile_sha):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=profile_sha:raise ValueError('external_profile_pin')
 p=json.loads((HERE/'profile.json').read_text());assert p['limits']==CAPS
 proposal=json.loads((ROOT/'gutenberg-first-prose-cohort-proposal-v1/proposal.json').read_text())
 if p['records']!=proposal['records'] or len(p['records'])!=20:raise ValueError('exact20proposal')
 if len({r['ebook_ID'] for r in p['records']})!=20:raise ValueError('duplicate_ID')
 for r in p['records']:
  if r['format']['resolved_URL']!=f"https://www.gutenberg.org/ebooks/{r['ebook_ID']}.txt.utf-8":raise ValueError('native_URL')
 return p
def helpers():
 sys.path[:0]=[str(REPO/'src'),str(BASE)]
 from acquire_sources import IntakeLedger,CONTRACT
 path=ROOT/'gutenberg-preparation-parallel-v4/discover.py';spec=importlib.util.spec_from_file_location('frozen_pg_tls_helper',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 return IntakeLedger,CONTRACT,mod
class BodyDeadline(Exception):pass
def alarm(signum,frame):raise BodyDeadline('absolute60second_body_deadline')
def response_open(opener,url,timeout):
 try:return opener.open(urllib.request.Request(url,headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity'}),timeout=timeout)
 except urllib.error.HTTPError as e:return e

def transfer(row,out,ledger,key,opener,state,started,open_fn=response_open):
 eid=row['ebook_ID'];url=row['format']['resolved_URL'];path=out/f'pg{eid}.partial';hopreceipts=[];lastbytes=0;complete=False;error=None;begin=clk()
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
   ledger.reserve(hopkey,requests=1)
   write(out,f'pg{eid}-hop{hop}-attempt.json',{'url':url,'hop':hop,'ledger_key':hopkey,'status':'DURABLY_CHARGED_BEFORE_HTTP_IO'})
   state['last_request']=clk();state['requests']+=1
   if state['requests']>60:raise ValueError('physical_request_cap')
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
     location=res.headers.get('Location')
     if not location:raise ValueError('redirect_without_location')
     url=urljoin(url,location)
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
  error=type(e).__name__+':'+str(e)[:500]
  rowstate=ledger.db.execute('select state from attempts where key=?',(key,)).fetchone()
  if rowstate and rowstate[0]=='pending':ledger.finish(key,raw=None)
 finally:
  p=out/(f'pg{eid}.raw' if complete else f'pg{eid}.partial')
  rec={'ebook_ID':eid,'ordinal':row['ordinal'],'family_component_ID':row['family_component_ID'],'frame_raw_hash':row['frame_raw_hash'],'source_binding':row['source_binding'],'requested_native_URL':row['format']['resolved_URL'],'metadata_genre_proxy':row['metadata_stratum'],'status':'RAW_DISCOVERY_COMPLETE_NOT_ADMITTED' if complete else 'FAILED_PARTIAL_NO_RETRY','error':error,'hops':hopreceipts,'received_bytes':p.stat().st_size if p.exists() else 0,'raw_or_partial_sha256':sha(p) if p.exists() else None,'body_file':p.name if p.exists() else None,'elapsed_seconds':clk()-begin,'new_admitted_documents':0}
  write(out,f'pg{eid}-receipt.json',rec)
 return rec

def worker(args):
 p=verify(args.code_pins_sha256,args.profile_sha256);out=pathlib.Path(p['output']);start=float(args.start)
 if os.getppid()!=args.supervisor_pid:raise ValueError('parent_identity')
 Ledger,contract,helper=helpers()
 try:ledger=Ledger(ROOT/'charges',contract)
 except BaseException as e:
  terminal(out,'worker-result.json',{'status':'PROFILE_TERMINAL_PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'new_admitted_documents':0});raise
 records=[];state={'requests':0,'last_request':None};prefix='gutenberg-first-prose-cohort-v1-'
 previous=signal.signal(signal.SIGALRM,alarm)
 try:
  # Every finite allowance charged durably before the first HTTP operation.
  ledger.reserve(prefix+'metadata',output_bytes=2000000,body_bytes=2000000)
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
  terminal(out,'worker-result.json',{'status':'FINITE20_ATTEMPTS_TERMINAL_NO_ADMISSION','successful_raw_bodies':sum(r['error'] is None for r in records),'failed_bodies':sum(r['error'] is not None for r in records),'physical_requests':state['requests'],'records':[{'ebook_ID':r['ebook_ID'],'status':r['status'],'bytes':r['received_bytes'],'sha256':r['raw_or_partial_sha256']} for r in records],'global_reserved':ledger.totals(),'elapsed_seconds':clk()-start,'new_admitted_documents':0,'new_admitted_tokens':0})
 except BaseException as e:
  terminal(out,'worker-result.json',{'status':'PROFILE_TERMINAL_PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'completed_attempts':len(records),'physical_requests':state['requests'],'global_reserved':ledger.totals(),'new_admitted_documents':0});raise
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
 start=clk();p=verify(args.code_pins_sha256,args.profile_sha256);out=pathlib.Path(p['output'])
 if out!=ROOT/'gutenberg-first-prose-cohort-raw-v1' or out.exists():raise ValueError('fixed_output_no_retry')
 if ROOT.is_symlink() or any(x.is_symlink() for x in ROOT.rglob('*')):raise ValueError('intake_symlink')
 diskpolicy=json.loads((BASE/'disk-budget.json').read_text())
 if diskpolicy['weights_checkpoints_reserved_bytes']!=16000000000:raise ValueError('weights_policy_drift')
 if size(ROOT)+50000000>min(diskpolicy['processed_data_cap_bytes'],diskpolicy['raw_download_cap_bytes']):raise ValueError('combined_intake_cap')
 if shutil.disk_usage(ROOT).free<FREE+50000000:raise ValueError('preflight_free_reserves')
 out.mkdir()
 for name,n in SLOTS.items():
  with (out/name).open('xb') as f:f.write(b' '*n);f.flush();os.fsync(f.fileno())
 child=None;peak=0;reason=None
 def stop(s,f):raise RuntimeError('supervisor_signal_'+str(s))
 handlers={s:signal.signal(s,stop) for s in [signal.SIGINT,signal.SIGTERM]}
 try:
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
  terminal(out,'supervisor-result.json',{'status':'FINITE_PROFILE_TERMINAL_NO_ADMISSION' if done else 'PROFILE_PARTIAL_NO_RETRY','reason':reason,'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'output_bytes':size(out),'worker_receipt_sha256':sha(out/'worker-result.json'),'new_admitted_documents':0,'new_admitted_tokens':0});return 0 if done else 1
 except BaseException as e:
  if child is not None:kill(child)
  terminal(out,'supervisor-result.json',{'status':'PROFILE_PARTIAL_NO_RETRY','reason':type(e).__name__+':'+str(e)[:1500],'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'new_admitted_documents':0});raise
 finally:
  for s,h in handlers.items():signal.signal(s,h)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--worker',action='store_true');ap.add_argument('--code-pins-sha256',required=True);ap.add_argument('--profile-sha256',required=True);ap.add_argument('--supervisor-pid',type=int);ap.add_argument('--start');a=ap.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a.code_pins_sha256,a.profile_sha256);print('PREPARED_VERIFIED_NO_NETWORK')
