"""Offline transports only; isolated ledgers; no source body/network requests."""
import acquire as a,json,pathlib,tempfile,sys,email.message,signal,time,subprocess,os,urllib.error
sys.path.insert(0,str(a.REPO/'src'))
from slm.data.intake_ledger import IntakeLedger
from unittest.mock import patch
checks=[]
class Response:
 def __init__(self,url,status=200,body=b'English prose.',headers=None):
  self.url=url;self.code=status;self.body=body;self.pos=0;self.headers=email.message.Message()
  for k,v in (headers or {'Content-Type':'text/plain; charset=utf-8','Content-Length':str(len(body))}).items():self.headers[k]=v
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def geturl(self):return self.url
 def read1(self,n):b=self.body[self.pos:self.pos+n];self.pos+=len(b);return b

def case(name,responses,expect_success,caprequests=3):
 with tempfile.TemporaryDirectory() as t:
  root=pathlib.Path(t);out=root/'out';out.mkdir();ledger=IntakeLedger(root/'ledger',{'limits':{'requests':3,'body_bytes':2400000,'rows':1,'output_bytes':2400000},'wall_seconds':30})
  ledger.reserve('book',body_bytes=2400000,output_bytes=2400000);state={'requests':0,'last_request':None};calls=[]
  def opener(op,url,timeout):
   key='book-hop'+str(len(calls));assert ledger.db.execute('select state from attempts where key=?',(key,)).fetchone()==('pending',);calls.append(url);return responses[len(calls)-1]
  with patch.object(a.time,'sleep',lambda x:None):r=a.transfer({'ebook_ID':123,'family_component_ID':123,'frame_raw_hash':'hash','source_binding':{'member_identity':{'ordinal':1}},'primary_metadata_stratum':'proxy','source_URL':'https://www.gutenberg.org/ebooks/123.txt.utf-8'},out,ledger,'book',None,state,a.clk(),opener)
  assert (r['error'] is None)==expect_success,(name,r)
  assert len(calls)<=caprequests and ledger.totals()['requests']==len(calls)
  for res in responses:
   if res.code in [301,302,303,307,308]:assert res.pos==0
  if not expect_success and (out/'pg123.partial').exists():assert (out/'pg123.partial').stat().st_size==r['received_bytes']
  try:ledger.reserve('book',body_bytes=1)
  except ValueError:pass
  else:raise AssertionError('replay')
  ledger.close();checks.append(name)
u='https://www.gutenberg.org/ebooks/123.txt.utf-8';cache='https://www.gutenberg.org/cache/epub/123/pg123.txt'
case('successful_exact_raw_and_preIO_hop_charge',[Response(u)],True)
case('explicit_official_same_ID_redirect',[Response(u,302,b'',{'Location':cache}),Response(cache)],True)
case('third_redirect_refused_without_fourth_GET',[Response(u,302,b'not read',{'Location':cache}),Response(cache,302,b'not read',{'Location':'https://gutenberg.org/ebooks/123.txt.utf-8'}),Response('https://gutenberg.org/ebooks/123.txt.utf-8',302,b'not read',{'Location':u})],False,3)
case('offhost_redirect_refused_before_IO',[Response(u,302,b'',{'Location':'https://example.com/123'})],False,1)
case('different_ebook_redirect_refused',[Response(u,302,b'',{'Location':'https://www.gutenberg.org/ebooks/124.txt.utf-8'})],False,1)
case('nonUTF8_partial_retained',[Response(u,200,b'bad\xff')],False,1)
case('HTTP_failure_body_and_headers_retained',[Response(u,503,b'Service unavailable')],False,1)
case('cap_exact_preserved_no_EOF_overread',[Response(u,200,b'x'*2400000)],False,1)
case('truncated_advertised_body_retained',[Response(u,200,b'abc',{'Content-Type':'text/plain','Content-Length':'10'})],False,1)
# Actual pending-hop counterexamples, original and redirected attempts.
for redirected in [False,True]:
 for error_type in ['URL','timeout','deadline']:
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);out=root/'out';out.mkdir();ledger=IntakeLedger(root/'ledger',{'limits':{'requests':3,'body_bytes':2400000,'rows':1,'output_bytes':2400000},'wall_seconds':30});ledger.reserve('book',body_bytes=2400000,output_bytes=2400000);calls=[]
   def broken(op,url,timeout):
    calls.append(url)
    if redirected and len(calls)==1:return Response(u,302,b'',{'Location':cache})
    if error_type=='URL':raise urllib.error.URLError('offline mock')
    if error_type=='timeout':raise TimeoutError('offline timeout')
    raise a.BodyDeadline('offline absolute deadline')
   with patch.object(a.time,'sleep',lambda x:None):r=a.transfer({'ebook_ID':123,'family_component_ID':123,'frame_raw_hash':'hash','source_binding':{'member_identity':{'ordinal':1}},'primary_metadata_stratum':'proxy','source_URL':u},out,ledger,'book',None,{'requests':0,'last_request':None},a.clk(),broken)
   hop=int(redirected);key='book-hop'+str(hop)
   assert ledger.db.execute('select state from attempts where key=?',(key,)).fetchone()==('failed',)
   assert ledger.totals()['requests']==hop+1
   failure=json.loads((out/f'pg123-hop{hop}-failure.json').read_text());assert failure['IO_began'] and not failure['response_headers_available'] and failure['url']==(cache if redirected else u)
   assert ledger.db.execute("select count(*) from attempts where state='pending'").fetchone()==(0,)
   ledger.close();checks.append(('redirected_' if redirected else 'first_')+error_type+'_pending_hop_terminalized')
with tempfile.TemporaryDirectory() as tmp:
 ledger=IntakeLedger(pathlib.Path(tmp)/'ledger',{'limits':{'requests':3,'body_bytes':5000000,'rows':1,'output_bytes':5000000},'wall_seconds':30})
 ledger.reserve('profile-metadata',body_bytes=2000000,output_bytes=2000000);ledger.finish('profile-metadata',raw=b'');assert ledger.db.execute("select state,actual_bytes from attempts where key='profile-metadata'").fetchone()==('complete',0)
 ledger.reserve('profile-unattempted',body_bytes=2400000,output_bytes=2400000);assert a.settle_pending(ledger,'profile-')==['profile-unattempted'];assert ledger.totals()['body_bytes']==4400000;assert ledger.db.execute("select count(*) from attempts where state='pending'").fetchone()==(0,);ledger.close();checks.append('metadata_zero_download_and_partial_unattempted_failed_without_refund')
assert a.tree('1 0 2\n2 1 3\n3 2 5\n4 0 7',1)==10240;checks.append('whole_owned_process_tree_RSS')
old=signal.signal(signal.SIGALRM,a.alarm);start=time.monotonic();signal.setitimer(signal.ITIMER_REAL,.02)
try:
 try:time.sleep(.5)
 except a.BodyDeadline:assert time.monotonic()-start<.4
 else:raise AssertionError('absolute_alarm')
finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
checks.append('absolute_alarm_interrupts_blocked_operation')
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'],start_new_session=True);a.kill(p);assert p.poll() is not None;checks.append('owned_group_kill_reap')
# Digest binding rejects the original mutable-empty-registry attack before file writes.
import code_guard
try:code_guard.verify('0'*64)
except (ValueError,FileNotFoundError):checks.append('wrong_or_missing_external_registry_refused')
else:raise AssertionError('registry')
# Actual mocked worker entrypoint lifecycle: all imports/helpers preflight, full20
# attempts or a declared partial, exact supervisor-owned metadata precondition.
import types,hashlib
rows=[{'ebook_ID':12300+i,'family_component_ID':12300+i,'frame_raw_hash':'fixture','source_binding':{'member_identity':{'ordinal':i+1}},'primary_metadata_stratum':'fixture','source_URL':f'https://www.gutenberg.org/ebooks/{12300+i}.txt.utf-8','preserved_annotation':'synthetic metadata stays in receipt'} for i in range(20)]
contract={'limits':{'requests':100,'body_bytes':80000000,'rows':1,'output_bytes':80000000},'wall_seconds':60}
# Verify true production imports now (no sockets), rather than mocking helpers only.
L,C,T=a.helpers();ctx=T.trusted_context();assert ctx.check_hostname and ctx.verify_mode==a.ssl.CERT_REQUIRED;checks.append('all_runtime_helpers_and_verified_CA_preflight')
for mode in ['success','all_URL_fail','all_allowed_cache_upgrade','pin_change','missing_metadata','wrong_metadata','mid_reservation_failure','metadata_write_failure']:
 with tempfile.TemporaryDirectory() as t:
  root=pathlib.Path(t);out=root/'out';out.mkdir();lr=root/'ledger';calls=[];opened=[];active=[]
  class Local(IntakeLedger):
   def __init__(self,p,c):super().__init__(lr,contract);active.append(self)
   def reserve(self,key,**charges):
    if mode=='mid_reservation_failure' and key==a.PREFIX+str(rows[5]['ebook_ID']):raise ValueError('fixture_midreservation')
    return super().reserve(key,**charges)
  l=Local(None,None)
  if mode not in ['missing_metadata','wrong_metadata']:a.reserve_metadata(l)
  if mode=='wrong_metadata':l.reserve(a.PREFIX+'metadata',output_bytes=1,body_bytes=1)
  l.close()
  for name,n in a.SLOTS.items():(out/name).write_bytes(b' '*n)
  def verified(c,p):
   calls.append((c,p))
   if mode=='pin_change' and len(calls)==2:raise ValueError('fixture_pin_changed')
   return {'output':str(out),'records':rows}
  class Open:
   def open(self,req,timeout):
    # Durable allbook and exact physicalhop allocations must precede every IO.
    l=active[-1];assert l.db.execute("select count(*) from attempts where key like ?",(a.PREFIX+'%',)).fetchone()[0]>=22;opened.append(req.full_url)
    if mode=='all_URL_fail':raise urllib.error.URLError('fixture')
    if mode=='all_allowed_cache_upgrade' and '/ebooks/' in req.full_url:
     eid=req.full_url.split('/ebooks/')[1].split('.')[0];return Response(req.full_url,302,b'unread redirect body',{'Location':f'http://www.gutenberg.org/cache/epub/{eid}/pg{eid}.txt'})
    return Response(req.full_url)
  oldwrite=a.write
  def guarded_write(out,name,obj):
   if mode=='metadata_write_failure' and name=='reservation.json':raise OSError('fixture_metadata_write')
   return oldwrite(out,name,obj)
  with patch.object(a,'ROOT',root),patch.object(a,'verify',verified),patch.object(a,'helpers',return_value=(Local,contract,T)),patch.object(a.urllib.request,'build_opener',return_value=Open()),patch.object(a.time,'sleep',lambda x:None),patch.object(a.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)),patch.object(a,'write',guarded_write):
   args=types.SimpleNamespace(code_pins_sha256='codepin',profile_sha256='profilepin',supervisor_pid=os.getppid(),start=str(a.clk()))
   try:a.worker(args)
   except (ValueError,OSError):assert mode in ['pin_change','missing_metadata','wrong_metadata','mid_reservation_failure','metadata_write_failure']
   else:assert mode in ['success','all_URL_fail','all_allowed_cache_upgrade']
  l=Local(None,None);assert l.db.execute("select count(*) from attempts where state='pending'").fetchone()==(0,);reserved=l.totals();l.close()
  w=json.loads((out/'worker-result.json').read_text())
  assert calls[0]==('codepin','profilepin')
  if mode in ['success','all_URL_fail','all_allowed_cache_upgrade']:
   assert len(opened)==(40 if mode=='all_allowed_cache_upgrade' else 20) and w['status']=='FINITE20_ATTEMPTS_TERMINAL_NO_ADMISSION' and reserved['body_bytes']==50000000 and reserved['output_bytes']==50000000 and reserved['requests']==(40 if mode=='all_allowed_cache_upgrade' else 20)
   assert w['successful_raw_bodies']==(20 if mode in ['success','all_allowed_cache_upgrade'] else 0)
  if mode=='success':assert json.loads((out/'pg12300-receipt.json').read_text())['original_selected_metadata_record']==rows[0]
  if mode in ['missing_metadata','wrong_metadata','mid_reservation_failure','metadata_write_failure']:assert opened==[]
  checks.append('actual_worker_'+mode+'_receipt_pending_and_no_refund')
# Supervisor first-file failure and fake child entry: real temp ledger precharge
# must exist before slots/ownership and before subprocess argument dispatch.
for mode in ['slot_failure','child_failed','hardstop_pending_prefix']:
 with tempfile.TemporaryDirectory() as t:
  root=pathlib.Path(t);out=root/'out';lr=root/'ledger';seen=[]
  class Local(IntakeLedger):
   def __init__(self,p,c):super().__init__(lr,contract)
  original=pathlib.Path.open
  def opened(p,*args,**kw):
   if p.parent==out and args and args[0]=='xb':
    l=Local(None,None);a.require_metadata_pending(l);l.close()
    if mode=='slot_failure' and p.name=='worker-result.json':raise OSError('fixture_slot_failure')
   return original(p,*args,**kw)
  class Child:
   pid=12345;returncode=1
   def poll(self):return 1
   def wait(self,timeout):return 1
  def launch(cmd,**kw):
   seen.extend(cmd)
   if mode=='hardstop_pending_prefix':
    l=Local(None,None);l.reserve(a.PREFIX+'uncertain',body_bytes=2400000,output_bytes=2400000);l.close()
   return Child()
  with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'verify',return_value={'output':str(out),'records':rows}),patch.object(a,'helpers',return_value=(Local,contract,T)),patch.object(a.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)),patch.object(pathlib.Path,'open',opened),patch.object(a.subprocess,'Popen',launch):
   try:a.supervise(types.SimpleNamespace(code_pins_sha256='codepin',profile_sha256='profilepin'))
   except (OSError,ValueError):pass # blank fake child receipt is explicitly partial
  l=Local(None,None);assert l.db.execute("select count(*) from attempts where state='pending'").fetchone()==(0,);assert l.totals()['output_bytes']>=2000000;l.close()
  if mode=='slot_failure':assert seen==[]
  else:assert seen[seen.index('--code-pins-sha256')+1]=='codepin' and seen[seen.index('--profile-sha256')+1]=='profilepin'
  checks.append('supervisor_'+mode+'_precharged_closed_and_postreaped_cleanup')
# Invalid/mutable manifest and runtime controls, exact-inventory and dependency pins.
with tempfile.TemporaryDirectory() as t:
 h=pathlib.Path(t);f=h/'input';f.write_bytes(b'original');manifest=h/'code-pins.json'
 def save(x):manifest.write_text(json.dumps(x));return sha(manifest)
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 good={'runtime':a.runtime(),'sha256':{str(f):sha(f)}}
 with patch.object(code_guard,'HERE',h),patch.object(a,'bound_inventory',return_value={str(f)}):
  code_guard.verify(save(good));checks.append('exact_inventory_runtime_pin')
  for name,obj in [('empty_inventory',{'runtime':a.runtime(),'sha256':{}}),('wrong_runtime',{'runtime':{},'sha256':good['sha256']})]:
   try:code_guard.verify(save(obj))
   except ValueError:checks.append(name+'_refused')
   else:raise AssertionError(name)
  pin=save(good);f.write_bytes(b'changed')
  try:code_guard.verify(pin)
  except ValueError:checks.append('actual_dependency_tamper_refused')
  else:raise AssertionError('tamper')
# New-cohort predeclared scheme-only mapping: rawLocation bound before follow.
allowed='http://www.gutenberg.org/cache/epub/123/pg123.txt'
dec=a.redirect_decision(u,allowed,123);assert dec['allowed'] and dec['next_HTTPS_URL']==cache and dec['captured_Location_verbatim']==allowed and not dec['HTTP_transport_permitted'];checks.append('exact_captured_HTTP_cache_Location_only_scheme_upgraded')
for name,location in [('host','http://gutenberg.org/cache/epub/123/pg123.txt'),('offhost','http://example.com/cache/epub/123/pg123.txt'),('ID','http://www.gutenberg.org/cache/epub/124/pg124.txt'),('query',allowed+'?download=1'),('fragment',allowed+'#x'),('path','http://www.gutenberg.org/ebooks/123.txt.utf-8'),('port','http://www.gutenberg.org:80/cache/epub/123/pg123.txt'),('userinfo','http://user@www.gutenberg.org/cache/epub/123/pg123.txt'),('padded',' '+allowed),('encoded_path','http://www.gutenberg.org/cache/epub/123/pg%31%32%33.txt')]:
 d=a.redirect_decision(u,location,123);assert not d['allowed'] and d['next_HTTPS_URL'] is None;checks.append('unknown_HTTP_'+name+'_HELD')
case('actual_transfer_predeclared_exact_HTTPcache_upgrade',[Response(u,302,b'never read',{'Location':allowed}),Response(cache)],True,2)
case('actual_transfer_HTTP_unknown_path_hold',[Response(u,302,b'never read',{'Location':'http://www.gutenberg.org/ebooks/123.txt.utf-8'})],False,1)
dup=Response(u,302,b'never read',{'Location':allowed});dup.headers['Location']=allowed;case('duplicate_Location_held_before_follow',[dup],False,1)
# V3 shared external watchdog includes genuinely blocked preflight before mutation.
for stage in ['pin_verify','TLS_helpers','disk_preflight']:
 with tempfile.TemporaryDirectory() as t:
  root=pathlib.Path(t);out=root/'out';events=[];handlers={sig:signal.getsignal(sig) for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGALRM]}
  def blocked(*args,**kw):events.append(stage);time.sleep(2);raise AssertionError('watchdog failed')
  def forbidden(*args,**kw):raise AssertionError('no IO ledger metadata reserve cleanup or child permitted')
  verified=blocked if stage=='pin_verify' else lambda *args,**kw:{'output':str(out)}
  helper=blocked if stage=='TLS_helpers' else lambda *args,**kw:None
  disk=blocked if stage=='disk_preflight' else lambda *args,**kw:types.SimpleNamespace(free=10**15)
  begun=a.clk()
  with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'CAPS',dict(a.CAPS,external_seconds=.05)),patch.object(a,'verify',verified),patch.object(a,'helpers',helper),patch.object(a.shutil,'disk_usage',disk),patch.object(a,'supervisor_reserve_metadata',forbidden),patch.object(a,'cleanup_owned',forbidden),patch.object(a.subprocess,'Popen',forbidden):
   try:a.supervise(types.SimpleNamespace(code_pins_sha256='x',profile_sha256='y'))
   except RuntimeError as e:assert 'supervisor_signal_' in str(e)
   else:raise AssertionError('blocked preflight did not stop')
  assert events==[stage] and .02<=a.clk()-begun<1 and not out.exists() and not (root/'charges').exists()
  checks.append('actual50ms_alarm_stops_blocked_'+stage+'_before_IO_ledger_output')
  assert signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0) and all(signal.getsignal(sig)==h for sig,h in handlers.items());checks.append(stage+'_refusal_restores_handlers_and_cancels_timer')
for refusal_mode in ['pin_refusal','existing_output_refusal']:
 with tempfile.TemporaryDirectory() as t:
  root=pathlib.Path(t);out=root/'existing';out.mkdir();sentinel=out/'supervisor-result.json';sentinel.write_bytes(b'FROZEN_UNRELATED_PRIOR_EVIDENCE')
  def verified(*args,**kw):
   if refusal_mode=='pin_refusal':raise ValueError('pinned_preflight_refusal')
   return {'output':str(out)}
  def forbidden(*args,**kw):raise AssertionError('uncharged preflight must not reserve/reconcile/start child')
  with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'verify',verified),patch.object(a,'helpers',return_value=None),patch.object(a,'supervisor_reserve_metadata',forbidden),patch.object(a,'cleanup_owned',forbidden),patch.object(a.subprocess,'Popen',forbidden):
   try:a.supervise(types.SimpleNamespace(code_pins_sha256='x',profile_sha256='y'))
   except ValueError:pass
   else:raise AssertionError('preflight refused')
  assert sentinel.read_bytes()==b'FROZEN_UNRELATED_PRIOR_EVIDENCE' and sorted(q.name for q in out.iterdir())==['supervisor-result.json'] and not (root/'charges').exists();checks.append(refusal_mode+'_preserves_existing_OUT_and_unrelated_ledger')
with tempfile.TemporaryDirectory() as t:
 root=pathlib.Path(t)
 with patch.object(a,'ROOT',root),patch.object(a,'OUT',root/'out'),patch.object(a,'CAPS',dict(a.CAPS,external_seconds=1)),patch.object(a,'clk',side_effect=[10,12]),patch.object(a,'verify',side_effect=AssertionError('expired_beforeverify')),patch.object(a,'cleanup_owned',side_effect=AssertionError('uncharged_cleanup')):
  try:a.supervise(types.SimpleNamespace(code_pins_sha256='x',profile_sha256='y'))
  except TimeoutError:pass
  else:raise AssertionError('no fresh expired allowance')
 assert not (root/'out').exists();checks.append('already_aged_shared_start_refuses_before_verify_no_fresh_allowance')
print(json.dumps({'status':'PASS_OFFLINE_ONLY_ACTUAL_MOCKED_WORKER_LIFECYCLES','count':len(checks),'checks':checks,'network_requests':0,'global_ledger_writes':0},indent=2))
