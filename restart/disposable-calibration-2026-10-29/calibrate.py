"""Authorized12-update engineering calibration. Separate processes test real reload."""
import sys,json,pickle,hashlib,gc,subprocess,os,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];READY=HERE.parent/'runner-readiness-2026-10-29'
sys.path.insert(0,str(READY))
from runner import Backend,Inputs,Runner,Meter,read,sha,atomic
LIMITS=dict(positions=2000000,updates=12,assistant=10000,narrative=50000,seconds=600)

def verify():
 for directory,names in [(READY,['freeze.json','preservation-freeze.json','gradient-freeze.json','launch-freeze.json']),(HERE,['freeze.json'])]:
  for name in names:
   for f,h in read(directory/name)['files'].items():
    if sha(ROOT/f)!=h:raise RuntimeError('FROZEN_INPUT_CHANGED:'+f)
 return sha(HERE/'freeze.json')

def digest_tree(x):
 h=hashlib.sha256()
 def rec(a):
  if isinstance(a,dict):
   for k in sorted(a):h.update(str(k).encode());rec(a[k])
  elif isinstance(a,(list,tuple)):
   for v in a:rec(v)
  elif isinstance(a,np.ndarray):h.update(str(a.dtype).encode());h.update(str(a.shape).encode());h.update(a.tobytes())
  else:h.update(repr(a).encode())
 rec(x);return h.hexdigest()

def attach_optimizer_check(b,records):
 original=b.opt.apply_gradients
 def checked(grad,params):
  mx=b.mx;mx.eval(grad,params,b.opt.state)
  step=int(b.opt.state['step'])+1
  # Independent NumPy reference: same clipped gradients supplied to actual optimizer.
  expected={};expected_m={};expected_v={}
  for k,p in params.items():
   g=np.array(grad[k]);m=np.array(b.opt.state[k]['m']);v=np.array(b.opt.state[k]['v']);m=np.float32(.9)*m+np.float32(.1)*g;v=np.float32(.95)*v+np.float32(.05)*g*g
   expected_m[k]=m;expected_v[k]=v
   mh=m/(1-.9**step);vh=v/(1-.95**step);expected[k]=np.array(p)-np.float32(2e-5)*mh/(np.sqrt(vh)+np.float32(1e-8))
  out=original(grad,params);mx.eval(out,b.opt.state)
  errors=dict(parameters=0.,first_moment=0.,second_moment=0.)
  for k in out:
   for label,actual,ref in [('parameters',np.array(out[k]),expected[k]),('first_moment',np.array(b.opt.state[k]['m']),expected_m[k]),('second_moment',np.array(b.opt.state[k]['v']),expected_v[k])]:
    errors[label]=max(errors[label],float(np.max(np.abs(actual-ref))))
    if not np.all(np.isfinite(actual)) or not np.allclose(actual,ref,rtol=2e-5,atol=2e-7):raise RuntimeError('NUMPY_ADAM_MISMATCH:'+label+':'+k)
  if int(b.opt.state['step'])!=step:raise RuntimeError('OPTIMIZER_STEP_MISMATCH')
  records.append({'optimizer_step':step,'max_abs_error':errors,'reference':'independent NumPy Adam equations on actual clipped gradients','rtol':2e-5,'atol':2e-7})
  return out
 b.opt.apply_gradients=checked

def worker(coefficient,path_kind,segment):
 identity=verify();meter=Meter(HERE/'private/calibration.sqlite',LIMITS,True);meter.start()
 try:b=Backend(2e-5)
 finally:meter.stop()
 start_hash=b.digest();inputs=Inputs();folder=HERE/'private'/f'r{coefficient}-{path_kind}';r=Runner(b,inputs,meter,'diverse',coefficient,identity,folder)
 if segment=='resume':
  meter.start()
  try:r.restore()
  finally:meter.stop()
  if r.cursor!=1 or b.steps!=1 or int(b.opt.state['step'])!=1:raise RuntimeError('BAD_RESUME_CURSOR')
 elif folder.joinpath('checkpoint.pkl').exists():raise RuntimeError('IMPLICIT_RERUN')
 checks=[];attach_optimizer_check(b,checks)
 until=1 if segment=='interrupt' else 3;logs=[]
 while r.cursor<until:
  stats=r.one();logs.append({'cursor':r.cursor,**stats,'optimizer_check':checks[-1]})
  atomic(folder/f'step-{r.cursor}.json',json.dumps(logs[-1],indent=2).encode())
 if b.digest()==start_hash:raise RuntimeError('NO_PARAMETER_CHANGE')
 endpoint=None
 if until==3:
  batch,_=inputs.batch('diverse',3,0);meter.reserve('next-prediction',int(batch[0].size));meter.start()
  try:
   from mlx.utils import tree_unflatten
   mx=b.mx;b.e.model.update(tree_unflatten([(k,v.astype(mx.bfloat16)) for k,v in b.e.params.items()]));logits=b.e.model(mx.array(batch[0])).astype(mx.float32);mx.eval(logits);arr=np.array(logits)
   if not np.isfinite(arr).all():raise RuntimeError('NONFINITE_PREDICTIONS')
   endpoint={'logits_sha256':hashlib.sha256(arr.tobytes()).hexdigest(),'argmax_sha256':hashlib.sha256(arr.argmax(-1).tobytes()).hexdigest(),'prediction_positions':int(batch[0].size)}
  finally:meter.stop()
 meter.start()
 try:snapshot=r.save()
 finally:meter.stop()
 summary={'coefficient':coefficient,'path':path_kind,'segment':segment,'pid':os.getpid(),'cursor':r.cursor,'parameters':digest_tree(snapshot['state']['params']),'optimizer':digest_tree(snapshot['state']['optimizer']),'rng':digest_tree(snapshot['state']['rng']),'prediction':endpoint,'checks':checks,'charges':meter.totals()}
 atomic(folder/(segment+'-result.json'),json.dumps(summary,indent=2).encode());print(json.dumps(summary),flush=True)

def main():
 verify()
 if (HERE/'started.json').exists():raise RuntimeError('NO_IMPLICIT_CALIBRATION_RESTART')
 atomic(HERE/'started.json',json.dumps({'authority':'User approved exactly12 disposable updates and reassessment before retained training','limits':LIMITS,'retained_training':False}).encode())
 comparisons=[]
 try:
  for coefficient in [0.0,0.5]:
   for kind,seg in [('continuous','continuous'),('resumed','interrupt'),('resumed','resume')]:
    log=HERE/'private'/f'{coefficient}-{seg}.log'
    with log.open('x') as handle:
     result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'worker',str(coefficient),kind,seg],stdout=handle,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError('WORKER_FAILED:'+str(log))
   a=read(HERE/'private'/f'r{coefficient}-continuous/continuous-result.json');b=read(HERE/'private'/f'r{coefficient}-resumed/resume-result.json');first=read(HERE/'private'/f'r{coefficient}-resumed/interrupt-result.json')
   for field in ['parameters','optimizer','rng','prediction']:
    if a[field]!=b[field]:raise RuntimeError('RESUME_MISMATCH:'+field)
   assert first['pid']!=b['pid']
   comparisons.append({'replay':coefficient,'parameters_exact':True,'optimizer_exact':True,'rng_exact':True,'next_logits_exact':True,'restart_in_new_process':True})
   atomic(HERE/'comparisons.json',json.dumps(comparisons,indent=2).encode())
  meter=Meter(HERE/'private/calibration.sqlite',LIMITS,True);tot=meter.totals();assert tot['updates']==12
  verify()
  atomic(HERE/'result.json',json.dumps({'status':'PASS','comparisons':comparisons,'charges':tot,'seconds':meter.seconds(),'retained_training':False,'learning_rate':2e-5,'learning_rate_selected_for_screen':False},indent=2).encode())
 except BaseException as ex:
  atomic(HERE/'stop.json',json.dumps({'reason':str(ex),'retained_training':False}).encode());raise
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='worker':worker(float(sys.argv[2]),sys.argv[3],sys.argv[4])
 else:main()
