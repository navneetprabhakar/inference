"""Isolated ledger and loopback fixtures only; never contacts a public source."""
import functools,gzip,hashlib,json,os,socket,sqlite3,subprocess,sys,tempfile,threading,time,types,signal
from pathlib import Path
from unittest.mock import patch
import controller,transport,validate,sandbox,run
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'src'))
from slm.data.intake_ledger import IntakeLedger
N=[]
def test(name,fn):fn();N.append(name)
def must(fn):
 try:fn()
 except Exception as e:return e
 raise AssertionError('must refuse')
CONTRACT={'version':1,'limits':{'requests':1000,'body_bytes':1000000000,'output_bytes':1000000000,'rows':1000000},'wall_seconds':600}
def planned(eid,i):return {'ordinal':i,'ebook_ID':eid,'module':'gutenberg-epub','source_relative_path':transport.path_for(eid),'native_catalog_URL':f'https://www.gutenberg.org/ebooks/{eid}.txt.utf-8','source_row_SHA256':'a'*64,'family_component_ID':eid}
def fixture(root,n):
 ledger=IntakeLedger(root/'ledger',CONTRACT);ledger.reserve('pg-output',output_bytes=800000000);out=root/'out';out.mkdir();return ledger,out,{'records':[planned(123+i,i) for i in range(n)],'ledger_prefix':'pg-'}
def checker(*a,**kw):pass
def missing(eid,*args,**kw):
 receipt={'exit_code':23,'stdout':'','stderr':f"rsync(1): error: '{eid}/pg{eid}.txt': (l)stat: No such file or directory\n",'received_bytes':5,'remote_started':False};return receipt,b'proto'
def ledger_policy():
 with tempfile.TemporaryDirectory() as z:
  ledger,out,p=fixture(Path(z),4)
  try:
   e=must(lambda:controller.execute(p,out,ledger,checker,transfer=missing,pace=lambda n:None));assert isinstance(e,controller.PolicyStop) and e.profile_partial['unattempted_ordinals']==[3]
   rows=ledger.db.execute("select key,state from attempts order by key").fetchall();assert rows==[('pg-body-000','failed'),('pg-body-001','failed'),('pg-body-002','failed'),('pg-output','pending')]
   assert ledger.totals()['body_bytes']==7500000 and ledger.totals()['requests']==3 and not (out/'attempt-003').exists()
  finally:ledger.close()
test('integrated isolated durableledger exact3failurestop/allcharges/no fourthattempt',ledger_policy)
def fatal():
 with tempfile.TemporaryDirectory() as z:
  ledger,out,p=fixture(Path(z),3)
  try:
   def fail(*a,**kw):raise transport.ProtocolError('synthetic protocol')
   e=must(lambda:controller.execute(p,out,ledger,checker,transfer=fail,pace=lambda n:None));assert isinstance(e,transport.ProtocolError) and ledger.totals()['requests']==1 and len(list(out.glob('attempt-*')))==1 and ledger.db.execute("select state from attempts where key='pg-body-000'").fetchone()==('failed',)
  finally:ledger.close()
test('protocolfatal immediate/no retry pendingcharge settled',fatal)
def resource():
 with tempfile.TemporaryDirectory() as z:
  ledger,out,p=fixture(Path(z),2)
  def cap(*a,**kw):
   if kw.get('extra'):raise ValueError('resourcecap')
  try:
   e=must(lambda:controller.execute(p,out,ledger,cap,transfer=lambda *a:(_ for _ in ()).throw(AssertionError('no network'))));assert ledger.totals()['requests']==1 and ledger.db.execute("select state from attempts where key='pg-body-000'").fetchone()==('failed',) and not list(out.iterdir())
  finally:ledger.close()
test('preIO resourcefailure retainscharge andnever starts network',resource)
def ledger_failure():
 with tempfile.TemporaryDirectory() as z:
  ledger,out,p=fixture(Path(z),1);ledger.reserve('pg-body-000',requests=1,body_bytes=2500000)
  try:must(lambda:controller.execute(p,out,ledger,checker,transfer=lambda *a:(_ for _ in ()).throw(AssertionError('no network'))));assert not list(out.iterdir()) and ledger.db.execute("select count(*) from attempts where key='pg-body-000'").fetchone()==(1,)
  finally:ledger.close()
test('duplicate durablecharge prevents replay beforeanyfiles/sourceIO',ledger_failure)
def timeout():
 with tempfile.TemporaryDirectory() as z:
  ledger,out,p=fixture(Path(z),4)
  try:
   def fail(*a,**kw):e=transport.IndependentTimeout('synthetic');e.transport_receipt={'received_bytes':5,'remote_started':False};raise e
   must(lambda:controller.execute(p,out,ledger,checker,transfer=fail,pace=lambda n:None));assert ledger.totals()['requests']==3 and len(list(out.glob('attempt-*/receipt.json')))==3
  finally:ledger.close()
test('independent timeout finite3stop no replacement',timeout)
def argv():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z);f=root/'f';f.write_bytes(b'123/pg123.txt\0');args=transport.argv(123,1234,f,root);assert args[-2]=='rsync://127.0.0.1/gutenberg-epub/123/pg123.txt' and all(x not in args for x in ['-r','-a','--delete','--copy-links','--compress'])
  for eid in ['../1',-1,True,100000000]:must(lambda:transport.path_for(eid))
  f.write_bytes(b'123/pg123.txt\0../other\0');must(lambda:transport.argv(123,1234,f,root))
test('literalexactfileargv/no broadflags/no declarationinjection',argv)
def pathguards():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z);outside=p/'outside';outside.write_bytes(b'KEEP');stage=p/'stage';stage.mkdir();(stage/'pg123.txt').symlink_to(outside);must(lambda:validate.result(stage,123,{'exit_code':0,'stdout':'','stderr':''}));assert outside.read_bytes()==b'KEEP'
  (stage/'pg123.txt').unlink();(stage/'unexpected').write_bytes(b'x');must(lambda:validate.result(stage,123,{'exit_code':0,'stdout':'','stderr':''}))
 with tempfile.TemporaryDirectory() as z:must(lambda:validate.result(z,123,{'exit_code':0,'stdout':'','stderr':''}))
test('symlink/unexpectedpath/exit0empty refusals preserve outsidefile',pathguards)
def confinement():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z).resolve();stage=p/'stage';stage.mkdir();f=p/'file';f.write_bytes(b'123/pg123.txt\0');sb=p/'policy.sb';sb.write_text(sandbox.policy(stage,f,1234));outside=p/'outside'
  x=subprocess.run(['/usr/bin/sandbox-exec','-f',str(sb),'/usr/bin/touch',str(outside)],capture_output=True,timeout=3);assert x.returncode and not outside.exists()
  x=subprocess.run(['/usr/bin/sandbox-exec','-f',str(sb),'/usr/bin/touch',str(stage/'inside')],capture_output=True,timeout=3);assert x.returncode==0 and (stage/'inside').exists()
test('actualmacOSsandbox writesconfinedstage/outsidewrite blocked',confinement)
def local_integrated():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();src=root/'src';src.mkdir()
  for eid in [123,124]:(src/str(eid)).mkdir();(src/str(eid)/f'pg{eid}.txt').write_bytes((f'Synthetic whole story {eid}.\n'*100).encode());(src/str(eid)/'secret.txt').write_bytes(b'NO')
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();cfg=root/'daemon.conf';cfg.write_text(f'use chroot = no\nuid = {os.getuid()}\ngid = {os.getgid()}\n[gutenberg-epub]\npath = {src}\nread only = yes\n');daemon=subprocess.Popen(['/usr/bin/rsync','--daemon','--no-detach','--config='+str(cfg),'--port='+str(port),'--address=127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  ledger,out,p=fixture(root,2)
  try:
   time.sleep(.1);starts=[]
   def xfer(*a,**kw):starts.append(transport.clk());return transport.transfer(*a,**kw,connector=lambda:socket.create_connection(('127.0.0.1',port),timeout=1))
   r=controller.execute(p,out,ledger,checker,transfer=xfer,pace=lambda n:None);assert r['completed']==2 and r['attempted']==2 and r['received_application_bytes']<10000
   for i,eid in enumerate([123,124]):
    stage=out/f'attempt-{i:03}'/'raw';assert (stage/f'pg{eid}.txt').read_bytes()==(src/str(eid)/f'pg{eid}.txt').read_bytes() and len(list(stage.iterdir()))==1
   assert ledger.db.execute("select count(*) from attempts where state='complete'").fetchone()==(2,) and ledger.totals()['body_bytes']==5000000
   assert all(json.loads((out/f'attempt-{i:03}/receipt.json').read_text())['charged_before_IO'] for i in range(2))
   inv=controller.inventory(out,checker);assert len(inv['artifacts'])==8
  finally:ledger.close();daemon.kill();daemon.wait(timeout=2)
test('actualLOCALnative+ownedrelay+sandbox+durableledger2bookwholehash/selectivity/reap/inventory',local_integrated)
def bytecap():
 listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);port=listener.getsockname()[1]
 def send():
  c,_=listener.accept()
  try:c.sendall(b'x'*100000)
  except OSError:pass
  finally:c.close();listener.close()
 t=threading.Thread(target=send);t.start();relay=transport.Relay(transport.clk()+3,checker,connector=lambda:socket.create_connection(('127.0.0.1',port),timeout=1),received_cap=5000,authenticate=lambda *a:None);relay.start();client=socket.create_connection(('127.0.0.1',relay.port));client.settimeout(3)
 try:
  while client.recv(65536):pass
 finally:client.close();relay.close();t.join(timeout=2)
 assert isinstance(relay.error,transport.TransferLimit) and len(relay.received)==5000 and not relay.thread.is_alive()
test('actualloopback receivehardcap beforeforwarding noEOFclaim',bytecap)
def cleanup_error():
 class Fake:
  pid=999999;stdout=None;stderr=None
  def poll(self):return None
  def wait(self,timeout):raise subprocess.TimeoutExpired('fixture',timeout)
 # Cleanup path always closes relay even when nativekill or wait fails.
 with tempfile.TemporaryDirectory() as z:
  p=Path(z);(p/'f').write_bytes(b'123/pg123.txt\0');closed=[]
  with patch.object(transport.subprocess,'Popen',return_value=Fake()),patch.object(transport.os,'killpg',side_effect=PermissionError('fixture')),patch.object(transport.Relay,'close',lambda self:closed.append(True)):
   must(lambda:transport.transfer(123,p/'f',p,transport.clk()+.05,lambda *a:(_ for _ in ()).throw(ValueError('stop before assign'))))
  assert closed
test('nativecleanupfailure still executes relaycleanup',cleanup_error)
def threadguard():
 with tempfile.TemporaryDirectory() as z:
  ledger,out,p=fixture(Path(z),1);owner=threading.get_ident();seen=[]
  def check(*a,**kw):
   if not kw.get('register_only'):assert threading.get_ident()==owner
   if kw.get('pid'):seen.append(kw['pid'])
  def mock(eid,f,stage,deadline,callback):
   failures=[]
   def call():
    try:callback(12345)
    except Exception as e:failures.append(e)
   t=threading.Thread(target=call);t.start();t.join();assert not failures
   return missing(eid)
  try:controller.execute(p,out,ledger,check,transfer=mock)
  finally:ledger.close()
  assert seen==[12345]
test('relaythread only ownershipregistration no SQLite/resourcechecks',threadguard)
def early():
 old=run.START;run.START=run.clk()-21594.98
 try:
  signal.setitimer(signal.ITIMER_REAL,.02)
  with patch.object(run,'verify',lambda a:time.sleep(.1)):must(lambda:run.execute(types.SimpleNamespace()))
 finally:run.START=old;signal.setitimer(signal.ITIMER_REAL,0)
 with tempfile.TemporaryDirectory() as z:
  out=Path(z);(out/'old').write_bytes(b'KEEP')
  with patch.object(run,'verify',lambda a:{'output':str(out)}):must(lambda:run.execute(types.SimpleNamespace()))
  assert (out/'old').read_bytes()==b'KEEP' and len(list(out.iterdir()))==1
test('earlyglobalpreflightalarm and oldOUT preserved withoutledgeropen',early)
def actual_timeout():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z).resolve();stage=p/'stage';stage.mkdir();f=p/'file';f.write_bytes(b'123/pg123.txt\0');listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);port=listener.getsockname()[1]
  def stall():
   c,_=listener.accept();time.sleep(.5);c.close();listener.close()
  t=threading.Thread(target=stall);t.start();begin=transport.clk()
  e=must(lambda:transport.transfer(123,f,stage,begin+.2,checker,connector=lambda:socket.create_connection(('127.0.0.1',port),timeout=1)))
  t.join(timeout=2);assert isinstance(e,transport.IndependentTimeout) and e.transport_receipt['child_reaped'] and transport.clk()-begin<2,(type(e).__name__,str(e),getattr(e,'transport_receipt',None))
  try:os.kill(e.transport_receipt['child_PID'],0)
  except ProcessLookupError:pass
  else:raise AssertionError('nativechildalive')
test('actualsandboxesnative stalledhandshake perfiledeadline kills/reaps/relaycloses',actual_timeout)
def DNS_timeout():
 relay=transport.Relay(transport.clk()+.1,checker);real=transport.subprocess.Popen;children=[]
 def child(*a,**kw):
  p=real([sys.executable,'-I','-S','-c','import time;time.sleep(10)'],stdout=subprocess.PIPE,stderr=subprocess.PIPE);children.append(p);return p
 try:
  with patch.object(transport.subprocess,'Popen',child):e=must(relay.resolve)
  assert isinstance(e,transport.IndependentTimeout) and children[0].poll() is not None and relay.resolver is None
 finally:relay.listener.close()
test('actualownedDNSsubprocess deadline kills/reaps before sourceconnect',DNS_timeout)
def whole_runner():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();intake=root/'intake';intake.mkdir();src=root/'src';src.mkdir();(src/'123').mkdir();(src/'123/pg123.txt').write_bytes(b'Whole integrated local story.\n'*100)
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();cfg=root/'daemon.conf';cfg.write_text(f'use chroot = no\nuid = {os.getuid()}\ngid = {os.getgid()}\n[gutenberg-epub]\npath = {src}\nread only = yes\n');daemon=subprocess.Popen(['/usr/bin/rsync','--daemon','--no-detach','--config='+str(cfg),'--port='+str(port),'--address=127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  out=intake/'out';profile={'output':str(out),'records':[planned(123,0)],'ledger_prefix':'integrated-'};original=controller.execute
  def local_execute(p,out,ledger,check):
   return original(p,out,ledger,check,transfer=lambda *a,**kw:transport.transfer(*a,**kw,connector=lambda:socket.create_connection(('127.0.0.1',port),timeout=1)))
  try:
   time.sleep(.1)
   with patch.object(run,'ROOT',intake),patch.object(run,'verify',lambda a:profile),patch.object(run,'helpers',lambda:(IntakeLedger,CONTRACT)),patch.object(controller,'execute',local_execute):assert run.execute(types.SimpleNamespace(profile_sha256='p',code_pins_sha256='c'))==0
   result=json.loads((out/'result.json').read_text());assert result['completed']==1 and result['attempted']==1
   owner=json.loads((out/'ownership.json').read_text());assert owner['active_owned_PIDs']=={}
   inv=json.loads((out/'inventory.json').read_text());assert any(r['path']=='attempt-000/raw/pg123.txt' for r in inv['artifacts'])
   db=sqlite3.connect(intake/'charges/ledger.sqlite');assert db.execute("select key,state from attempts order by key").fetchall()==[('integrated-body-000','complete'),('integrated-output','complete')];db.close()
  finally:daemon.kill();daemon.wait(timeout=2)
test('actualfullrunner precharge/output/ownershipclear/terminalinventory/ledgercomplete LOCALonly',whole_runner)
print(json.dumps({'status':'PASS_LOCAL_ONLY_NO_REMOTE_OR_GLOBAL_LEDGER','controls':len(N),'names':N,'public_source_connections':0,'global_ledger_writes':0,'real_book_bodies_read':0},indent=2))
