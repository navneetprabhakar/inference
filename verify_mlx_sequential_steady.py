"""Tiny CPU native adapter + simulated steady clock; never allocates GPU."""
import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
import numpy as np
import mlx_sequential_steady as s
import mlx_own_base_adapter as bridge
ROOT=Path(__file__).resolve().parent

class ClockTests(unittest.TestCase):
 def test_window_exact_denominator_idle_and_bins(self):
  clock=[0.]
  def update(index,kind):clock[0]+=4.;return dict(index=index,seconds=4.,loss=1.,norm=1.)
  def sleep(seconds):clock[0]+=seconds
  x=s.measured_window(update,lambda:None,now=lambda:clock[0],sleep=sleep,settling_seconds=4.)
  self.assertEqual(x['prescribed_seconds'],600);self.assertGreaterEqual(x['observed_seconds'],600);self.assertLessEqual(x['last_commit_seconds'],600);self.assertEqual(sum(x['bins_100_seconds']),x['targets']);self.assertEqual(x['targets_per_second'],x['targets']/600)
 def test_slice_exhaustion_no_cycling(self):
  clock=[0.]
  def update(index,kind):clock[0]+=.1;return dict(seconds=.1)
  with self.assertRaises(s.rt.RunnerStop):s.measured_window(update,lambda:None,now=lambda:clock[0],sleep=lambda _:None,settling_seconds=.1)
 def test_nonrefundable_phase_budget(self):
  with tempfile.TemporaryDirectory()as td:
   p=Path(td);(p/'phases'/'steady').mkdir(parents=True);s.rt.atomic(p/'launch.json',dict(baseline_swap_bytes=0));s.rt.atomic(p/'ledger.json',dict(reserved_targets=s.LIMITS['attempted_targets']-8192,committed_targets=0,pending=None));b=s.Budget({'stop_paths':[]},p,s.rt.make_ticket(1200),'steady',probe=False);b.reserve(8192,'test')
   with self.assertRaises(s.rt.RunnerStop):b.reserve(8192,'test')
   b.commit({'loss':1})
   with self.assertRaises(s.rt.RunnerStop):b.reserve(1024,'validation')

class NativeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.path=Path(sys.argv[2]);v=json.loads((cls.path/'fixture.json').read_text());cls.meta=v['meta'];cls.pinned=v['pinned'];cls.identity=v['identity']
  with np.load(cls.path/'fixture.npz',allow_pickle=False)as f:cls.arrays={n:f[n]for n in f.files if n!='batch'};cls.batch=f['batch']
 def model(self):return Native(self.meta,self.arrays,pinned=self.pinned,benchmark_identity=self.identity,device=mx.cpu)
 def step(self,m):return m.step([mx.array(self.batch[:1]),mx.array(self.batch[1:])],learning_rate=6e-5)
 def test_restore_compiled_identity_and_distinct_cursors(self):
  m=self.model();before=m.digest_state();callables=(id(m.core._micro),id(m.core._apply));self.step(m);m.restore_source_in_place(self.arrays,pinned=self.pinned);self.assertEqual(before,m.digest_state());self.assertEqual(callables,(id(m.core._micro),id(m.core._apply)));self.assertEqual(m.progress['optimizer_step'],3);self.assertEqual(m.progress['committed_updates'],0)
 def test_full_digest_matches_snapshot_and_scalar_shapes(self):
  m=self.model();self.step(m);meta,arrays=m.snapshot();d=m.digest_state();self.assertEqual(d['metadata'],meta);self.assertEqual(set(d['arrays']),set(arrays))
  import hashlib
  for n,a in arrays.items():self.assertEqual(d['arrays'][n],dict(shape=list(a.shape),dtype=str(a.dtype),sha256=hashlib.sha256(a.tobytes()).hexdigest()))
 def test_fresh_process_resume_exact_one_checkpoint(self):
  m=self.model();trace=[self.step(m)for _ in range(4)];expected=m.digest_state();(self.path/'expected.json').write_text(json.dumps(dict(digest=expected,trace=trace[2:])))
  n=self.model();self.step(n);self.step(n);meta,arrays=n.snapshot();bridge.publish(self.path/'native',meta,arrays,benchmark_identity=n.identity,source_provenance=n.provenance);self.assertEqual(len(list((self.path/'native').glob('*.npz'))),1)
  result=subprocess.run([sys.executable,__file__,'--resume',str(self.path)],capture_output=True,text=True,timeout=60);self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(len(list((self.path/'native').glob('*.npz'))),1)
 def test_native_wrong_identity_counter_moment_refusals(self):
  m=self.model();meta,arrays=m.snapshot()
  for kind in ['identity','counter','moment']:
   cm=copy.deepcopy(meta);ca=dict(arrays);identity=m.identity
   if kind=='identity':identity={'wrong':True}
   if kind=='counter':cm['benchmark_progress']['source_offset']+=1
   if kind=='moment':ca.pop('m::tokens.weight')
   with self.assertRaises(ValueError):Native.from_native(cm,ca,benchmark_identity=identity,source_provenance=m.provenance,device=mx.cpu)

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]in ('--cpu','--resume'):
  import mlx.core as mx
  mx.set_default_device(mx.cpu)
  from mlx_sequential_native import SequentialNative as Native
  if sys.argv[1]=='--resume':
   p=Path(sys.argv[2]);v=json.loads((p/'native/accepted.json').read_text());meta,arrays=bridge.read_native(p/'native',benchmark_identity=v['metadata']['benchmark_identity'],source_provenance=v['metadata']['source_provenance']);m=Native.from_native(meta,arrays,benchmark_identity=meta['benchmark_identity'],source_provenance=meta['source_provenance'],device=mx.cpu)
   with np.load(p/'fixture.npz')as f:batch=mx.array(f['batch'])
   trace=[m.step([batch[:1],batch[1:]],learning_rate=6e-5)for _ in range(2)];expected=json.loads((p/'expected.json').read_text());assert m.digest_state()==expected['digest'] and [list(x)for x in trace]==expected['trace']
  else:unittest.main(argv=[sys.argv[0]],verbosity=2)
 else:
  suite=unittest.defaultTestLoader.loadTestsFromTestCase(ClockTests);r=unittest.TextTestRunner().run(suite);assert r.wasSuccessful()
  from verify_mlx_own_base_adapter import make_fixture
  with tempfile.TemporaryDirectory()as td:
   make_fixture(Path(td));child=subprocess.run([str(ROOT/'.venv-mlx-own-base/bin/python'),__file__,'--cpu',td],timeout=120);raise SystemExit(child.returncode)
