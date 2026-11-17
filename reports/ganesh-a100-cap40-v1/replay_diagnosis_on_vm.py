"""Bounded read-only replays of already captured inputs; no model training."""
import datetime as dt,fcntl,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path('/opt/english');D=ROOT/'diagnostic-results';D.mkdir(exist_ok=False)
limit=min(time.time()+1200,dt.datetime.fromisoformat(json.loads((ROOT/'config.json').read_text())['qualification_deadline_utc'].replace('Z','+00:00')).timestamp()-600)
with Path('/tmp/ganesh-gpu-writer.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for mode in ('eager','compiled'):
  for repeat in (1,2):
   remaining=limit-time.time();assert remaining>30
   with (D/f'{mode}-{repeat}.log').open('x') as f:
    subprocess.run([sys.executable,'-m','cloud_training.nano_optimizer_capture','--capture',str(ROOT/'results/uninterrupted/optimizer-capture/step-00000001'),'--repo',str(ROOT/'nanochat-source'),'--mode',mode,'--output',str(D/f'replay-{mode}-{repeat}')],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=remaining)
   print(mode,repeat,'complete',flush=True)
 subprocess.run([sys.executable,str(ROOT/'capture_compare.py'),'--replays',str(D)],check=True,timeout=120)
