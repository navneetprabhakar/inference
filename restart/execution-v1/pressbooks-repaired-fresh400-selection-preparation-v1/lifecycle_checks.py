"""Actual synthetic worker/supervisor lifecycle; no retained sources."""
from pathlib import Path
import tempfile,argparse,json,os,signal,time,subprocess
from unittest.mock import patch
import pilot
cases=[]
def refuse(f):
 try:f()
 except BaseException:return
 raise AssertionError('expected refusal')
for text in ['', '77 1 0','77 77 5','77 1 nope','77 1 5\n77 1 6']:
 refuse(lambda:pilot.tree_rss(text,77));cases.append('strictRSS_'+repr(text))
assert pilot.tree_rss('77 1 10\n78 77 20',77,78)==30720;cases.append('ownedpositiveRSSrootpluschild')
with tempfile.TemporaryDirectory() as z:
 root=Path(z)
 for post in [False,True]:
  out=root/('worker'+str(post));out.mkdir()
  for n,c in pilot.SLOTS.items():(out/n).write_bytes(b' '*c)
  a=argparse.Namespace(start=pilot.clk(),supervisor_pid=os.getppid(),profile_sha256='p',code_pins_sha256='c')
  (out/'ownership.json').write_text(json.dumps({'worker_PID':os.getpid(),'supervisor_PID':os.getppid(),'shared_start':a.start,'profile_SHA256':'p','codepins_SHA256':'c'}))
  profile={'output':str(out)};calls=[profile,ValueError('pin drift')] if post else [profile,profile]
  with patch.object(pilot,'verify',side_effect=calls),patch.object(pilot,'guard',return_value=None),patch.object(pilot.engine,'run',return_value={'status':'COMPLETE_REPAIRED_FRESH400_SELECTION_METADATA_ONLY_NO_ADMISSION'}):
   if post:refuse(lambda:pilot.worker(a))
   else:pilot.worker(a)
  r=json.loads((out/'result.json').read_text());assert ('PARTIAL' in r['status'])==post;cases.append('actual_owned_worker_postflight_pin_'+str(post))
 for method in ['alarm','TERM','INT']:
  out=root/('early'+method);a=argparse.Namespace(profile_sha256='p',code_pins_sha256='c')
  def blocked(a):
   if method!='alarm':os.kill(os.getpid(),getattr(signal,'SIG'+method))
   time.sleep(.1)
  with patch.object(pilot,'ENTRY_START',pilot.clk()-84.98),patch.object(pilot,'verify',side_effect=blocked):refuse(lambda:pilot.supervise(a))
  assert not out.exists();cases.append('early_preflight_'+method)
 # Existing output refusal precedes source execution or writes.
 out=root/'existing';out.mkdir();(out/'old').write_text('old')
 with patch.object(pilot,'ENTRY_START',pilot.clk()),patch.object(pilot,'verify',return_value={'output':str(out)}):refuse(lambda:pilot.supervise(a))
 assert list(out.iterdir())==[out/'old'];cases.append('existing_output_preserved')
 real=subprocess.Popen
 for mode in ['RSS','deadline']:
  out=root/('child'+mode);children=[]
  def launch(cmd,**kw):
   c=real([os.sys.executable,'-B','-c','import time;time.sleep(5)'],**kw);children.append(c);return c
  fakeps=argparse.Namespace(stdout='1 0 1')
  with patch.object(pilot,'ENTRY_START',pilot.clk()-(84.92 if mode=='deadline' else 0)),patch.object(pilot,'verify',return_value={'output':str(out)}),patch.object(pilot,'size',return_value=0),patch.object(pilot.shutil,'disk_usage',return_value=argparse.Namespace(free=10**12)),patch.object(pilot.subprocess,'Popen',side_effect=launch),patch.object(pilot.subprocess,'run',return_value=fakeps),patch.object(pilot,'tree_rss',return_value=2000000000 if mode=='RSS' else 1000):refuse(lambda:pilot.supervise(a))
  assert len(children)==1 and children[0].poll() is not None;assert json.loads((out/'supervisor.json').read_text())['status'].startswith('PARTIAL');cases.append('actual_child_'+mode+'_kill_reap_partial')
print(json.dumps({'status':'PASS_SYNTHETIC_LIFECYCLE_ONLY','checks':len(cases),'cases':cases,'retained_source_body_reads':0},indent=2));signal.setitimer(signal.ITIMER_REAL,0)
