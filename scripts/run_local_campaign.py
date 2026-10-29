"""Run one local benchmark, then at most one 100M-token pilot if all gates pass."""
import fcntl,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from train_local import atomic_json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/local-campaign-v1'
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    lock=(OUT/'.lock').open('a');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (OUT/'campaign.json').exists():raise RuntimeError('Campaign already initialized; inspect existing state before starting another')
    files=[ROOT/'scripts'/n for n in ['benchmark_mlx.py','train_local.py','run_local_campaign.py']]
    pins={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    state={'status':'benchmark_running','pid':os.getpid(),'started_at':time.time(),'cloud_spend_usd':0,'paid_api_spend_usd':0,'pilot_target_tokens':100_000_000,'source_pins':pins,'benchmark_seconds':1800,'policy':'Run benchmark; launch fresh random-weight pilot only after every feasibility gate passes. No retries or expansion beyond 100M tokens.'}
    def write():state['updated_at']=time.time();atomic_json(OUT/'campaign.json',state)
    def invoke(mode,seed):
        folder=OUT/mode;folder.mkdir(exist_ok=True)
        cmd=[sys.executable,str(ROOT/'scripts/train_local.py'),'--mode',mode,'--output',str(folder),'--data',str(ROOT/'data/pilot-v1'),'--seed',str(seed)]
        with (folder/'console.log').open('a') as log:
            p=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            state['child_pid']=p.pid;write();return p.wait()
    write();rc=invoke('benchmark',42)
    if rc:
        state.update(status='benchmark_stopped',exit_code=rc);write();return rc
    result=json.loads((OUT/'benchmark/result.json').read_text());state['benchmark_result']=result
    unchanged=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h for name,h in pins.items())
    if not result.get('feasible') or not all(result.get('checks',{}).values()) or not unchanged:
        state.update(status='pilot_not_started',source_unchanged=unchanged);write();return 0
    state.update(status='pilot_running',pilot_started_at=time.time());write();rc=invoke('pilot',43)
    state.update(status='pilot_completed' if rc==0 else 'pilot_stopped',exit_code=rc,finished_at=time.time());write();return rc
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:
        OUT.mkdir(parents=True,exist_ok=True);atomic_json(OUT/'error.json',{'error':repr(e),'time':time.time()});raise
