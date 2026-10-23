"""Per-phase watchdog, one authorized attempt and no next-stage launcher."""
import argparse,json,os,re,signal,subprocess,sys,time,traceback
from pathlib import Path
import psutil
from engine_support import ROOT,GIB,save,append,sha,CHECKPOINT

def main(phase):
    contract=json.loads((ROOT/'contract.json').read_text());clock=json.loads((ROOT/'clock.json').read_text())
    assert contract['first_stage_training_authorized'] and not contract['next_stage_authorized']
    if (ROOT/'global-stop.json').exists():raise RuntimeError('Global stop remains terminal')
    marker=ROOT/(phase+'-supervisor-started.json')
    if marker.exists():raise RuntimeError('One attempt per phase; no automatic restart')
    baseline=382.75*1024**2  # First approval-time sysctl reading; never reset.
    deadline=min(clock['stage1_deadline_epoch'],clock['overall_original_deadline_epoch'])
    if time.time()>=deadline-10:raise TimeoutError('Phase budget exhausted before launch')
    command=[sys.executable,str(ROOT/'audit_boundaries.py')]
    save(marker,dict(pid=os.getpid(),epoch=time.time(),deadline_epoch=deadline,swap_baseline_bytes=baseline,command=command))
    env=dict(os.environ,PYTORCH_ENABLE_MPS_FALLBACK='0',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',PYTHONUNBUFFERED='1',TOKENIZERS_PARALLELISM='false')
    log=(ROOT/(phase+'.log')).open('x');child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    save(ROOT/'active-worker.json',dict(phase=phase,pid=child.pid,deadline_epoch=deadline));reason=None;peak=0;max_growth=0;last_slow=0;critical_since=None
    try:
      while child.poll() is None:
        now=time.time();process=psutil.Process(child.pid)
        rss=process.memory_info().rss
        for sub in process.children(recursive=True):
          try:rss+=sub.memory_info().rss
          except psutil.NoSuchProcess:pass
        peak=max(peak,rss)
        text=subprocess.check_output(['/usr/sbin/sysctl','vm.swapusage'],text=True)
        m=re.search(r'used =\s*([\d.]+)([MG])',text);assert m,'Swap telemetry unavailable'
        current=float(m[1])*(1024**2 if m[2]=='M' else GIB);growth=max(0,current-baseline);max_growth=max(max_growth,growth)
        free=psutil.disk_usage(ROOT).free
        if now-last_slow>=15:
          power=subprocess.check_output(['/usr/bin/pmset','-g','batt'],text=True);thermal=subprocess.check_output(['/usr/bin/pmset','-g','therm'],text=True,stderr=subprocess.STDOUT)
          append(ROOT/'power-thermal.jsonl',dict(epoch=now,phase=phase,power=power,thermal=thermal))
          on_ac="Now drawing from 'AC Power'" in power
          critical=bool(re.search(r'(?:Thermal_(?:Warning_)?Level|ThermalPressure)\s*=\s*(?:[2-9]|[1-9][0-9]+)',thermal))
          critical_since=(critical_since or now) if critical else None;last_slow=now
        append(ROOT/'resources.jsonl',dict(epoch=now,phase=phase,RSS_bytes=rss,additional_swap_bytes=growth,free_disk_bytes=free))
        if (ROOT/'global-stop.json').exists():reason='GLOBAL_STOP'
        elif rss>12*GIB:reason='RSS_CAP'
        elif growth>512*1024**2:reason='SWAP_GROWTH_CAP'
        elif free<60*GIB:reason='DISK_FLOOR'
        elif not on_ac:reason='AC_POWER_LOST'
        elif critical_since and now-critical_since>=60:reason='SUSTAINED_CRITICAL_THERMAL'
        elif now>=deadline:reason='PHASE_DEADLINE'
        if reason:
          save(ROOT/'global-stop.json',dict(reason=reason,phase=phase,epoch=now));break
        time.sleep(3)
    except BaseException as e:
      reason=type(e).__name__+': '+str(e);save(ROOT/'global-stop.json',dict(reason=reason,phase=phase,epoch=time.time()))
    finally:
      if child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
      log.close();save(ROOT/(phase+'-supervisor.json'),dict(returncode=child.returncode,stop_reason=reason,worker_reaped=True,peak_RSS_bytes=peak,maximum_additional_swap_bytes=max_growth,terminal_epoch=time.time()))
      (ROOT/'active-worker.json').unlink(missing_ok=True)
    if child.returncode or reason:raise RuntimeError(f'Phase failed: {phase}, exit {child.returncode}, {reason}')
    assert sha(CHECKPOINT)==contract['reference']['checkpoint_sha256']
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['boundary-audit']);main(p.parse_args().phase)
