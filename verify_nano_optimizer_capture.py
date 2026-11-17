"""Local capture integrity, actual optimizer noninterference and replay checks."""
import copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import torch
from cloud_training import nano_optimizer_capture as cap

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runs/nanochat-source'))
from nanochat import optim

class CaptureTests(unittest.TestCase):
 def setup_optimizer(self):
  torch.manual_seed(732)
  ps=[torch.nn.Parameter(torch.randn(4,8)) for _ in range(2)]
  opt=optim.MuonAdamW([{'kind':'muon','params':ps,'lr':.005,'momentum':.95,'beta2':.95,'weight_decay':0.,'ns_steps':5}])
  for p in ps:p.grad=torch.randn_like(p)
  return ps,opt
 def capture(self,path):
  ps,opt=self.setup_optimizer()
  # Use upstream Python implementation for unit checks; compiled replay is separate.
  with patch.object(optim,'muon_step_fused',optim.muon_step_fused.__wrapped__):
   with cap.capture_step(optim,opt,zip(['target','other'],ps),path,step=1,parameter='target',identity={'test':1}):opt.step()
  return ps,opt
 def test_alias_offset_transpose_roundtrip_and_independent_snapshot(self):
  x=torch.arange(24.).reshape(4,6)
  args=[x[1:],x.t(),torch.tensor(.5),-2]
  snap=cap.snapshot(args,4096);restored=cap.restore(snap)
  self.assertTrue(cap.exact(snap,cap.snapshot(restored,4096)))
  self.assertEqual(restored[0].untyped_storage().data_ptr(),restored[1].untyped_storage().data_ptr())
  self.assertEqual(restored[0].storage_offset(),6)
  x.add_(100);self.assertEqual(restored[0][0,0].item(),6.)
  restored[0][0,0]=73;self.assertEqual(restored[1][0,1].item(),73.)
 def test_signed_zero_is_not_exact(self):
  self.assertFalse(cap.exact(cap.snapshot([torch.tensor([0.])],64),cap.snapshot([torch.tensor([-0.])],64)))
 def test_unsupported_layout_and_mixed_dtype_alias_rejected(self):
  x=torch.ones(8)
  for args in [[x.expand(2,8)],[x,x.view(torch.int32)],[x[::2]]]:
   with self.assertRaises(ValueError):cap.snapshot(args,4096)
 def test_budget_checked_before_copy(self):
  with self.assertRaisesRegex(ValueError,'bound'):cap.snapshot([torch.zeros(32)],4)
 def test_config_requires_isolated_diagnostic_and_trace(self):
  self.assertIsNone(cap.config(SimpleNamespace()))
  for obj in [dict(capture_muon_step=1),dict(capture_muon_step=1,fit_diagnostic=True,trace_updates=1),dict(capture_muon_step=2,fit_diagnostic=True,trace_updates=2)]:
   with self.assertRaises(ValueError):cap.config(SimpleNamespace(**obj))
  self.assertEqual(cap.config(SimpleNamespace(capture_muon_step=1,fit_diagnostic=True,trace_updates=2))['absolute_step'],1)
 def test_capture_does_not_change_actual_update_gradients_or_rng(self):
  a,oa=self.setup_optimizer();b,ob=self.setup_optimizer();rng=torch.get_rng_state().clone()
  with tempfile.TemporaryDirectory() as d,patch.object(optim,'muon_step_fused',optim.muon_step_fused.__wrapped__):
   oa.step()
   with cap.capture_step(optim,ob,zip(['target','other'],b),Path(d)/'c',step=1,parameter='target',identity={'test':1}):ob.step()
   self.assertTrue(torch.equal(rng,torch.get_rng_state()))
   for x,y in zip(a,b):self.assertTrue(torch.equal(x,y));self.assertTrue(torch.equal(x.grad,y.grad))
   for k in oa.state[a[0]]:self.assertTrue(torch.equal(oa.state[a[0]][k],ob.state[b[0]][k]))
   meta,before,after=cap.load_capture(Path(d)/'c');self.assertEqual(meta['parameter_names'],['target','other'])
   self.assertFalse(cap.exact(before,after))
 def test_exception_restores_hook_and_uncommitted_capture_rejected(self):
  p,o=self.setup_optimizer();original=optim.muon_step_fused
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'c'
   with self.assertRaises(RuntimeError):
    with cap.capture_step(optim,o,zip(['target','other'],p),path,step=1,parameter='target',identity={}):raise RuntimeError('injected')
   self.assertIs(optim.muon_step_fused,original);self.assertFalse(hasattr(optim,'_own_capture_active'))
   with self.assertRaises(FileNotFoundError):cap.load_capture(path)
 def test_missing_target_and_schedule_fail_closed(self):
  p,o=self.setup_optimizer()
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'Target'):
    with cap.capture_step(optim,o,zip(['target','other'],p),Path(d)/'x',step=1,parameter='absent',identity={}):pass
   with self.assertRaisesRegex(ValueError,'schedule'):
    with cap.capture_step(optim,o,zip(['target','other'],p),Path(d)/'y',step=1,parameter='target',identity={}):pass
   self.assertFalse((Path(d)/'y'/'COMMITTED').exists())
 def test_bound_prevents_kernel_and_restores_hook(self):
  p,o=self.setup_optimizer();original=optim.muon_step_fused
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'bound'):
    with cap.capture_step(optim,o,zip(['target','other'],p),Path(d)/'x',step=1,parameter='target',identity={},max_bytes=100):o.step()
   self.assertIs(optim.muon_step_fused,original)
 def test_corruption_and_overwrite_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'c';self.capture(path)
   with self.assertRaises(FileExistsError):self.capture(path)
   with (path/'before.pt').open('ab') as f:f.write(b'corruption')
   with self.assertRaisesRegex(ValueError,'integrity'):cap.load_capture(path)
 def test_replay_checks_environment_and_matches_eager(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'c';self.capture(path)
   r=cap.replay(path,optim,'eager',Path(d)/'out');self.assertTrue(r['repeatable_exact'])
   self.assertTrue(all(x['matches_captured_output_exact'] for x in r['calls']))
   with patch.object(optim,'COMPUTE_DTYPE',torch.float64):
    with self.assertRaisesRegex(ValueError,'environment'):cap.replay(path,optim,'eager',Path(d)/'bad')
 def test_cli_restores_captured_cublas_workspace_across_process(self):
  with tempfile.TemporaryDirectory() as d:
   for index,recorded in enumerate((':4096:8',None)):
    path=Path(d)/('capture-'+str(index));out=Path(d)/('replay-'+str(index))
    with patch.dict(os.environ,{},clear=False):
     if recorded is None:os.environ.pop('CUBLAS_WORKSPACE_CONFIG',None)
     else:os.environ['CUBLAS_WORKSPACE_CONFIG']=recorded
     self.capture(path)
    env=dict(os.environ)
    if recorded is None:env['CUBLAS_WORKSPACE_CONFIG']=':16:8'
    else:env.pop('CUBLAS_WORKSPACE_CONFIG',None)
    child=subprocess.run([sys.executable,'-m','cloud_training.nano_optimizer_capture','--capture',str(path),'--repo',str(ROOT/'runs/nanochat-source'),'--mode','eager','--output',str(out)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
    self.assertEqual(child.returncode,0,child.stderr)
    result=json.loads((out/'result.json').read_text())
    self.assertEqual(result['environment']['cublas_workspace'],recorded)
    self.assertTrue(result['repeatable_exact'])
    self.assertTrue(all(call['matches_captured_output_exact'] for call in result['calls']))
 def test_actual_sft_loop_captures_only_declared_update(self):
  command=[sys.executable,'-m','reports.english-first-v1.check_loop']
  args={'updates':2,'losses':[3.,2.9,2.8],'capture_step':1}
  result=json.loads(subprocess.check_output(command+[json.dumps(args)],text=True))
  self.assertEqual(result['capture_steps'],[1]);self.assertEqual(result['step'],2)
  args.pop('capture_step')
  result=json.loads(subprocess.check_output(command+[json.dumps(args)],text=True))
  self.assertEqual(result['capture_steps'],[])
 def test_package_closure(self):
  from cloud_training.nano_package import verify_module_closure
  self.assertEqual(verify_module_closure(ROOT)['missing'],[])

if __name__=='__main__':unittest.main()
