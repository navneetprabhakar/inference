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
  with patch.object(a.time,'sleep',lambda x:None):r=a.transfer({'ebook_ID':123,'ordinal':1,'family_component_ID':123,'frame_raw_hash':'hash','source_binding':{},'metadata_stratum':'proxy','format':{'resolved_URL':'https://www.gutenberg.org/ebooks/123.txt.utf-8'}},out,ledger,'book',None,state,a.clk(),opener)
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
   with patch.object(a.time,'sleep',lambda x:None):r=a.transfer({'ebook_ID':123,'ordinal':1,'family_component_ID':123,'frame_raw_hash':'hash','source_binding':{},'metadata_stratum':'proxy','format':{'resolved_URL':u}},out,ledger,'book',None,{'requests':0,'last_request':None},a.clk(),broken)
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
print(json.dumps({'status':'PASS_OFFLINE_ONLY','count':len(checks),'checks':checks,'network_requests':0},indent=2))
