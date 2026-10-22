import pathlib,sys,runpy,contextlib,io,tempfile,json,urllib.error,hashlib,types,os,ssl,sqlite3,subprocess,time
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parent;D=P.parent/'gutenberg-cohort-acquisition-preparation-v2';h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert h(D/'code-pins.json')=='976da20e4cc8430d9541cac3c8556e97650f9269080a6915fbc69c8f82cc083b';assert h(D/'profile.json')=='134d7b5044319e91a016f769f7f8771bf6527868bcbf4bbac420708510a3e3ed';before={str(p):h(p) for p in D.iterdir() if p.is_file()};sys.path.insert(0,str(D));log=io.StringIO()
with contextlib.redirect_stdout(log):scope=runpy.run_path(str(D/'checks.py'),run_name='__main__')
(P/'baseline-checks.json').write_text(log.getvalue());a=scope['a'];Ledger=scope['IntakeLedger'];Response=scope['Response'];rows=[]
a.verify('976da20e4cc8430d9541cac3c8556e97650f9269080a6915fbc69c8f82cc083b','134d7b5044319e91a016f769f7f8771bf6527868bcbf4bbac420708510a3e3ed')
for label,error,redirect in [('URLError_firsthop',urllib.error.URLError('offline synthetic connection failure'),False),('Timeout_firsthop',TimeoutError('offline synthetic timeout'),False),('AbsoluteDeadline_firsthop',a.BodyDeadline('offline synthetic deadline'),False),('URLError_after_redirect',urllib.error.URLError('offline synthetic redirected-hop failure'),True)]:
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);out=root/'out';out.mkdir();ledger=Ledger(root/'ledger',{'limits':{'requests':3,'body_bytes':2400000,'rows':1,'output_bytes':2400000},'wall_seconds':30});ledger.reserve('book',body_bytes=2400000,output_bytes=2400000);state={'requests':0,'last_request':None};calls=[]
  def open_fn(opener,url,timeout):
   calls.append(url)
   if redirect and len(calls)==1:return Response(url,302,b'',{'Location':'https://www.gutenberg.org/cache/epub/123/pg123.txt'})
   raise error
  row={'ebook_ID':123,'ordinal':1,'family_component_ID':123,'frame_raw_hash':'audit_fixture','source_binding':{},'metadata_stratum':'audit_fixture','format':{'resolved_URL':'https://www.gutenberg.org/ebooks/123.txt.utf-8'}}
  with patch.object(a.time,'sleep',lambda _:None):receipt=a.transfer(row,out,ledger,'book',None,state,a.clk(),open_fn)
  snap=ledger.snapshot();assert not [x for x in snap['attempts'] if x['state']=='pending'];assert snap['reserved']['requests']==len(calls) and snap['reserved']['body_bytes']==2400000;failure=json.loads((out/('pg123-hop'+str(int(redirect))+'-failure.json')).read_text());assert failure['IO_began'] and not failure['response_headers_available'] and failure['ledger_key']=='book-hop'+str(int(redirect));rows.append({'case':label,'request_and_body_terminal_failed_no_refund':True,'hopfailure':failure,'snapshot':snap});ledger.close()
# Exercise actual worker normal/exception lifecycle using isolated ledgers and no HTTP transport.
contracts=[]
for mode in ['all20_terminal','profile_partial']:
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);out=root/'out';out.mkdir();contract={'limits':{'requests':60,'body_bytes':50000000,'rows':20,'output_bytes':50000000},'wall_seconds':30};profile={'output':str(out),'records':[{'ebook_ID':i} for i in range(1,21)]}
  for name,n in a.SLOTS.items():(out/name).write_bytes(b' '*n)
  def fake_transfer(row,out,ledger,key,opener,state,start):
   if mode=='profile_partial':raise RuntimeError('offline lifecycle interruption before bodyIO')
   ledger.finish(key,raw=None);return {'ebook_ID':row['ebook_ID'],'status':'FAILED_PARTIAL_NO_RETRY','received_bytes':0,'raw_or_partial_sha256':None,'error':'offline noHTTP fixture'}
  helper=types.SimpleNamespace(trusted_context=ssl.create_default_context);args=types.SimpleNamespace(code_pins_sha256='audit',profile_sha256='audit',start=str(a.clk()),supervisor_pid=os.getppid())
  with patch.object(a,'ROOT',root),patch.object(a,'verify',lambda *args:profile),patch.object(a,'helpers',lambda:(Ledger,contract,helper)),patch.object(a,'transfer',fake_transfer):
   try:a.worker(args)
   except RuntimeError:assert mode=='profile_partial'
  db=sqlite3.connect(root/'charges/ledger.sqlite');actual=db.execute('select key,state,actual_bytes,charge from attempts').fetchall();db.close();assert len(actual)==21 and not [x for x in actual if x[1]=='pending'];assert sum(json.loads(x[3])['body_bytes'] for x in actual)==50000000;meta=next(x for x in actual if x[0].endswith('metadata'));assert meta[1:3]==(('complete',0) if mode=='all20_terminal' else ('failed',None));receipt=json.loads((out/'worker-result.json').read_text());assert receipt['status']==('FINITE20_ATTEMPTS_TERMINAL_NO_ADMISSION' if mode=='all20_terminal' else 'PROFILE_TERMINAL_PARTIAL_NO_RETRY');contracts.append({'case':mode,'all21allocations_terminal':True,'metadata_state':meta[1],'metadata_actual_download_bytes':meta[2],'reserved_body_bytes_not_refunded':50000000,'worker_receipt_status':receipt['status']})
# Real killed child: finally cannot run; charges remain, lock releases, then explicit parent reconciliation.
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);contract={'limits':{'requests':1,'body_bytes':100,'rows':1,'output_bytes':100},'wall_seconds':30};script="import sys,time,pathlib;sys.path.insert(0,"+repr(str(a.REPO/'src'))+");from slm.data.intake_ledger import IntakeLedger;l=IntakeLedger("+repr(str(root/'ledger'))+","+repr(contract)+");l.reserve('owned-prefix-hop0',requests=1,body_bytes=100,output_bytes=100);pathlib.Path("+repr(str(root/'ready'))+").write_text('ready');time.sleep(20)";child=subprocess.Popen([sys.executable,'-c',script],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  deadline=time.monotonic()+3
  while not (root/'ready').exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.01)
  assert (root/'ready').exists();a.kill(child);assert child.poll() is not None;ledger=Ledger(root/'ledger',contract);snap=ledger.snapshot();assert snap['attempts'][0]['state']=='pending';settled=a.settle_pending(ledger,'owned-prefix-');after=ledger.snapshot();assert settled==['owned-prefix-hop0'] and after['attempts'][0]['state']=='failed' and after['reserved']==snap['reserved'];ledger.close()
 finally:
  if child.poll() is None:a.kill(child)
assert all(h(pathlib.Path(n))==d for n,d in before.items());result={'status':'PASS_FOCUSED_V2_FAILURE_ACCOUNTING_FIXES','prior_four_counterexamples_now_terminal':rows,'actual_worker_lifecycle_offline_controls':contracts,'SIGKILL_control':{'real_owned_child_killed_reaped':True,'pending_after_forced_death_expected':True,'lock_released_after_childdeath':True,'explicit_scoped_postdeath_reconciliation_works_without_refund':True,'automatic_retry':False},'baseline_controls_reproduced':20,'independent_controls':7,'preparation_unchanged':True,'network_requests':0,'global_ledger_writes':0};(P/'focused-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':'PASS','baseline':20,'independent':7,'noHTTP':True}))
