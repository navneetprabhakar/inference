import socket,subprocess,tempfile,os,time,json
from pathlib import Path
import transport
results=[]
with tempfile.TemporaryDirectory() as z:
 root=Path(z).resolve();src=root/'src';src.mkdir();(src/'123').mkdir();file=src/'123/pg123.txt';fl=root/'list';fl.write_bytes(b'123/pg123.txt\0');sk=socket.socket();sk.bind(('127.0.0.1',0));port=sk.getsockname()[1];sk.close();cfg=root/'conf';cfg.write_text(f'use chroot = no\nuid = {os.getuid()}\ngid = {os.getgid()}\n[gutenberg-epub]\npath = {src}\nread only = yes\n');daemon=subprocess.Popen(['/usr/bin/rsync','--daemon','--no-detach','--config='+str(cfg),'--port='+str(port),'--address=127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
 try:
  time.sleep(.1)
  for kind in ['missing','oversize','symlink']:
   if file.exists() or file.is_symlink():file.unlink()
   if kind=='oversize':file.write_bytes(b'x'*2400001)
   if kind=='symlink':(src/'elsewhere').write_bytes(b'NO');file.symlink_to(src/'elsewhere')
   stage=root/kind;stage.mkdir()
   try:r,b=transport.transfer(123,fl,stage,transport.clk()+5,lambda *a:None,connector=lambda:socket.create_connection(('127.0.0.1',port),timeout=1));error=None
   except Exception as e:r=getattr(e,'transport_receipt',{});error=type(e).__name__+':'+str(e)
   results.append({'kind':kind,'error':error,'receipt':r,'files':[str(x.relative_to(stage)) for x in stage.rglob('*')]})
 finally:daemon.kill();daemon.wait(timeout=2)
print(json.dumps({'scope':'LOCAL_ONLY_NO_REMOTE','results':results},indent=2))
