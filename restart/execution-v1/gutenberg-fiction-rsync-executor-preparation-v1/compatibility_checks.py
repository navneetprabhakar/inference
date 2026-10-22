"""Local-only native rsync compatibility evidence; no remote daemon contacted."""
import socket,subprocess,threading,tempfile,time,os,json,hashlib
from pathlib import Path
import transport
results=[]
with tempfile.TemporaryDirectory(prefix='pg-rsync-local-') as z:
 root=Path(z).resolve();src=root/'source';src.mkdir();(src/'123').mkdir();wanted=b'Whole synthetic fiction.\n'*100;(src/'123/pg123.txt').write_bytes(wanted);(src/'123/secret.txt').write_bytes(b'MUST NOT COPY');(src/'999').mkdir();(src/'999/pg999.txt').write_bytes(b'MUST NOT COPY');fl=root/'files';fl.write_bytes(b'123/pg123.txt\0')
 d=root/'localdest';d.mkdir();cmd=['/usr/bin/rsync','--relative','--no-implied-dirs','--from0','--files-from='+str(fl),'--max-size=2400000',str(src)+'/',str(d)+'/'];r=subprocess.run(cmd,capture_output=True,text=True,timeout=5);assert r.returncode==0 and (d/'123/pg123.txt').read_bytes()==wanted and len([p for p in d.rglob('*') if p.is_file()])==1;results.append({'check':'actual_localfilesystem_singlefile_no_implicit_recursion','status':'PASS','argv':cmd,'only_file_SHA256':hashlib.sha256(wanted).hexdigest()})
 sk=socket.socket();sk.bind(('127.0.0.1',0));port=sk.getsockname()[1];sk.close();config=root/'daemon.conf';config.write_text(f'use chroot = no\nuid = {os.getuid()}\ngid = {os.getgid()}\n[gutenberg-epub]\npath = {src}\nread only = yes\n');daemon=subprocess.Popen(['/usr/bin/rsync','--daemon','--no-detach','--config='+str(config),'--port='+str(port),'--address=127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
 try:
  time.sleep(.1)
  for i,(extra,suffix) in enumerate([([], '/123/pg123.txt'),(['--from0','--files-from='+str(fl)],'/'),(['--from0','--files-from='+str(fl)],'/./')]):
   d=root/f'daemon{i}';d.mkdir();cmd=['/usr/bin/rsync',*extra,f'rsync://127.0.0.1:{port}/gutenberg-epub'+suffix,str(d)+'/'];r=subprocess.run(cmd,capture_output=True,text=True,timeout=5);files=[str(p.relative_to(d)) for p in d.rglob('*') if p.is_file()]
   results.append({'check':'actual_loopback_daemon_'+str(i),'exit':r.returncode,'files':files,'stderr':r.stderr,'observed_complete_expected_file':files==['pg123.txt'] if i==0 else files==['123/pg123.txt']})
 finally:daemon.kill();daemon.wait(timeout=2)
# Operational application-byte cap against deliberately overflowing LOCAL peer.
listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);port=listener.getsockname()[1]
def sender():
 c,_=listener.accept()
 try:c.sendall(b'x'*100000)
 except OSError:pass
 finally:c.close();listener.close()
t=threading.Thread(target=sender);t.start();relay=transport.Relay(transport.clk()+3,lambda:None,connector=lambda:socket.create_connection(('127.0.0.1',port),timeout=1),received_cap=5000,authenticate=lambda *a:None);relay.start();client=socket.create_connection(('127.0.0.1',relay.port));received=bytearray();client.settimeout(3)
try:
 while True:
  b=client.recv(65536)
  if not b:break
  received.extend(b)
finally:client.close();relay.close();t.join(timeout=2)
assert isinstance(relay.error,transport.TransferLimit) and len(relay.received)==5000 and len(received)<=5000 and not relay.thread.is_alive();results.append({'check':'actual_loopback_relay5000B_application_hardcap','status':'PASS','upstream_application_read':len(relay.received),'forwarded_to_client':len(received),'no_physical_TCP_wire_claim':True})
# Actual pinned native child stalled in greeting, group SIGKILL then reap.
ls=socket.socket();ls.bind(('127.0.0.1',0));ls.listen(1);port=ls.getsockname()[1]
def stall():
 c,_=ls.accept();time.sleep(.3);c.close();ls.close()
t=threading.Thread(target=stall);t.start();child=subprocess.Popen(['/usr/bin/rsync','--timeout=2',f'rsync://127.0.0.1:{port}/gutenberg-epub/123/pg123.txt','/tmp/nonexistent-pg-fixture-no-file'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);time.sleep(.1);os.killpg(child.pid,9);child.wait(timeout=2);t.join(timeout=2);assert child.returncode==-9;results.append({'check':'actual_native_stalledchild_groupSIGKILL_reaped','status':'PASS','returncode':child.returncode})
print(json.dumps({'status':'LOCAL_CONTROLS_COMPLETE_REMOTE_PREPARATION_BLOCKED_NATIVE_DAEMON_FILESFROM_INCOMPATIBILITY','results':results,'remote_connections':0,'book_bodies_read':0,'global_ledger_writes':0,'note':'Localfilesystem exactfilesfrom copy succeeds and relaycap/ownedkill succeeds. LocalApple daemon cannot satisfy exactfilesfrom command: module root chdir error, dotrootemptylist. Directexactfile works but is NOT allowed fallback. Does not prove behavior of public GNUdaemon; no remoteprobe authorized.'},indent=2))
