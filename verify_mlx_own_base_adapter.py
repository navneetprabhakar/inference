"""Tiny CPU-only adapter controls; no full checkpoint, GPU or production conversion."""
import copy,json,tempfile,unittest
from dataclasses import asdict
from pathlib import Path
import numpy as np
import subprocess,sys,os
import mlx_own_base_adapter as bridge

def make_fixture(path):
 import torch
 from gpt2 import Config,GPT2,next_token_loss
 from train import optimizer_for
 import own_base_neutral_state as neutral
 torch.set_num_threads(1)
 torch.manual_seed(982);cfg=Config(vocabulary=19,context=16,width=12,heads=3,depth=1);model=GPT2(cfg).cpu();opt=optimizer_for(model)
 for g in opt.param_groups:g['params'].reverse();g['lr']=.000123456789
 batch=torch.arange(39).reshape(3,13)%19
 for _ in range(3):
  opt.zero_grad();next_token_loss(model,batch).backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step()
 identity=dict(model=asdict(cfg),tokenizer={'synthetic':'a'*64},scheduler={'name':'synthetic'},initialization='random',seed=982,corpus={'synthetic':True},protocol={'target_tokens':36000})
 source=dict(path='synthetic-only.pt',sha256='b'*64,bytes=1)
 progress=dict(campaign_step=1,optimizer_step=3,initial_optimizer_step=2,trained_tokens=36,reserved_tokens=72,targets_per_update=36,initial_source_offset=100,source_offset=136)
 pinned=dict(expected_identity=identity,expected_source=source,expected_progress=progress,expected_optimizer=neutral.optimizer_policy(opt))
 meta,arrays=neutral.export_objects(model,opt,identity=identity,source=source,progress=progress,cpu_rng=torch.get_rng_state(),mps_rng=torch.arange(8,dtype=torch.uint8),**pinned)
 np.savez(path/'fixture.npz',**arrays,batch=batch.numpy().copy());(path/'fixture.json').write_text(json.dumps(dict(meta=meta,pinned=pinned,identity={'fixture':'cpu-only','seed':982})))

class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  path=Path(sys.argv[2]);record=json.loads((path/'fixture.json').read_text());cls.meta=record['meta'];cls.pinned=record['pinned'];cls.identity=record['identity']
  with np.load(path/'fixture.npz',allow_pickle=False) as f:cls.arrays={n:f[n] for n in f.files if n!='batch'};cls.batch=f['batch']
 def core(self,native=None):return bridge.DisposableCore(self.meta,self.arrays,pinned=self.pinned,benchmark_identity=self.identity,device=mx.cpu,native=native)
 def test_exact_initial_arrays_and_distinct_progress(self):
  core=self.core();meta,arrays=core.snapshot()
  for key,value in self.arrays.items():
   if key.startswith('step::'):continue
   np.testing.assert_array_equal(arrays[key],value)
  self.assertEqual(meta['benchmark_progress'],dict(committed_updates=0,committed_targets=0,source_offset=136,optimizer_step=3))
  self.assertEqual(meta['source_provenance']['source_neutral']['progress']['campaign_step'],1)
  self.assertEqual(meta['source_provenance']['source_neutral']['optimizer'][0]['learning_rate'],.000123456789)
 def test_native_roundtrip_and_exact_continuation(self):
  left=self.core();batch=mx.array(self.batch);left.step([batch[:1],batch[1:]],learning_rate=6e-5);meta,arrays=left.snapshot()
  with tempfile.TemporaryDirectory() as d:
   bridge.publish(d,meta,arrays,benchmark_identity=self.identity,source_provenance=left.provenance)
   loaded=bridge.read_native(d,benchmark_identity=self.identity,source_provenance=left.provenance);right=self.core(loaded)
   self.assertEqual(left.step([batch[:1],batch[1:]],learning_rate=3e-5),right.step([batch[:1],batch[1:]],learning_rate=3e-5))
   lm,la=left.snapshot();rm,ra=right.snapshot();self.assertEqual(lm,rm)
   for k in la:np.testing.assert_array_equal(la[k],ra[k])
   bridge.publish(d,lm,la,benchmark_identity=self.identity,source_provenance=left.provenance)
   self.assertEqual(len(list(Path(d).glob('*.npz'))),1)
 def test_restore_preserves_compiled_callable_and_source_state(self):
  core=self.core();batch=mx.array(self.batch);initial=core.snapshot();core.step([batch[:1],batch[1:]],learning_rate=6e-5)
  traces=core.core.trace_count;callable_identity=id(core.core._execute)
  core.restore_source_in_place(self.arrays,pinned=self.pinned);restored=core.snapshot();self.assertEqual(restored[0],initial[0])
  for k in initial[1]:np.testing.assert_array_equal(restored[1][k],initial[1][k])
  core.step([batch[:1],batch[1:]],learning_rate=6e-5);self.assertEqual(core.core.trace_count,traces);self.assertEqual(id(core.core._execute),callable_identity)
 def test_resume_without_original_weight_file(self):
  core=self.core();batch=mx.array(self.batch);core.step([batch[:1],batch[1:]],learning_rate=6e-5);meta,arrays=core.snapshot()
  other=bridge.DisposableCore.from_native(meta,arrays,benchmark_identity=self.identity,source_provenance=core.provenance,device=mx.cpu)
  self.assertEqual(core.step([batch[:1],batch[1:]],learning_rate=6e-5),other.step([batch[:1],batch[1:]],learning_rate=6e-5))
 def test_refuse_wrong_source_and_native_counter(self):
  wrong=copy.deepcopy(self.pinned);wrong['expected_source']['sha256']='c'*64
  with self.assertRaises(ValueError):bridge.convert_neutral(self.meta,self.arrays,pinned=wrong)
  core=self.core();meta,arrays=core.snapshot();meta['benchmark_progress']['source_offset']+=1
  with self.assertRaises(ValueError):bridge.validate_native(meta,arrays,benchmark_identity=self.identity,source_provenance=core.provenance)
 def test_corruption_and_wrong_identity_refusal(self):
  core=self.core();meta,arrays=core.snapshot()
  for mode in ['truncated','receipt','identity']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
    receipt=bridge.publish(d,meta,arrays,benchmark_identity=self.identity,source_provenance=core.provenance)
    if mode=='truncated':(Path(d)/receipt['file']).write_bytes(b'truncated')
    if mode=='receipt':
     p=Path(d)/'accepted.json';v=json.loads(p.read_text());v['bytes']+=1;p.write_text(json.dumps(v))
    with self.assertRaises(ValueError):bridge.read_native(d,benchmark_identity={'wrong':True} if mode=='identity' else self.identity,source_provenance=core.provenance)
 def test_failed_replacement_preserves_accepted_state(self):
  core=self.core();meta,arrays=core.snapshot()
  with tempfile.TemporaryDirectory() as d:
   bridge.publish(d,meta,arrays,benchmark_identity=self.identity,source_provenance=core.provenance);accepted=(Path(d)/'accepted.json').read_bytes();count=0
   def fail():
    nonlocal count
    count+=1
    if count==2:raise RuntimeError('synthetic precommit failure')
   with self.assertRaises(RuntimeError):bridge.publish(d,meta,arrays,benchmark_identity=self.identity,source_provenance=core.provenance,check=fail)
   self.assertEqual((Path(d)/'accepted.json').read_bytes(),accepted)
   bridge.read_native(d,benchmark_identity=self.identity,source_provenance=core.provenance)
 def test_wrong_effective_batch_rejected_before_update(self):
  core=self.core()
  with self.assertRaises(ValueError):core.step([mx.array(self.batch[:1])],learning_rate=6e-5)
  self.assertEqual(core.progress['committed_updates'],0)
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='--worker':
  import mlx.core as mx
  mx.set_default_device(mx.cpu)
  unittest.main(argv=[sys.argv[0]],verbosity=2)
 else:
  with tempfile.TemporaryDirectory() as d:
   make_fixture(Path(d))
   env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',MLX_ENABLE_TF32='0')
   child=subprocess.run([str(Path(__file__).parent/'.venv-mlx-own-base/bin/python'),__file__,'--worker',d],env=env,timeout=120)
   raise SystemExit(child.returncode)
