"""Actual local openrsync selective-file fixture. No public network or ledger."""
import os,socket,subprocess,tempfile,time,json
from pathlib import Path
import transport
root=Path(tempfile.mkdtemp(prefix='pg-rsync-fixture-')).resolve();source=root/'source';source.mkdir();(source/'123').mkdir();(source/'123/pg123.txt').write_bytes(b'Whole synthetic fiction.\n'*100);(source/'123/secret.txt').write_bytes(b'MUST NOT COPY');(source/'999').mkdir();(source/'999/pg999.txt').write_bytes(b'MUST NOT COPY')
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();config=root/'daemon.conf';config.write_text(f'address = 127.0.0.1\nport = {port}\nuse chroot = false\nuid = {os.getuid()}\ngid = {os.getgid()}\n[gutenberg-epub]\npath = {source}\nread only = true\n')
daemon=subprocess.Popen(['/usr/bin/rsync','--daemon','--no-detach','--config='+str(config),'--port='+str(port),'--address=127.0.0.1'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
try:
 time.sleep(.1)
 if daemon.poll() is not None:raise RuntimeError(daemon.communicate())
 stage=root/'stage';stage.mkdir();fl=root/'files';fl.write_bytes(b'123/pg123.txt\0')
 def connector():return socket.create_connection(('127.0.0.1',port),timeout=2)
 
 try:receipt,raw=transport.transfer(123,fl,stage,transport.clk()+10,lambda *a:None,connector=connector)
 except Exception as e:
  print(json.dumps({'error':str(e),'receipt':getattr(e,'transport_receipt',{})}));raise
 print(json.dumps({'receipt':receipt,'files':[str(x.relative_to(stage)) for x in stage.rglob('*')],'root':str(root)},indent=2));assert receipt['exit_code']==0 and (stage/'pg123.txt').read_bytes()==(source/'123/pg123.txt').read_bytes() and len([p for p in stage.rglob('*') if p.is_file()])==1
finally:
 os.killpg(daemon.pid,9);daemon.wait(timeout=2)
