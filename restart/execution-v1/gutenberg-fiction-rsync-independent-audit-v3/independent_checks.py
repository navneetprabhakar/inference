"""Synthetic temporary files/loopback only; no public network or global ledger."""
import sys,signal,json,subprocess,socket,tempfile,time,os,hashlib
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parents[1]/'gutenberg-fiction-rsync-executor-preparation-v3'
sys.path.insert(0,str(P))
import transport,sandbox,validate
N=[]
def must(fn):
 try:fn()
 except Exception as e:return e
 raise AssertionError('expected refusal')
def test(n,f):f();N.append(n)
def resolver_guard():
 class Fake:
  pid=999998;returncode=0
  def poll(self):return 0
  def wait(self,timeout):return 0
  def communicate(self,timeout):return self.out,b''
 for values in [ [[2,1,6,'',['127.0.0.1',873]]], [[2,1,6,'',['8.8.8.8',874]]], [[2,2,17,'',['8.8.8.8',873]]], [], [[2,1,6,'',['169.254.169.254',873]]], [[10,1,6,'',['::1',873,0,0]]] ]:
  x=Fake();x.out=json.dumps(values).encode();relay=transport.Relay(transport.clk()+1,lambda *a:None)
  try:
   with patch.object(transport.subprocess,'Popen',return_value=x):assert isinstance(must(relay.resolve),transport.ProtocolError)
   assert relay.resolver is None and not relay.remote_started
  finally:relay.listener.close()
test('private/misdirected/malformed DNS values refuse without source connection',resolver_guard)
def sandbox_read_network():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z).resolve();stage=p/'stage';stage.mkdir();decl=p/'decl';decl.write_bytes(b'123/pg123.txt\0');outside=p/'secret';outside.write_bytes(b'SYNTHETIC_NOT_SECRET')
  listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);wrong=listener.getsockname()[1];allowed=wrong+1 if wrong<65535 else wrong-1;sb=p/'p.sb';sb.write_text(sandbox.policy(stage,decl,allowed))
  try:
   r=subprocess.run(['/usr/bin/sandbox-exec','-f',str(sb),'/bin/cat',str(outside)],capture_output=True,timeout=3);assert r.returncode and b'SYNTHETIC_NOT_SECRET' not in r.stdout
   r=subprocess.run(['/usr/bin/sandbox-exec','-f',str(sb),'/usr/bin/nc','-z','-w','1','127.0.0.1',str(wrong)],capture_output=True,timeout=3);assert r.returncode
   listener.settimeout(.1)
   try:listener.accept();raise AssertionError('forbidden port connected')
   except socket.timeout:pass
  finally:listener.close()
test('actual sandbox refuses outside-read and nonapproved loopback destination',sandbox_read_network)
def native_negative():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z).resolve();src=p/'src';src.mkdir();(src/'123').mkdir();(src/'124').mkdir();(src/'123/pg123.txt').write_bytes(b'x'*2400001);outside=p/'outside';outside.write_bytes(b'SYNTHETIC_TARGET');(src/'124/pg124.txt').symlink_to(outside)
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();cfg=p/'daemon';cfg.write_text(f'use chroot = no\nuid = {os.getuid()}\ngid = {os.getgid()}\n[gutenberg-epub]\npath = {src}\nread only = yes\n');daemon=subprocess.Popen(['/usr/bin/rsync','--daemon','--no-detach','--config='+str(cfg),'--port='+str(port),'--address=127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  try:
   time.sleep(.1)
   for eid in [123,124]:
    attempt=p/f'attempt{eid}';attempt.mkdir();stage=attempt/'raw';stage.mkdir();decl=attempt/'decl';decl.write_bytes(f'{eid}/pg{eid}.txt\0'.encode());r,raw=transport.transfer(eid,decl,stage,transport.clk()+4,lambda *a:None,connector=lambda:socket.create_connection(('127.0.0.1',port),timeout=1));assert r['child_reaped'] and r['received_bytes']==len(raw)
    if eid==123:assert validate.result(stage,eid,r)['status']=='INDEPENDENT_SOURCE_OVERSIZE_SKIPPED_NO_RETRY' and not list(stage.iterdir())
    else:assert isinstance(must(lambda:validate.result(stage,eid,r)),transport.ProtocolError) and not list(stage.iterdir())
   assert outside.read_bytes()==b'SYNTHETIC_TARGET'
  finally:daemon.kill();daemon.wait(timeout=2)
test('actual native local oversize is skipped; symlink never copied or called complete',native_negative)
def stats_refusals():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z);(p/'pg123.txt').write_bytes(b'x');base={'exit_code':0,'stdout':'Number of files: 1\nNumber of files transferred: 1\nTotal file size: 1 B\nTotal transferred file size: 1 B\n','stderr':''}
  for change in [{'stdout':base['stdout']+'Total file size: 1 B\n'},{'stdout':base['stdout'].replace('Total transferred file size: 1 B','Total transferred file size: 2 B')},{'stderr':'unexpected diagnostic'},{'exit_code':23}]:assert isinstance(must(lambda:validate.result(p,123,base|change)),transport.ProtocolError)
test('duplicate stats/mismatched sizes/nonempty diagnostics/nonzero exit refuse completion',stats_refusals)
print(json.dumps({'status':'PASS_SYNTHETIC_AND_LOOPBACK_ONLY','controls':len(N),'names':N,'public_source_connections':0,'global_ledger_writes':0,'retained_source_body_reads':0},indent=2))
