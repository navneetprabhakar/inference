"""CPU-only worker dispatch/accounting/parity controls; no live checkpoint or GPU."""
import contextlib,copy,pathlib,tempfile,unittest
from unittest.mock import patch
import numpy as np
import mlx_full_benchmark_worker as worker
import mlx_full_benchmark_control as control

class Clock:
 def __init__(self):self.now=0.
 def monotonic(self):return self.now
 def sleep(self,n):self.now+=n

class Budget:
 def __init__(self):self.operations=[];self.pending=None;self.periods=[]
 def period(self,n):self.periods.append(n)
 def check(self):pass
 def reserve(self,n,k):
  if self.pending:raise ValueError('pending fixture')
  self.pending=(n,k)
 def commit(self,n,k,m):
  if self.pending!=(n,k):raise ValueError('commit fixture')
  self.operations.append((n,k,m));self.pending=None

class Checks(unittest.TestCase):
 def test_every_frozen_command_dispatch_and_result_schema(self):
  calls={'source-convert':'source_convert','cleanup':'cleanup','sustained':'sustained','resume-reference':'resume_phase','resume-pause':'resume_phase','resume-check':'resume_phase'}
  for phase in control.expected_phase_plan():
   name=calls.get(phase['command'],'correctness');result=dict(correctness_pass=True)
   if phase['command']=='sustained':result.update(prescribed_window_seconds=1800.,observed_window_seconds=1800.1,last_commit_seconds=1789.,warmup_updates=10,settling_updates=2,measured_updates=100,slice_exhausted=False)
   with self.subTest(phase=phase['id']),patch.object(worker,name,return_value=result) as fn:
    actual=worker.execute_command({},pathlib.Path('/not-used'),phase,None);fn.assert_called_once();control.validate_phase_result(phase,worker.result_payload(phase,actual,1.))
  with self.assertRaises(ValueError):worker.execute_command({},pathlib.Path('/not-used'),dict(command='not-authorized'),None)
 def test_causal_prefix_rejects_future_leak(self):
  original=np.zeros((2,512,3),dtype=np.float32);changed=original.copy();changed[:,256:]=7
  self.assertEqual(worker.prefix_difference(original,changed)['max_abs'],0.)
  changed[0,100,0]=.01
  with self.assertRaisesRegex(ValueError,'causal-prefix'):worker.prefix_difference(original,changed)
 def test_environment_rejects_wrong_interpreter_and_versions_before_allocation(self):
  import sys,importlib.metadata
  spec={'python':{'torch':'/wrong/python'},'versions':{}}
  phase={'runtime':'torch-cpu'}
  with patch.object(control,'validate_spec',return_value=spec):
   with self.assertRaisesRegex(ValueError,'interpreter'):worker.validate_worker_environment(spec,phase)
   spec['python']['torch']=sys.executable;spec['versions']['torch']={'python':'wrong','torch':'wrong','numpy':'wrong'}
   with self.assertRaisesRegex(ValueError,'versions'):worker.validate_worker_environment(spec,phase)
 def test_worker_delegates_fixed_spec_tolerance_gate(self):
  with self.assertRaisesRegex(control.runtime.RunnerStop,'reviewed benchmark'):worker.validate_worker_environment({'schema':1,'state':'pending_root_review'},{'runtime':'torch-cpu'})
 def test_cpu_accumulation_refreshes_budget_each_microbatch(self):
  import torch,gpt2
  from unittest.mock import Mock
  engine=worker.Engine.__new__(worker.Engine);engine.runtime='torch-cpu';engine.device='cpu';engine.torch=torch;engine.model=torch.nn.Linear(1,1);engine.optimizer=torch.optim.SGD(engine.model.parameters(),lr=.01);engine.budget=Mock();engine.progress=0;engine.sync=lambda:None;engine.memory=lambda:None;engine.tensor=lambda row:row
  row=np.zeros((2,513),dtype=np.int32)
  with patch.object(gpt2,'next_token_loss',side_effect=lambda model,seq:sum(p.square().sum() for p in model.parameters())):
   engine.update([row]*8)
  self.assertEqual(engine.budget.check.call_count,8);self.assertEqual(engine.progress,1)
 def test_chunked_full_tensor_comparison_and_delta(self):
  reference={'embedding':np.ones((70000,),dtype=np.float32),'bias':np.zeros((3,),dtype=np.float32)};actual={k:v.copy() for k,v in reference.items()};actual['embedding'][-1]+=np.float32(.001)
  result=worker.difference(actual,reference,baseline={k:np.zeros_like(v) for k,v in reference.items()});self.assertGreater(result['max_abs'],.0009);self.assertEqual(result['per_tensor_max_abs']['bias'],0.);self.assertGreater(result['update_delta_relative_l2'],0.)
  actual['bias'][0]=np.nan
  with self.assertRaises(ValueError):worker.difference(actual,reference)
 def simulate(self,step_seconds):
  clock=Clock();budget=Budget();row=np.zeros((2,513),dtype=np.int32)
  class Engine:
   compiled=False
   def __init__(self,*args):pass
   def update(self,rows):clock.now+=step_seconds;return 1.,2.
   def restore(self):pass
   def evaluate(self,rows):return dict(loss=1.)
  class Data:
   def __init__(self,*args):pass
   def batch(self,*args):return row
   def validation_batch(self):return row
  phase=dict(id='Bcpu-test',command='sustained',runtime='torch-mps-fp32')
  with contextlib.ExitStack() as stack:
   for name,value in [('Engine',Engine),('Data',Data),('load_arrays',lambda _:({'neutral':{}},{})),('checkpoint_io',lambda *args:dict(save_seconds=1.,read_seconds=1.))]:stack.enter_context(patch.object(worker,name,value))
   stack.enter_context(patch.object(worker.time,'monotonic',clock.monotonic));stack.enter_context(patch.object(worker.time,'sleep',clock.sleep))
   return worker.sustained(dict(benchmark_identity={}),pathlib.Path('/not-used'),phase,budget),budget
 def test_fixed_window_actual_elapsed_idle_and_reserved_targets(self):
  result,budget=self.simulate(2.)
  self.assertEqual(result['prescribed_window_seconds'],1800.);self.assertGreaterEqual(result['observed_window_seconds'],1800.);self.assertLessEqual(result['last_commit_seconds'],1800.)
  self.assertGreater(result['ending_idle_seconds'],0.);self.assertEqual(result['settling_updates'],2);self.assertEqual(result['warmup_updates'],10)
  self.assertEqual(sum(x[0] for x in budget.operations),(12+result['measured_updates'])*8192+1024)
  self.assertEqual(result['targets_per_second'],result['measured_updates']*8192/1800)
  self.assertEqual(sum(b['targets'] for b in result['contiguous_five_minute_bins']),result['targets']);self.assertIsNone(budget.pending)
 def test_fixed_slice_exhaustion_is_incomplete_not_cycled(self):
  with self.assertRaisesRegex(ValueError,'slice exhausted'):self.simulate(.1)
 def test_gate_result_cannot_be_claimed_without_required_metrics(self):
  phase=next(p for p in control.expected_phase_plan() if p['command']=='sustained')
  with self.assertRaises(Exception):control.validate_phase_result(phase,worker.result_payload(phase,{},1.))
if __name__=='__main__':unittest.main(verbosity=2)
