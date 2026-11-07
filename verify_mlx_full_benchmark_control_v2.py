"""CPU-only ledger/controller helper tests; no model, checkpoint or GPU."""
import json,os,tempfile,time,unittest
from unittest.mock import patch
from pathlib import Path
import mlx_full_benchmark_control_v2 as c

class BudgetTests(unittest.TestCase):
 def setup_budget(self,root):
  run=Path(root);(run/'phases'/'BCtorch').mkdir(parents=True);c.runtime.atomic(run/'launch.json',{'baseline_swap_bytes':0});spec={'stop_paths':[]};c.initialize(spec,run,'fixture');ledger=c.read_ledger(run);ledger.update(state='running',phase='BCtorch');c.write_ledger(run,ledger);clock=[0.]
  ticket=c.runtime.make_ticket(1000,'fixture');ticket.update(watchdog_pid=os.getppid(),phase='BCtorch',benchmark_wall_started=time.time());b=c.WorkerBudget(spec,run,'BCtorch',ticket,now=lambda:clock[0],probe=False);return b,clock
 def test_reserve_commit_and_pending(self):
  with tempfile.TemporaryDirectory()as td:
   b,t=self.setup_budget(td);b.period('warmup');b.reserve(8192,'update');ledger=c.read_ledger(td);self.assertEqual(ledger['reserved_targets'],8192);self.assertEqual(ledger['committed_targets'],0)
   with self.assertRaises(c.runtime.RunnerStop):b.reserve(8192,'update')
   with self.assertRaises(c.runtime.RunnerStop):b.commit(1024,'update',{})
   b.commit(8192,'update',{'finite_loss':1.});self.assertEqual(c.read_ledger(td)['committed_targets'],8192)
 def test_no_refund_and_global_limit(self):
  with tempfile.TemporaryDirectory()as td:
   b,t=self.setup_budget(td);b.reserve(c.TOKEN_LIMIT,'fixture');b.commit(c.TOKEN_LIMIT,'fixture',{})
   with self.assertRaises(c.runtime.RunnerStop):b.reserve(1,'over')
   self.assertEqual(c.read_ledger(td)['reserved_targets'],c.TOKEN_LIMIT)
 def test_time_period_and_global(self):
  with tempfile.TemporaryDirectory()as td:
   b,t=self.setup_budget(td);b.period('warmup');t[0]=299.;b.check();self.assertEqual(c.read_ledger(td)['period_seconds']['warmup'],299.);b.period('overhead');t[0]=299.5;b.check();self.assertEqual(c.read_ledger(td)['active_seconds'],299.5)
   b.period('warmup');t[0]=301.5
   with self.assertRaises(c.runtime.RunnerStop):b.check()
 def test_gpu_guards_optional_driver(self):
  with tempfile.TemporaryDirectory()as td:
   b,t=self.setup_budget(td);b.memory(1024,2048,None,reason='installed MLX API lacks driver metric')
   for value in (None,float('nan'),-1,12*1024**3):
    with self.assertRaises(c.runtime.RunnerStop):b.memory(value,0,None)
 def test_corruption_pending_restart_and_symlink(self):
  with tempfile.TemporaryDirectory()as td:
   b,t=self.setup_budget(td);b.reserve(1,'unfinished')
   with self.assertRaises(c.runtime.RunnerStop):c.WorkerBudget(b.spec,b.run,b.phase,b.ticket,probe=False)
   p=Path(td)/'alias';p.symlink_to(Path(td)/'launch.json')
   with self.assertRaises(c.runtime.RunnerStop):c.output_bytes(td)
   v=json.loads((Path(td)/'benchmark-ledger.json').read_text());v['reserved_targets']=0;(Path(td)/'benchmark-ledger.json').write_text(json.dumps(v))
   with self.assertRaises(c.runtime.RunnerStop):c.read_ledger(td)
 def test_disk_and_stop(self):
  with tempfile.TemporaryDirectory()as td:
   b,t=self.setup_budget(td);stop=Path(td)/'STOP';stop.touch()
   with self.assertRaises(c.runtime.RunnerStop):c.storage_check({'stop_paths':[str(stop)]},td)

 def test_all_phase_result_contracts(self):
  phases=c.expected_phase_plan();self.assertEqual(len(phases),27)
  for phase in phases:
   result=dict(state='complete',phase=phase['id'],command=phase['command'],runtime=phase['runtime'],correctness_pass=True)
   if phase['command']=='sustained':result.update(prescribed_window_seconds=1800,observed_window_seconds=1800.002,last_commit_seconds=1785.,warmup_updates=10,settling_updates=2,measured_updates=300,slice_exhausted=False)
   c.validate_phase_result(phase,result)
   wrong=dict(result,phase='wrong')
   with self.assertRaises(c.runtime.RunnerStop):c.validate_phase_result(phase,wrong)
   if phase['command']=='sustained':
    for key,value in [('last_commit_seconds',1800.001),('observed_window_seconds',1799.999),('measured_updates',2047),('slice_exhausted',True),('warmup_updates',9)]:
     with self.assertRaises(c.runtime.RunnerStop):c.validate_phase_result(phase,dict(result,**{key:value}))
 def test_measured_idle_boundary_accounting(self):
  with tempfile.TemporaryDirectory()as td:
   b,t=self.setup_budget(td);b.period('measured');t[0]=1799.5;b.period('overhead');t[0]=1800.001;b.check();value=c.read_ledger(td)
   self.assertEqual(value['period_seconds']['measured'],1799.5);self.assertAlmostEqual(value['active_seconds'],1800.001);self.assertAlmostEqual(value['period_seconds']['overhead'],.501)

class RevisionTests(unittest.TestCase):
 def test_owned_file_disappears_between_walk_and_lstat(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);victim=root/'reference.json';victim.write_text('receipt');(root/'keep').write_bytes(b'abc')
   def raced_walk(*args,**kwargs):
    victim.unlink();yield str(root),[],['reference.json','keep']
   with patch.object(c.os,'walk',raced_walk):self.assertEqual(c.output_bytes(root),3)
 def test_permission_error_not_suppressed(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);victim=root/'reference.json';victim.write_text('receipt');original=Path.lstat
   def denied(path,*args,**kwargs):
    if path==victim:raise PermissionError('fixture')
    return original(path,*args,**kwargs)
   with patch.object(Path,'lstat',denied):
    with self.assertRaises(PermissionError):c.output_bytes(root)
 def test_removed_root_not_suppressed(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'run';root.mkdir();victim=root/'file';victim.write_text('x')
   def raced_walk(*args,**kwargs):
    victim.unlink();root.rmdir();yield str(root),[],['file']
   with patch.object(c.os,'walk',raced_walk):
    with self.assertRaises(c.runtime.RunnerStop):c.output_bytes(root)
 def test_cumulative_initial_reservations_and_periods(self):
  with tempfile.TemporaryDirectory() as td:
   prior=dict(reserved_targets=9216,committed_targets=9216,elapsed_wall_seconds=23.572912454605103,worker_active_seconds=21.064050334040076,period_seconds=dict(correctness=21.064050334040076,warmup=0.,measured=0.,resume=0.,overhead=0.))
   c.initialize({'prior_attempt':prior},td,'fixture');x=c.read_ledger(td)
   self.assertEqual(x['reserved_targets'],9216);self.assertEqual(x['active_seconds'],prior['elapsed_wall_seconds']);self.assertAlmostEqual(x['period_seconds']['overhead'],2.508862120565027);self.assertAlmostEqual(sum(x['period_seconds'].values()),x['active_seconds'])
 def test_disk_counts_retained_prior(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);old=root/'old';new=root/'new';old.mkdir();new.mkdir();(old/'receipt').write_bytes(b'abcd');(new/'receipt').write_bytes(b'efgh')
   with patch.object(c,'OUTPUT_LIMIT',7):
    with self.assertRaises(c.runtime.RunnerStop):c.storage_check({'prior_attempt':{'run':str(old)},'stop_paths':[]},new)

if __name__=='__main__':unittest.main()
