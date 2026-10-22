"""Actual production supervisor RSS failclosed paths, synthetic child/output only."""
import json,pathlib,tempfile,types,os
from unittest.mock import patch
import pilot as p
checks=[]
root=os.getpid();childpid=987654321
cases={'empty':'','missing_root':f'{childpid} 1 42\n','malformed':f'{root} 1 42\nbroken\n','negative':f'{root} 1 42\n{childpid} {root} -1\n','duplicate':f'{root} 1 42\n{root} 1 42\n','selfparent':f'{root} {root} 42\n','zero_root':f'{root} 1 0\n','missing_liveworker':f'{root} 1 42\n','unowned_liveworker':f'{root} 1 42\n{childpid} 1 42\n','zero_liveworker':f'{root} 1 42\n{childpid} {root} 0\n'}
for name,snapshot in list(cases.items())+[('valid',f'{root} 1 42\n{childpid} {root} 43\n987654322 {childpid} 2\n')]:
 with tempfile.TemporaryDirectory() as td:
  r=pathlib.Path(td);out=r/'out';args=types.SimpleNamespace(code_pins_sha256='CODE',profile_sha256='PROFILE',source_binding='BOUND',source_binding_sha256='DIGEST')
  class Child:
   pid=childpid;returncode=None;waited=False
   def poll(self):return self.returncode
   def wait(self,timeout):self.waited=True;return self.returncode
  child=Child()
  def launch(*x,**kw):
   (out/'result.json').write_text(json.dumps({'status':'COMPLETE_TERMINAL_PREFIX_INDIVIDUAL_FRAME_DISCOVERY_NO_ADMISSION'}));return child
  def sleep(*x):child.returncode=0
  def kill(c):c.returncode=-9;c.wait(timeout=3)
  with patch.object(p,'ROOT',r),patch.object(p,'OUT',out),patch.object(p,'verify',return_value={}),patch.object(p,'verify_binding',return_value={}),patch.object(p.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)),patch.object(p.subprocess,'Popen',launch),patch.object(p.subprocess,'run',return_value=types.SimpleNamespace(stdout=snapshot)),patch.object(p.time,'sleep',sleep),patch.object(p,'kill',kill):
   if name=='valid':assert p.supervise(args)==0
   else:
    try:p.supervise(args)
    except ValueError:pass
    else:raise AssertionError('false COMPLETE '+name)
  sr=json.loads((out/'supervisor.json').read_text());assert child.waited
  if name=='valid':assert sr['status']=='COMPLETE_TERMINAL_PREFIX_FRAMES_NO_ADMISSION' and sr['peak_observed_RSS_bytes']==87*1024
  else:assert sr['status']=='PARTIAL_PREFIX_NO_RETRY' and child.returncode==-9
  checks.append('production_supervisor_'+name+'_snapshot')
print(json.dumps({'status':'PASS_ACTUAL_SUPERVISOR_SYNTHETIC_RSS_SNAPSHOTS','count':len(checks),'checks':checks,'retained_source_bytes':0,'actual_worker_or_source_execution':False},indent=2))
