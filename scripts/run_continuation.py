"""Local 100M -> 200M -> 300M campaign, evaluation at both milestones."""
import argparse,fcntl,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from train_local import atomic_json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runs/continuation-v1';REPORT=ROOT/'reports/continuation-v1'
def main(resume=False):
    OUT.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    lock=(OUT/'.lock').open('a');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    previous=json.loads((OUT/'campaign.json').read_text()) if (OUT/'campaign.json').exists() else None
    if previous and not resume:raise RuntimeError('Campaign already exists; inspect before restarting')
    if resume and not previous:raise RuntimeError('No campaign to resume')
    assert (ROOT/'data/continuation-v1/manifest.json').exists()
    names=['benchmark_mlx.py','train_local.py','train_continuation.py','evaluate_pilot.py','evaluate_continuation.py','run_continuation.py'];pins={n:hashlib.sha256((ROOT/'scripts'/n).read_bytes()).hexdigest() for n in names}
    if previous:
        assert all(pins[n]==h for n,h in previous['source_pins'].items() if n!='run_continuation.py'),'Training/evaluation sources changed'
    state={'status':'baseline_evaluation','pid':os.getpid(),'started_at':time.time(),'source_pins':pins,'additional_tokens_authorized':200000000,'total_token_ceiling':300000000,'cloud_spend_usd':0,'paid_api_spend_usd':0}
    if previous:state.update(resumed_at=time.time(),consent_required=False,previous_pid=previous['pid'])
    def write():state['updated_at']=time.time();atomic_json(OUT/'campaign.json',state)
    def invoke(args,logpath):
        assert all(hashlib.sha256((ROOT/'scripts'/n).read_bytes()).hexdigest()==h for n,h in pins.items()),'Source changed during campaign'
        with logpath.open('a') as f:
            p=subprocess.Popen([sys.executable,'-u',*map(str,args)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT);state['child_pid']=p.pid;write();rc=p.wait()
        if rc:raise RuntimeError(f'Child stopped with code {rc}: {args[0]}')
    def latest(directory):return directory/json.loads((directory/'latest.json').read_text())['directory']
    source=latest(ROOT/'runs/local-campaign-v1/pilot');assert json.loads((source/'state.json').read_text())['tokens']==100_000_000
    write()
    baseline=REPORT/'100m/completed.json'
    if resume and baseline.exists():
        assert json.loads(baseline.read_text())['complete']
        assert json.loads((REPORT/'100m/loss-results.json').read_text())['model_sha256']==hashlib.sha256((source/'model.safetensors').read_bytes()).hexdigest()
    else:invoke([ROOT/'scripts/evaluate_continuation.py','--checkpoint',source,'--total-tokens',100000000,'--output',REPORT/'100m'],OUT/'baseline-evaluation.log')
    for target in [200000000,300000000]:
        stage=OUT/f'{target//1000000}m';stage.mkdir(exist_ok=True);state.update(status='training',target_total_tokens=target);write()
        args=[ROOT/'scripts/train_continuation.py','--from-checkpoint',source,'--output',stage,'--target-total',target]
        if resume and (stage/'latest.json').exists():args.append('--resume')
        invoke(args,stage/'console.log')
        source=latest(stage);assert json.loads((source/'state.json').read_text())['tokens']==target
        state.update(status='evaluating',completed_total_tokens=target);write()
        invoke([ROOT/'scripts/evaluate_continuation.py','--checkpoint',source,'--total-tokens',target,'--output',REPORT/f'{target//1000000}m'],stage/'evaluation.log')
        state['last_completed_evaluation']=str(REPORT/f'{target//1000000}m/REPORT.md');write()
    state.update(status='completed',finished_at=time.time());write()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');args=p.parse_args()
    try:main(args.resume)
    except Exception as e:
        atomic_json(OUT/'error.json',{'error':repr(e),'time':time.time()})
        p=OUT/'campaign.json'
        if p.exists():s=json.loads(p.read_text());s.update(status='stopped',error=repr(e));atomic_json(p,s)
        raise
