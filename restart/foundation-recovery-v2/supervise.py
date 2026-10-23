"""Independent resource/deadline watchdog for serialized phase jobs; no retry."""
import argparse,json,os,re,signal,subprocess,sys,time,traceback
from common import *
def supervise(phase,commands,label):
 check(phase);freeze_check(phase);peak=0;critical_since=None;results=[]
 try:
  for i,command in enumerate(commands):
   check(phase);freeze_check(phase)
   logpath=ROOT/phase/f'{label}-{i}.log'
   with logpath.open('x') as log:
    child=subprocess.Popen(command,cwd=PROJECT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYTORCH_ENABLE_MPS_FALLBACK='0',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',PYTHONUNBUFFERED='1'))
    save(ROOT/'active-worker.json',dict(phase=phase,label=label,pid=child.pid,supervisor_pid=os.getpid(),epoch=time.time()))
    try:
     while child.poll() is None:
      check(phase);r=resources(os.getpid());peak=max(peak,r['rss_bytes'])
      critical=bool(re.search(r'(?:Thermal_(?:Warning_)?Level|ThermalPressure)\s*=\s*(?:[2-9]|[1-9][0-9]+)',r['thermal']))
      critical_since=(critical_since or time.time()) if critical else None
      if critical_since and time.time()-critical_since>=60:raise RuntimeError('SUSTAINED_CRITICAL_THERMAL')
      save(ROOT/f'{label}-resources.json',dict(**r,peak_RSS_bytes=peak));time.sleep(3)
    finally:
     if child.poll() is None:
      os.killpg(child.pid,signal.SIGTERM)
      try:child.wait(timeout=5)
      except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
    results.append(dict(command=command,returncode=child.returncode,worker_reaped=True))
    if child.returncode:raise RuntimeError(f'WORKER_FAILED: {label}-{i} exit {child.returncode}')
   freeze_check(phase)
 except BaseException as e:
  save(ROOT/'STOP.json',dict(phase=phase,reason=type(e).__name__+': '+str(e),epoch=time.time(),training_authorized=False));raise
 finally:
  (ROOT/'active-worker.json').unlink(missing_ok=True)
  save(ROOT/f'{label}-supervisor.json',dict(results=results,peak_RSS_bytes=peak,terminal_epoch=time.time()))
