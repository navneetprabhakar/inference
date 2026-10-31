"""Overlap one authorized arm with an existing evaluator; preserve pinned experiment code."""
import json,os,signal,subprocess,sys,time,fcntl
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runs/sft-v2'
def write(s):
 p=OUT/'overlap.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(s,indent=2));tmp.replace(p)
def main():
 lock=(OUT/'.overlap.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 campaign=json.loads((OUT/'campaign.json').read_text());parent=campaign['pid'];evaluator=campaign['child_pid']
 assert campaign['status']=='evaluating' and campaign['stage']=='base-200m'
 assert not (OUT/'STOP').exists()
 arm=OUT/'100m-lr1e-5';assert not (arm/'latest.json').exists() and not (arm/'result.json').exists()
 base=ROOT/'runs/local-campaign-v1/pilot';base=base/json.loads((base/'latest.json').read_text())['directory']
 state={'status':'starting','supervisor_pid':parent,'evaluation_pid':evaluator,'arm':'100m-lr1e-5','started_at':time.time(),'input_token_cap':5000000,'cloud_spend_usd':0,'strategy':'one trainer plus existing evaluator; original supervisor held until trainer exits'}
 child=None;held=False
 try:
  # Stop only the orchestrator, never its evaluator. This prevents duplicate arm launch.
  os.kill(parent,signal.SIGSTOP);held=True
  arm.mkdir(exist_ok=True)
  with (arm/'console.log').open('a') as log:
   child=subprocess.Popen([sys.executable,'-u',str(ROOT/'scripts/train_sft.py'),'--checkpoint',str(base),'--output',str(arm),'--lr','1e-5'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
   state.update(status='running',training_pid=child.pid);write(state)
   rc=child.wait()
  state.update(status='completed' if rc==0 else 'stopped',returncode=rc,finished_at=time.time());write(state)
  if rc:
   # Preserve checkpoints and prevent an automatic restart after a resource stop.
   (OUT/'STOP').write_text('Overlap trainer stopped; inspect before resuming.\n')
 finally:
  if child is not None and child.poll() is None:
   child.terminate();child.wait();(OUT/'STOP').write_text('Overlap controller interrupted.\n')
  if held:os.kill(parent,signal.SIGCONT)
if __name__=='__main__':main()
