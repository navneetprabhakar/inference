"""Frozen argument wiring, actual suite budgets, and process-tree cleanup."""
import json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from cloud_training.nano_recovery_tasks import train_argv

class TaskWiring(unittest.TestCase):
 def test_actual_blueprint_recipes(self):
  r=json.loads(Path('reports/ganesh-controller-v1/request-template.json').read_text())
  for task in r['tasks']:
   if task.get('operation') not in ('train_fit','train_curriculum'):continue
   argv=train_argv(r,task,Path.cwd());pilot=task['operation']=='train_curriculum'
   self.assertEqual(argv[argv.index('--epochs')+1],'3' if pilot else '64')
   self.assertEqual(argv[argv.index('--max-updates')+1],'64')
   self.assertEqual('--fit-diagnostic' in argv,not pilot)
   self.assertEqual('--fit-eval-steps' in argv,not pilot)
   self.assertNotIn('--resume',argv)
   self.assertIn(str(Path.cwd()/r['training_inputs']['base']),argv)
 def test_machine_wide_writer_lock(self):
  from cloud_training.nano_sft import gpu_writer_lock
  with tempfile.TemporaryDirectory() as d:
   p=str(Path(d)/'writer.lock')
   with gpu_writer_lock(p):
    with self.assertRaises(BlockingIOError):
     with gpu_writer_lock(p):pass
   with gpu_writer_lock(p):pass
 def test_explicit_muon_mode_reaches_both_training_tasks(self):
  r=json.loads(Path('reports/ganesh-controller-v1/request-template.json').read_text())
  r['training_inputs']['muon_kernel_mode']='eager'
  for task in r['tasks']:
   if task.get('operation') in ('train_fit','train_curriculum'):
    argv=train_argv(r,task,Path.cwd())
    self.assertEqual(argv[argv.index('--muon-kernel-mode')+1],'eager')
 def test_real_frozen_budget_sum(self):
  fit=json.loads(Path('reports/english-local-readiness-v1/fit-suite.json').read_text())
  dev=json.loads(Path('reports/english-first-v1/development-suite.json').read_text())
  bound=lambda s:sum(t.get('reply_budget',128)*3 for row in s['sessions'] for t in row['turns'])
  self.assertEqual(bound(fit)*6+bound(dev)*3,228096)
 def test_signal_joins_detached_probe_worker(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);out=root/'report.json';out.write_text('{"status":"loading"}')
   pidfile=root/'pid'
   child="import os,time;from pathlib import Path;Path("+repr(str(pidfile))+").write_text(str(os.getpid()));time.sleep(60)"
   parent="from cloud_training.nano_quality import supervise;import sys;supervise([sys.executable,'-c',"+repr(child)+"],"+repr(str(out))+",60)"
   process=subprocess.Popen([sys.executable,'-c',parent],start_new_session=True)
   try:
    limit=time.monotonic()+10
    while not pidfile.exists() and time.monotonic()<limit:time.sleep(.05)
    self.assertTrue(pidfile.exists());pid=int(pidfile.read_text())
    os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=5)
    with self.assertRaises(ProcessLookupError):os.kill(pid,0)
   finally:
    if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
if __name__=='__main__':unittest.main()
