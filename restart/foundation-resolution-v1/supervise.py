"""Independent resource/deadline watchdog for serialized phase jobs; no retry."""
import argparse,json,os,re,signal,subprocess,sys,time,traceback
from common import *
def supervise(phase,commands,label):
 check(phase);freeze_check(phase);peak=0;critical_since=None;results=[]
 try:
  for i,command in enumerate(commands):
   check(phase);freeze_check(phase)
   logpath=ROOT/f'{label}-{i}.log'
   with logpath.open('x') as log:
    child=subprocess.Popen(command,cwd=PROJECT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYTORCH_ENABLE_MPS_FALLBACK='0',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',PYTHONUNBUFFERED='1'))
    save(ROOT/'active-worker.json',dict(phase=phase,label=label,pid=child.pid,supervisor_pid=os.getpid(),epoch=time.time()))
    try:
     while child.poll() is None:
      check(phase);r=resources(child.pid);peak=max(peak,r['rss_bytes'])
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
def main():
 phase=sys.argv[1];assert phase=='R0'
 marker=ROOT/'R0-attempt.json'
 if marker.exists():raise RuntimeError('ATTEMPT_ALREADY_CONSUMED')
 check('R0');freeze_check('R0')
 save(marker,dict(epoch=time.time(),phase=phase,one_attempt=True,training_updates=0))
 commands=[]
 for name,path,stories in [('prior','restart/foundation-stage2-v1/stage2-checkpoint.pt',False),('baseline','restart/foundation-stage3-v1/stage3-checkpoint.pt',True)]:
  for backend in ['mlx','fp32']:
   command=[str(PYTHON),str(ROOT/'evaluate.py'),phase,backend,path,name]
   if backend=='mlx' and stories:command+=['--stories']
   commands.append(command)
 supervise(phase,commands,'R0-evaluation')
 for name in ['prior','baseline']:
  a=read(ROOT/name/'summary.json')['validation_nll'];b=read(ROOT/name/'fp32.json')['validation_nll'];assert abs(a-b)<=.02,'FP32_PARITY_FAILED'
 save(ROOT/'R0-computation-pass.json',dict(status='PASS',epoch=time.time(),training_updates=0,phase_positions=Meter('R0').total(),teacher_calibration_pending=True))
if __name__=='__main__':
 try:main()
 except BaseException as e:
  if not (ROOT/'STOP.json').exists():save(ROOT/'STOP.json',dict(phase='R0',reason=type(e).__name__+': '+str(e),epoch=time.time(),training_authorized=False))
  raise
