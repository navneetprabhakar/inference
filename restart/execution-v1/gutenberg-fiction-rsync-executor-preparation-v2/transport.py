"""Strict single-connection rsync relay; native application bytes, no TLS claim."""
import hashlib,ipaddress,os,re,selectors,socket,subprocess,threading,time
from pathlib import Path
HOST='rsync.ibiblio.org';PORT=873;RECEIVED=2500000;SENT=128000
class ProtocolError(Exception):pass
class IndependentTimeout(Exception):pass
class TransferLimit(ProtocolError):pass
clk=lambda:time.clock_gettime(time.CLOCK_MONOTONIC)
def path_for(eid):
 if type(eid) is not int or not 1<=eid<=99999999:raise ProtocolError('invalid_frozen_ID')
 return f'{eid}/pg{eid}.txt'
def public_addresses():
 values=socket.getaddrinfo(HOST,PORT,type=socket.SOCK_STREAM);out=[]
 for family,kind,proto,canon,addr in values:
  if family not in (socket.AF_INET,socket.AF_INET6) or not ipaddress.ip_address(addr[0]).is_global:raise ProtocolError('nonpublic_fixedhost_DNS')
  if (family,addr) not in out:out.append((family,addr))
 if not out:raise ProtocolError('no_public_fixedhost_address')
 return out

def owned_peer(child,peer,listen_port):
 if child is None or child.poll() is not None:raise ProtocolError('owned_client_absent')
 want=f'127.0.0.1:{peer[1]}->127.0.0.1:{listen_port}'
 r=subprocess.run(['/usr/sbin/lsof','-nP','-a','-p',str(child.pid),'-iTCP','-Fn'],capture_output=True,text=True,timeout=1)
 if r.returncode or len(r.stdout)>32768 or not any(line=='n'+want for line in r.stdout.splitlines()):raise ProtocolError('loopback_peer_not_owned_rsync')

class Relay:
 def __init__(self,deadline,check,connector=None,received_cap=RECEIVED,sent_cap=SENT,authenticate=owned_peer):
  self.deadline=deadline;self.check=check;self.connector=connector or self.remote;self.cap=received_cap;self.sendcap=sent_cap;self.authenticate=authenticate;self.child=None;self.listener=socket.socket();self.listener.bind(('127.0.0.1',0));self.listener.listen(1);self.listener.settimeout(.1);self.port=self.listener.getsockname()[1];self.stop=threading.Event();self.done=threading.Event();self.error=None;self.received=bytearray();self.sent=0;self.remote_started=False;self.remote_address=None;self.sockets=[];self.thread=threading.Thread(target=self.serve,daemon=True)
 def remote(self):
  choices=public_addresses();family,addr=choices[0] # one connection only, no address fallback
  self.check();self.remote_started=True;self.remote_address=list(addr)
  s=socket.socket(family,socket.SOCK_STREAM);self.sockets.append(s);s.settimeout(max(.001,min(10,self.deadline-clk())));s.connect(addr);return s
 def start(self):self.thread.start()
 def guard(self):
  if self.stop.is_set():raise ProtocolError('relay_cancelled')
  if clk()>=self.deadline:raise IndependentTimeout('per_file_deadline')
  self.check()
 def serve(self):
  sel=None
  try:
   while True:
    self.guard()
    try:client,peer=self.listener.accept();break
    except socket.timeout:continue
   self.sockets.append(client)
   if peer[0]!='127.0.0.1':raise ProtocolError('nonloopback_client')
   until=min(self.deadline,clk()+2)
   while self.child is None and clk()<until:self.guard();time.sleep(.005)
   self.authenticate(self.child,peer,self.port)
   upstream=self.connector();self.sockets.append(upstream)
   client.setblocking(False);upstream.setblocking(False);sel=selectors.DefaultSelector();sel.register(client,selectors.EVENT_READ,'c');sel.register(upstream,selectors.EVENT_READ,'u');to_client=bytearray();to_upstream=bytearray();ceof=False;ueof=False;write_shutdown=False
   while True:
    self.guard()
    if ueof and not to_client:break
    if len(self.received)>=self.cap:raise TransferLimit('received_application_byte_cap_no_EOF_claim')
    if self.sent>=self.sendcap:raise TransferLimit('client_protocol_byte_cap')
    for sock,role in [(client,'c'),(upstream,'u')]:
     events=(selectors.EVENT_READ if not (ceof if role=='c' else ueof) and len(to_upstream if role=='c' else to_client)<65536 else 0)|(selectors.EVENT_WRITE if (to_client if role=='c' else to_upstream) else 0)
     try:sel.unregister(sock)
     except KeyError:pass
     if events:sel.register(sock,events,role)
    for key,events in sel.select(min(.05,max(.001,self.deadline-clk()))):
     if events&selectors.EVENT_READ:
      maximum=min(65536,self.sendcap-self.sent) if key.data=='c' else min(65536,self.cap-len(self.received))
      try:b=key.fileobj.recv(maximum)
      except BlockingIOError:continue
      if key.data=='c':
       if not b:ceof=True
       else:self.sent+=len(b);to_upstream.extend(b)
      else:
       if not b:ueof=True
       else:self.received.extend(b);to_client.extend(b)
     if events&selectors.EVENT_WRITE:
      buffer=to_client if key.data=='c' else to_upstream
      if buffer:
       try:n=key.fileobj.send(buffer)
       except BlockingIOError:continue
       del buffer[:n]
    if ceof and not to_upstream and not write_shutdown:
     try:upstream.shutdown(socket.SHUT_WR)
     except OSError:pass
     write_shutdown=True
  except socket.timeout:self.error=IndependentTimeout('remote_connect_timeout')
  except BaseException as e:self.error=e
  finally:
   if sel:sel.close()
   for s in self.sockets:
    try:s.close()
    except OSError:pass
   self.listener.close();self.done.set()
 def close(self):
  self.stop.set()
  for s in self.sockets:
   try:s.shutdown(socket.SHUT_RDWR)
   except OSError:pass
  self.thread.join(timeout=2)
  if self.thread.is_alive():raise ProtocolError('relay_thread_not_reaped')

def argv(eid,port,filelist,stage):
 if type(port) is not int or not 1<=port<=65535:raise ProtocolError('local_port')
 # Preserve exact frozen-file declaration, now source path is literal rather than --files-from.
 if Path(filelist).read_bytes()!=path_for(eid).encode()+b'\0':raise ProtocolError('exact_single_file_declaration')
 return ['/usr/bin/rsync','--no-motd','--partial','--max-size=2400000','--timeout=50','--stats','--port='+str(port),'rsync://127.0.0.1/gutenberg-epub/'+path_for(eid),str(stage)+'/']
def clean_env(home):return {'PATH':'/usr/bin:/bin','HOME':str(home),'LC_ALL':'C','LANG':'C','TMPDIR':str(home)}

def transfer(eid,filelist,stage,deadline,check,connector=None,received_cap=RECEIVED,authenticate=owned_peer):
 child=None;relay=Relay(deadline,check,connector,received_cap=received_cap,authenticate=authenticate);stdout=bytearray();stderr=bytearray();sel=None
 try:
  relay.start();child=subprocess.Popen(argv(eid,relay.port,filelist,stage),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=clean_env(stage),start_new_session=True);relay.child=child;sel=selectors.DefaultSelector()
  for stream,role in [(child.stdout,'out'),(child.stderr,'err')]:os.set_blocking(stream.fileno(),False);sel.register(stream,selectors.EVENT_READ,role)
  while child.poll() is None or sel.get_map():
   check(child.pid)
   if clk()>=deadline:raise IndependentTimeout('per_file_deadline')
   for key,event in sel.select(.05):
    b=os.read(key.fd,65536)
    if not b:sel.unregister(key.fileobj);continue
    buffer=stdout if key.data=='out' else stderr
    if len(buffer)+len(b)>65536:raise ProtocolError('rsync_log_cap')
    buffer.extend(b)
  child.wait(timeout=1)
  if not relay.done.wait(timeout=max(.001,min(1,deadline-clk()))):raise ProtocolError('relay_missing_EOF_completion')
  if relay.error:raise relay.error
  return {'exit_code':child.returncode,'received_bytes':len(relay.received),'received_SHA256':hashlib.sha256(relay.received).hexdigest(),'sent_protocol_bytes':relay.sent,'stdout':bytes(stdout).decode('utf8','replace'),'stderr':bytes(stderr).decode('utf8','replace'),'remote_started':relay.remote_started,'remote_address':relay.remote_address,'child_PID':child.pid,'child_reaped':True,'transport':'official native unencrypted rsync; application-byte cap, not physical TCP/IP wire cap'},bytes(relay.received)
 except BaseException as exc:
  exc.transport_receipt={'exit_code':None if child is None else child.poll(),'received_bytes':len(relay.received),'received_SHA256':hashlib.sha256(relay.received).hexdigest(),'sent_protocol_bytes':relay.sent,'stdout':bytes(stdout).decode('utf8','replace'),'stderr':bytes(stderr).decode('utf8','replace'),'remote_started':relay.remote_started,'remote_address':relay.remote_address}
  raise
 finally:
  if child is not None:
   if child.poll() is None:
    try:os.killpg(child.pid,9)
    except ProcessLookupError:pass
    except PermissionError:
     if child.poll() is None:raise ProtocolError('owned_group_kill_permission_refused')
   child.wait(timeout=2)
   for stream in [child.stdout,child.stderr]:
    if stream is not None:stream.close()
  if sel:sel.close()
  relay.close()
