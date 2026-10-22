"""Offline mock responses/temp ledger only. No network/globalledger writes."""
import pathlib,tempfile,json,types,os,email.message,hashlib,signal,time,sys,urllib.error
from unittest.mock import patch
import acquire as a
sys.path.insert(0,str(a.REPO/'src'));from slm.data.intake_ledger import IntakeLedger
CONTRACT={'version':1,'scope':'synthetic metadata tests','limits':{'requests':100,'body_bytes':2000000,'rows':100,'output_bytes':16000000},'wall_seconds':3600,'minimum_free_disk_bytes':1,'paid_budget':0};checks=[]
def reject(name,fn,errors=(ValueError,OSError,RuntimeError)):
 try:fn()
 except errors:checks.append(name)
 else:raise AssertionError(name)
class Response:
 def __init__(self,url,body=b'{}',code=200,encoding=None,length=None):
  self.url=url;self.body=body;self.code=code;self.pos=0;self.read_calls=0;self.headers=email.message.Message()
  if length is not None:self.headers['Content-Length']=str(length)
  if encoding:self.headers['Content-Encoding']=encoding
 def geturl(self):return self.url
 def read1(self,n):self.read_calls+=1;b=self.body[self.pos:self.pos+n];self.pos+=len(b);return b
 def __enter__(self):return self
 def __exit__(self,*x):pass
class Opener:
 def __init__(self,fn):self.fn=fn;self.opens=[]
 def open(self,req,timeout):self.opens.append(req.full_url);return self.fn(req.full_url)
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td).resolve();clock=[100.0]
 def sleep(n):clock[0]+=n
 with patch.object(a,'ROOT',root),patch.object(a,'clk',side_effect=lambda:clock[0]),patch.object(a.time,'sleep',sleep),patch.object(a,'disk',return_value=None):
  for mode in ['success','oversize','redirect','encoding','advertised_overcap','URLError','socket_timeout']:
   out=root/mode;out.mkdir();ledger=IntakeLedger(root/('ledger-'+mode),CONTRACT);item={'key':'fixture','url':'https://example.invalid/only-metadata','response_body_cap':4};state={'requests':0,'body_bytes':0,'last_start':None,'current_attempt':None}
   response=Response(item['url'],b'1234',code=302 if mode=='redirect' else 200,encoding='gzip' if mode=='encoding' else None,length=99 if mode=='advertised_overcap' else None)
   if mode=='oversize':response.body=b'123456789'
   def op(url):
    # Actual durable requestcharge MUSTexist before mocknetworkopener entry.
    key=a.KEY+'-request-fixture';row=ledger.db.execute('select charge,state from attempts where key=?',(key,)).fetchone();assert row and row[1]=='pending' and json.loads(row[0])['requests']==1
    if mode=='URLError':raise urllib.error.URLError('offlinefixture')
    if mode=='socket_timeout':raise TimeoutError('offlinefixture')
    return response
   opener=Opener(op)
   with patch.object(a,'OUT',out):r=a.attempt(item,ledger,opener,state,100)
   assert len(opener.opens)==state['requests']==1 and ledger.db.execute('select state from attempts').fetchone()[0]==('complete' if mode=='success' else 'failed')
   if mode=='success':assert r['received_body_bytes']==4 and (out/r['file']).read_bytes()==b'1234' and response.read_calls==2
   elif mode=='oversize':assert r['received_body_bytes']==5 and (out/r['file']).stat().st_size==5
   elif mode in ['redirect','encoding','advertised_overcap']:assert response.read_calls==0
   assert ledger.db.execute("select count(*) from attempts where state='pending'").fetchone()[0]==0;checks.append('actual_attempt_'+mode+'_bounded_durable_charge_and_terminal')
   ledger.close()
  # Complete actualworker9 lifecycle againsttemp ledger andmockHTTP, no actualmetadata/body.
  out=root/'worker9';out.mkdir()
  for n,z in a.SLOTS.items():(out/n).write_bytes(b' '*z)
  dbroot=root/'charges';ledger=IntakeLedger(dbroot,CONTRACT);ledger.reserve(a.KEY,output_bytes=8000000);ledger.close();clock[0]=100
  opened=[]
  def op(url):
   opened.append(url);return Response(url,b'{}',length=2)
  opener=Opener(op);TLS=types.SimpleNamespace(CA_SHA256='0'*64,trusted_context=lambda:None);args=types.SimpleNamespace(start='100',supervisor_pid=os.getppid(),code_pins_sha256='C',profile_sha256='P')
  with patch.object(a,'OUT',out),patch.object(a,'helpers',return_value=(IntakeLedger,CONTRACT,TLS)),patch.object(a,'verify',return_value={}),patch.object(a.urllib.request,'build_opener',return_value=opener):a.worker(args)
  result=json.loads((out/'worker-result.json').read_text());assert result['physical_requests']==9 and result['successes']==9 and result['actual_response_body_bytes']==18 and opened==[v['url'] for v in a.ITEMS]
  starts=[v['physical_start_monotonic'] for v in result['records']];assert all(b-c>=1 for c,b in zip(starts,starts[1:]));checks.append('actual_worker_exact9_serialstarts_no_redirect_or_followup')
  ledger=IntakeLedger(dbroot,CONTRACT);assert ledger.db.execute("select count(*) from attempts where state='pending'").fetchone()[0]==0;assert ledger.db.execute('select state,actual_bytes from attempts where key=?',(a.KEY,)).fetchone()==('complete',0);checks.append('output_precharge_finished_complete0body_not_generated_headers');ledger.close()
  # Pending failed operations only exactownedkeys are settled; unrelatedkey preserved.
  ledger=IntakeLedger(root/'cleanup-fixture',CONTRACT);ledger.reserve(a.KEY,output_bytes=8000000);ledger.reserve(a.REQUEST_KEYS[0],requests=1,body_bytes=100);ledger.reserve('unrelated',requests=1,body_bytes=100);settled=a.settle(ledger);assert settled['pending_owned']==0 and ledger.db.execute('select state from attempts where key="unrelated"').fetchone()==('pending',);checks.append('settlement_exact_owned_keys_only_no_refund');ledger.close()
# Actualearlypreflightalarm and oldoutputpreservation, no ledger/networkopener.
args=types.SimpleNamespace(code_pins_sha256='C',profile_sha256='P')
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);out=root/'out';oldtimer=a.signal.setitimer
 def timer(which,seconds,*x):return oldtimer(which,.03 if seconds>100 else seconds,*x)
 with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'verify',side_effect=lambda *x:time.sleep(.2)),patch.object(a.signal,'setitimer',timer),patch.object(a,'helpers',side_effect=AssertionError('no ledger/helpers before blockedpreflight')):reject('actual_blocked_preflight_alarm_before_IO_ledger_OUT',lambda:a.supervise(args),a.ProfileDeadline)
 assert not out.exists()
 out.mkdir();(out/'frozen').write_bytes(b'unchanged');before=(out/'frozen').stat()
 with patch.object(a,'OUT',out),patch.object(a,'verify',return_value={}),patch.object(a,'helpers',return_value=(None,None,None)),patch.object(a,'cleanup',side_effect=AssertionError('unchargedcleanupforbidden')):reject('existing_frozen_OUT_refused_without_ledger_cleanup',lambda:a.supervise(args))
 assert (out/'frozen').read_bytes()==b'unchanged' and (out/'frozen').stat()==before and len(list(out.iterdir()))==1
# Nonblocking globalwriter lock proves no profileoutput or network beforeexclusiveownership.
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td).resolve();out=root/'new';ledger=IntakeLedger(root/'charges',CONTRACT)
 with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'verify',return_value={}),patch.object(a,'disk',return_value=None),patch.object(a,'helpers',return_value=(IntakeLedger,CONTRACT,None)),patch.object(a,'cleanup',side_effect=AssertionError('unallocatedcleanupforbidden')):
  reject('actual_busy_temp_globalwriter_refuses_before_OUT_and_request',lambda:a.supervise(args),BlockingIOError)
 assert not out.exists();ledger.close()
# Actual supervisor outputallocation precedes every profilefile, survives launchfailure.
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td).resolve();out=root/'new'
 def failed_spawn(*x,**kw):
  ledger=IntakeLedger(root/'charges',CONTRACT)
  try:
   row=ledger.db.execute('select charge,state from attempts where key=?',(a.KEY,)).fetchone();assert row and row[1]=='pending' and json.loads(row[0])=={'requests':0,'body_bytes':0,'rows':0,'output_bytes':8000000}
  finally:ledger.close()
  assert out.exists();raise OSError('synthetic launchfailure')
 with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'verify',return_value={}),patch.object(a,'disk',return_value=None),patch.object(a,'helpers',return_value=(IntakeLedger,CONTRACT,None)),patch.object(a.subprocess,'Popen',failed_spawn):reject('actual_supervisor_precharged8MB_before_file_and_launch_failure_settled',lambda:a.supervise(args),OSError)
 ledger=IntakeLedger(root/'charges',CONTRACT)
 assert ledger.db.execute('select state from attempts where key=?',(a.KEY,)).fetchone()==('failed',) and ledger.totals()['requests']==0 and ledger.totals()['body_bytes']==0 and ledger.totals()['output_bytes']==8000000
 ledger.close();assert json.loads((out/'supervisor-result.json').read_text())['status']=='PARTIAL_METADATA_PROFILE_NO_RETRY'
# ReviewedstrictRSS parser must never return0 for unverifiable snapshots.
for s in ['',f'{os.getpid()} 1 0\n',f'{os.getpid()} 1 42\nmalformed\n',f'{os.getpid()} 1 42\n{os.getpid()} 1 42\n']:reject('strict_RSS_fault_'+str(len(checks)),lambda s=s:a.process_tree_rss(s,os.getpid()))
assert a.process_tree_rss('100 1 4\n101 100 5\n',100,101)==9*1024;checks.append('strict_RSS_root_liveworker_exact_tree')
assert a.NoRedirect().redirect_request(None,None,None,None,None,None) is None;checks.append('NoRedirect_never_generates_followup_Request')
assert len(a.ITEMS)==9 and sum(v['response_body_cap']+1 for v in a.ITEMS)==901129 and a.CAPS['output_bytes']==8000000;checks.append('exact9_caps_plus9_EOF_probes_and8MBoutput')
print(json.dumps({'status':'PASS_OFFLINE_MOCKHTTP_TEMPLEDGER_ONLY','count':len(checks),'checks':checks,'network_requests':0,'global_ledger_writes':0,'actual_metadata_or_corpus_fetch':0},indent=2))
