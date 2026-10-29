"""Six disposable100-update runs. Training-only LR selection; no retained run."""
import sys,json,time,subprocess,gc,random,math
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;PROJECT=P.parents[1];READY=P.parent/'runner-readiness-2026-10-29';sys.path.insert(0,str(READY))
from runner import Backend,Inputs,Runner,Meter,read,sha,atomic
CAPS=dict(positions=50000000,updates=4612,assistant=1000000,narrative=10000000,seconds=5400)
PRIOR=read(P.parent/'disposable-calibration-2026-10-29/result.json')
class CalibrationMeter(Meter):
 def reserve(self,kind,positions,updates=0,assistant=0,narrative=0):
  totals=self.totals()
  if totals['updates']+updates>612:raise RuntimeError('CALIBRATION_600_UPDATE_CAP')
  if totals['positions']+positions>10000000:raise RuntimeError('CALIBRATION_POSITION_CAP')
  return super().reserve(kind,positions,updates,assistant,narrative)
 def check(self):
  super().check()
  if self.seconds()>PRIOR['seconds']+1800:raise RuntimeError('CALIBRATION_TIME_CAP')

def verify():
 for base,name in [(READY,'freeze.json'),(READY,'preservation-freeze.json'),(READY,'gradient-freeze.json'),(READY,'launch-freeze.json'),(P,'freeze.json')]:
  for f,h in read(base/name)['files'].items():
   if sha(PROJECT/f)!=h:raise RuntimeError('INPUT_CHANGED:'+f)
 return sha(P/'freeze.json')

def probe(b,inputs,meter):
 from runner import collate
 rows=inputs.rows['diverse'];values={}
 for family,indices in read(P/'training-probe.json').items():
  batch=collate([rows[i] for i in indices]);meter.reserve('training-only-probe',int(batch[0].size));meter.start()
  try:values[family]=b.forward(batch)
  finally:meter.stop()
 return values

def worker(lr,replay):
 identity=verify();meter=CalibrationMeter(P/'private/study.sqlite',CAPS,True);meter.start()
 try:b=Backend(lr)
 finally:meter.stop()
 inputs=Inputs();folder=P/'private'/f'lr{lr}-r{replay}';folder.mkdir(exist_ok=True)
 if (folder/'result.json').exists():raise RuntimeError('NO_RERUN')
 start=probe(b,inputs,meter);r=Runner(b,inputs,meter,'diverse',replay,identity,folder);logs=[]
 # Wrapping the concrete optimizer provides measured update norms without altering math.
 original=b.opt.apply_gradients;norms=[]
 def measured(g,params):
  mx=b.mx;out=original(g,params);mx.eval(out,b.opt.state)
  norm=float(mx.sqrt(sum(mx.sum((out[k]-v)**2) for k,v in params.items())))
  if not math.isfinite(norm):raise RuntimeError('NONFINITE_UPDATE_NORM')
  norms.append(norm);return out
 b.opt.apply_gradients=measured
 with (folder/'updates.jsonl').open('x') as f:
  for i in range(100):
   t=time.monotonic();stats=r.one();stats.update(seconds=time.monotonic()-t,update_norm=norms[-1]);logs.append(stats);f.write(json.dumps(stats)+'\n');f.flush()
   if (i+1)%25==0:
    state=b.state()
    for k,v in state['optimizer'].items():
     if isinstance(v,dict):
      for a in v.values():
       if isinstance(a,np.ndarray) and not np.isfinite(a).all():raise RuntimeError('NONFINITE_MOMENTS')
    print(json.dumps({'lr':lr,'replay':replay,'step':i+1,'loss':stats['loss']}),flush=True)
 end=probe(b,inputs,meter)
 meter.start()
 try:r.save()
 finally:meter.stop()
 result={'lr':lr,'replay':replay,'updates':100,'source_training_losses':start,'endpoint_training_losses':end,'finite':True,'step_seconds':{'total':sum(x['seconds'] for x in logs),'median':float(np.median([x['seconds'] for x in logs])),'p95':float(np.percentile([x['seconds'] for x in logs],95))},'max_gradient_norm':max(x['gradient_norm'] for x in logs),'max_update_norm':max(norms),'early_mean_loss':float(np.mean([x['loss'] for x in logs[:20]])),'late_mean_loss':float(np.mean([x['loss'] for x in logs[-20:]])),'child_disposable':True}
 atomic(folder/'result.json',json.dumps(result,indent=2).encode())

def main():
 verify()
 if (P/'started.json').exists():raise RuntimeError('NO_IMPLICIT_RESTART')
 atomic(P/'started.json',json.dumps({'authority':'User approved bounded LR/feasibility calibration; reassess before retained training','new_updates_max':600,'new_active_seconds_max':1800,'retained_training':False}).encode())
 meter=CalibrationMeter(P/'private/study.sqlite',CAPS,True)
 # One explicit carry-forward event: source ledger is immutable, not reset or reopened.
 meter.reserve('import-approved-12-update-calibration',PRIOR['charges']['positions'],updates=12,assistant=PRIOR['charges']['assistant'],narrative=PRIOR['charges']['narrative'])
 meter.db.execute('UPDATE timing SET seconds=? WHERE id=1',(PRIOR['seconds'],));meter.db.commit();meter.db.close()
 try:
  for lr in [2e-5,1e-4,5e-4]:
   for replay in [0.,.5]:
    with (P/'private'/f'lr{lr}-r{replay}.log').open('x') as f:
     result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'worker',str(lr),str(replay)],stdout=f,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(f'WORKER_FAILED lr={lr} replay={replay}')
  meter=CalibrationMeter(P/'private/study.sqlite',CAPS,True);assert meter.totals()['updates']==612
  results=[read(P/'private'/f'lr{lr}-r{r}/result.json') for lr in [2e-5,1e-4,5e-4] for r in [0.,.5]]
  eligible=[]
  for lr in [2e-5,1e-4,5e-4]:
   pair=[x for x in results if x['lr']==lr];ratios=[x['endpoint_training_losses'][f]/v for x in pair for f,v in x['source_training_losses'].items()]
   stable=all(x['finite'] and x['late_mean_loss']<=1.10*x['early_mean_loss'] for x in pair) and max(ratios)<=1.10
   if stable:eligible.append((float(np.mean(ratios)),lr))
  selected=min(eligible)[1] if eligible else None
  atomic(P/'result.json',json.dumps({'status':'PASS' if selected else 'NO_COMMON_LR','selected_common_lr':selected,'selection_rule':'Predeclared mean endpoint/source task-loss ratio across both replay settings; all tasks <=1.10 source, late loss <=1.10 early, finite; tie chooses lower LR','training_only':True,'results':results,'cumulative_charges':meter.totals(),'cumulative_seconds':meter.seconds(),'retained_training':False},indent=2).encode());verify()
 except BaseException as e:
  atomic(P/'stop.json',json.dumps({'reason':str(e),'retained_training':False}).encode());raise
if __name__=='__main__':
 if len(sys.argv)>1:worker(float(sys.argv[2]),float(sys.argv[3]))
 else:main()
