"""Tiny CPU-only checks; no full model, production checkpoints or GPU calls."""
import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
REPORT=ROOT/'reports/mlx-sequential-accumulation-proposal-v1'
SPEC=json.loads((REPORT/'cpu-protocol.json').read_text())
for name,expected in SPEC['code_sha256'].items():
 if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('changed CPU protocol pin:'+name)
import mlx.core as mx
mx.set_default_device(mx.cpu)
from mlx_sequential_train_core import SequentialTrainCore,check_memory
from mlx_train_core import TrainCore,Config,accumulated_gradients
CFG=Config(**SPEC['config'])
assert CFG.width==32 and CFG.depth==2 and mx.default_device()==mx.cpu

def initial(seed):
 p=ROOT/f'reports/mlx-own-base-feasibility/torch-seed-{seed}.npz'
 assert hashlib.sha256(p.read_bytes()).hexdigest()==SPEC['fixture_sha256'][str(seed)]
 with np.load(p,allow_pickle=False) as f:return {n:f[n] for n in f.files}
def params(seed):return {n[9:]:v for n,v in initial(seed).items() if n.startswith('initial::')}
def data(seed,step):
 rng=np.random.default_rng(seed+step*13)
 return [mx.array(rng.integers(CFG.vocabulary,size=(1+i%2,7+i%3),dtype=np.int32)) for i in range(8)]
def save(path,meta,arrays):
 np.savez(path,**arrays);path.with_suffix('.json').write_text(json.dumps(meta))
def read(path):
 with np.load(path,allow_pickle=False) as f:arrays={n:f[n] for n in f.files}
 return json.loads(path.with_suffix('.json').read_text()),arrays
def restored(path,beta):
 meta,arrays=read(path);p={n[8:]:v for n,v in arrays.items() if n.startswith('weight::')}
 return SequentialTrainCore(p,CFG,device=mx.cpu,betas=(.9,beta),clip=.15,restored=(meta,arrays))
def compare(a,b,tolerance):
 assert set(a)==set(b)
 for n in a:
  assert a[n].shape==b[n].shape and a[n].dtype==b[n].dtype,n
  assert np.max(np.abs(a[n].astype(float)-b[n].astype(float)))<=tolerance,n

class Checks(unittest.TestCase):
 def test_torch_reference_three_seeds(self):
  for seed in SPEC['seeds']:
   ref=initial(seed);seq=mx.array(ref['sequence'].astype(np.int32));core=SequentialTrainCore(params(seed),CFG,device=mx.cpu)
   # Same weighted derivative as original Torch fixture, now materialized one at a time.
   grads=None
   for batch in [seq[:1],seq[1:]]:
    v,g=core._micro(core.params,batch,mx.array(batch.shape[0]/seq.shape[0],dtype=mx.float32));grads=g if grads is None else {n:grads[n]+g[n] for n in g};mx.eval(grads,v)
   self.assertLessEqual(max(float(np.max(np.abs(np.array(g)-ref['gradient::'+n])))for n,g in grads.items()),5e-5)
   loss,norm=core.step([seq[:1],seq[1:]],learning_rate=.001);_,state=core.snapshot()
   self.assertLessEqual(abs(loss-float(ref['loss'])),2e-6)
   self.assertLessEqual(max(float(np.max(np.abs(state['weight::'+n]-ref['updated::'+n])))for n in core.params),2e-5)
 def test_six_cases_compiled_eager_reference_lr_unequal_and_fresh_resume(self):
  for seed in SPEC['seeds']:
   for beta in SPEC['beta2_values']:
    with tempfile.TemporaryDirectory() as td:
     path=Path(td);kwargs=dict(device=mx.cpu,betas=(.9,beta),clip=.15)
     compiled=SequentialTrainCore(params(seed),CFG,**kwargs);eager=SequentialTrainCore(params(seed),CFG,compiled=False,**kwargs);reference=TrainCore(params(seed),CFG,compiled=False,**kwargs);trace=[];total=0
     for step,lr in enumerate(SPEC['learning_rates']):
      batch=data(seed,step);total+=sum(x.shape[0]*(x.shape[1]-1)for x in batch)
      cl,cn=compiled.step(batch,learning_rate=lr);el,en=eager.step(batch,learning_rate=lr);rl,rn=reference.step(batch,learning_rate=lr)
      cm,ca=compiled.snapshot();em,ea=eager.snapshot();rm,ra=reference.snapshot()
      compare(ca,ea,2e-5);compare(ca,ra,2e-5);self.assertEqual(cm,em);self.assertEqual(cm,rm)
      self.assertLessEqual(max(abs(cl-el),abs(cl-rl)),3e-6);self.assertLessEqual(max(abs(cn-en),abs(cn-rn)),3e-5)
      self.assertEqual(cm['cursor'],dict(step=step+1,trained_tokens=total));self.assertEqual(int(ca['group_step::0']),step+1);self.assertEqual(int(ca['group_step::1']),step+1)
      self.assertTrue(all(x.dtype==np.float32 for n,x in ca.items() if n.startswith(('weight::','m::','v::'))));trace.append([cl,cn])
      if step==1:save(path/'pause.npz',cm,ca)
     save(path/'expected.npz',cm,ca);(path/'trace.json').write_text(json.dumps(trace[2:]));proc=subprocess.run([sys.executable,str(Path(__file__).resolve()),'resume',str(path),str(seed),str(beta)],timeout=60,capture_output=True,text=True);self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
 def test_parameters_frozen_until_single_update(self):
  core=SequentialTrainCore(params(SPEC['seeds'][0]),CFG,device=mx.cpu);before={n:np.array(p) for n,p in core.params.items()};seen=[]
  def observe(stage,index):
   seen.append((stage,index))
   if stage!='after_optimizer':
    self.assertTrue(all(np.array_equal(np.array(p),before[n]) for n,p in core.params.items()))
    self.assertEqual(int(core.optimizers[0].state['step'].item()),0)
   else:self.assertEqual(int(core.optimizers[0].state['step'].item()),1)
  core.boundary=observe;core.step(data(4817,0),learning_rate=.001);self.assertEqual(seen,[("microbatch",i)for i in range(8)]+[('before_optimizer',8),('after_optimizer',8)])
 def test_failures_poison_no_publication_or_cursor(self):
  for failure_stage in ('microbatch','after_optimizer'):
   def fail(stage,index):
    if stage==failure_stage:raise RuntimeError('injected guard failure')
   core=SequentialTrainCore(params(4817),CFG,device=mx.cpu,boundary=fail)
   with self.assertRaisesRegex(RuntimeError,'injected'):core.step(data(4817,0),learning_rate=.001)
   self.assertEqual(core.cursor,dict(step=0,trained_tokens=0));self.assertTrue(core.poisoned)
   with self.assertRaises(RuntimeError):core.snapshot()
   with self.assertRaises(RuntimeError):core.step(data(4817,1),learning_rate=.001)
 def test_memory_peak_cache_rss_and_missing(self):
  good=dict(active=1024,peak=2048,cache=0,rss=4096);check_memory(**good)
  for field,value in [('active',12*1024**3),('peak',12*1024**3),('cache',1024**3+1),('rss',18*1024**3+1),('peak',None),('cache',float('nan'))]:
   with self.assertRaises(RuntimeError):check_memory(**dict(good,**{field:value}))
 def test_bad_input_and_gpu_missing_guard_refused(self):
  core=SequentialTrainCore(params(4817),CFG,device=mx.cpu)
  with self.assertRaises(ValueError):core.step([],learning_rate=.001)
  with self.assertRaises(ValueError):core.step(data(4817,0),learning_rate=float('nan'))
  # Fails before super constructor/allocation, no GPU operation.
  with self.assertRaises(ValueError):SequentialTrainCore(params(4817),CFG,device=mx.gpu)
  self.assertFalse(core.poisoned)

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='resume':
  path=Path(sys.argv[2]);seed=int(sys.argv[3]);beta=float(sys.argv[4]);core=restored(path/'pause.npz',beta);trace=[]
  for step in (2,3):trace.append(list(core.step(data(seed,step),learning_rate=SPEC['learning_rates'][step])))
  meta,arrays=core.snapshot();expected_meta,expected=read(path/'expected.npz');assert meta==expected_meta and all(np.array_equal(arrays[n],expected[n])for n in arrays);assert trace==json.loads((path/'trace.json').read_text())
 else:unittest.main()
