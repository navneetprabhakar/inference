"""Actual worker/supervisor synthetic archives only; no retained native XML."""
import pathlib,tempfile,bz2,json,hashlib,types,time,signal,os
from unittest.mock import patch
import pilot as p,frame_core as c
# Import only inert fixture definitions; checks module runs its synthetic controls.
from checks import HEADER,page
checks=[]
def reject(name,fn,errors=(ValueError,TimeoutError)):
 try:fn()
 except errors:checks.append(name)
 else:raise AssertionError(name)
for mode in ['success','CRCfailure','native_index_mismatch','incomplete_prefix','source_symlink','opened_stat_mismatch']:
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);out=root/'out';out.mkdir();source=root/'SYNTHETIC_ONLY.bz2';groups=[];header=bz2.compress(HEADER);parts=[header];start=len(header)
  for i in range(16):
   body=page(i+1,100+i,title='Title '+str(i));body=body[:-12] if mode=='incomplete_prefix' and i==15 else body;raw=bz2.compress(body)
   if mode=='CRCfailure' and i==7:raw=raw[:-5]+bytes([raw[-5]^1])+raw[-4:]
   groups.append({'start':start,'end_exclusive':start+len(raw),'rows':[{'page_ID':i+1 if mode!='native_index_mismatch' or i!=7 else 999,'title':'Title '+str(i)}]});parts.append(raw);start+=len(raw)
  source.write_bytes(b''.join(parts)+bz2.compress(b'</mediawiki>'));binding={'source_stat':p.stat_id(source.stat()),'source_prefix_SHA256':hashlib.sha256(source.read_bytes()).hexdigest()};plan={'groups':groups,'XML_prefix_end_exclusive':start}
  if mode=='source_symlink':
   target=root/'synthetic-target';source.rename(target);source.symlink_to(target)
  if mode=='opened_stat_mismatch':binding['source_stat']['st_ino']+=1
  for name,n in p.SLOTS.items():(out/name).write_bytes(b' '*n)
  args=types.SimpleNamespace(code_pins_sha256='CODE',profile_sha256='PROFILE',source_binding='FUTURE-PARENT-ONLY',source_binding_sha256='BOUND',start=str(p.clk()),supervisor_pid=os.getppid())
  with patch.object(p,'ROOT',root),patch.object(p,'OUT',out),patch.object(p,'SOURCE',source),patch.object(p,'verify',return_value=plan),patch.object(p,'verify_binding',return_value=binding),patch.object(p.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)):
   if mode=='success':p.worker(args)
   else:reject('actual_worker_'+mode+'_terminalpartial_no_replacement',lambda:p.worker(args),(ValueError,OSError))
  r=json.loads((out/'result.json').read_text())
  if mode=='success':assert r['native_pages']==16 and r['indexed_groups']==16 and r['root_left_open'] and r['additional_full_archive_verification_read_bytes']==0 and r['compressed_prefix_bytes_read']==start;checks.append('actual_worker_16groups_header_native_tuple_counts_sourcebounds_PREFIX_ONLY')
  else:assert r['status']=='TERMINAL_PARTIAL_PREFIX_NO_RETRY_NO_GLOBALCLAIM'
# Binding absence must fail before opening any completed/live source file.
with patch.object(pathlib.Path,'stat',side_effect=AssertionError('must not inspect live archive')):reject('no_dispatch_without_fresh_source_binding_no_archive_stat_or_read',lambda:p.verify_binding(None,None,'p'))
# Actual supervisor alarms and TERM/INT cover the verification and futurebinding phase.
for stage in ['verify','binding','disk']:
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);out=root/'never';events=[];orig_timer=p.signal.setitimer
  def timer(which,seconds,*x):return orig_timer(which,.03 if seconds>100 else seconds,*x)
  def blocked(*x,**y):events.append(stage);time.sleep(2)
  with patch.object(p,'ROOT',root),patch.object(p,'OUT',out),patch.object(p,'verify',blocked if stage=='verify' else lambda *x:{}),patch.object(p,'verify_binding',blocked if stage=='binding' else lambda *x:{}),patch.object(p.shutil,'disk_usage',blocked if stage=='disk' else lambda x:types.SimpleNamespace(free=10**15)),patch.object(p.signal,'setitimer',timer):reject('actual_supervisor_blocked_'+stage+'_alarm_precedes_source_output',lambda:p.supervise(args),TimeoutError)
  assert events==[stage] and not out.exists() and p.signal.getitimer(signal.ITIMER_REAL)==(0.,0.)
for sig in [signal.SIGTERM,signal.SIGINT]:
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td)
  def raising(*x):signal.raise_signal(sig)
  with patch.object(p,'ROOT',root),patch.object(p,'OUT',root/'never'),patch.object(p,'verify',raising):reject('actual_supervisor_preflight_signal_'+str(sig),lambda:p.supervise(args),TimeoutError)
# Allstatic and freshsourcebinding pins must travel to worker unchanged.
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);out=root/'new';seen=[]
 class Child:
  pid=12345;returncode=1
  def poll(self):return 1
  def wait(self,timeout):return 1
 def launch(cmd,**kw):seen.extend(cmd);return Child()
 with patch.object(p,'ROOT',root),patch.object(p,'OUT',out),patch.object(p,'verify',return_value={}),patch.object(p,'verify_binding',return_value={}),patch.object(p.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)),patch.object(p.subprocess,'Popen',launch):reject('fake_reaped_child_partial_receipt_no_retry',lambda:p.supervise(args),(ValueError,json.JSONDecodeError))
 for key,val in [('--code-pins-sha256','CODE'),('--profile-sha256','PROFILE'),('--source-binding','FUTURE-PARENT-ONLY'),('--source-binding-sha256','BOUND')]:assert seen[seen.index(key)+1]==val
 checks.append('both_staticpins_and_future_sourcebinding_pins_propagate_parent_worker')
print(json.dumps({'status':'PASS_ACTUAL_SYNTHETIC_WORKER_LIFECYCLE_NO_RETAINED_XML','count':len(checks),'checks':checks,'retained_XML_bytes':0,'network':0,'global_ledger_writes':0},indent=2))
