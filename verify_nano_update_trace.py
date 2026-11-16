"""CPU evidence for trace parity and real accumulation rollback; no CUDA claim."""
import copy,json,tempfile,unittest,subprocess,sys
from pathlib import Path
import torch
from cloud_training.nano_update_trace import UpdateTrace,fingerprint,compare_traces
from cloud_training.nano_checkpoint import capture_rng,restore_rng_state
from cloud_training.nano_sft import backward_weighted
from verify_nano_sft import TinyLM

class TraceTests(unittest.TestCase):
 def test_first_divergence_and_partial_receipts(self):
  with tempfile.TemporaryDirectory() as d:
   a=UpdateTrace(Path(d)/'a',limit=1,identity={});b=UpdateTrace(Path(d)/'b',limit=1,identity={})
   for t in (a,b):t.record('initial',0,model=torch.tensor([1.]));t.record('after_optimizer',0,model=torch.tensor([2.]))
   self.assertEqual(compare_traces(a.path,b.path)['status'],'pass')
   path=b.path/'0001-after_optimizer.json';r=json.loads(path.read_text());r['values']['model']=fingerprint(torch.tensor([3.]));path.write_text(json.dumps(r))
   result=compare_traces(a.path,b.path);self.assertEqual(result['different_components'],['model']);self.assertEqual(result['first_difference'],1)
   path.unlink()
   with self.assertRaisesRegex(ValueError,'Incomplete'):compare_traces(a.path,b.path)
 def test_actual_sft_loop_emits_optimizer_boundaries(self):
  out=subprocess.check_output([sys.executable,'-m','reports.english-first-v1.check_loop',json.dumps({'updates':1,'losses':[3.,2.9],'trace':True})],text=True)
  self.assertEqual(json.loads(out)['trace_events'],[['before_collect',0],['before_optimizer',0],['after_optimizer',0]])
 def test_content_and_layout_are_separate_and_values_not_emitted(self):
  x=torch.arange(12,dtype=torch.float32).reshape(3,4);y=x.t().contiguous().t()
  a,b=fingerprint({'x':x}),fingerprint({'x':y})
  self.assertEqual(a['content_sha256'],b['content_sha256']);self.assertNotEqual(a['tensor_layouts'],b['tensor_layouts'])
  y[0,0]=9;self.assertNotEqual(a['content_sha256'],fingerprint({'x':y})['content_sha256'])
  self.assertEqual(fingerprint({'b':1,'a':2}),fingerprint({'a':2,'b':1}))
 def test_tracing_does_not_change_update_or_rng_and_is_bounded(self):
  torch.manual_seed(19);a=TinyLM();b=copy.deepcopy(a);oa=torch.optim.AdamW(a.parameters());ob=torch.optim.AdamW(b.parameters());rng=capture_rng()
  batches=[([[1,2]],[[2,3]]),([[3,4]],[[4,-1]])]
  backward_weighted(a,batches,3,device='cpu');oa.step()
  with tempfile.TemporaryDirectory() as d:
   t=UpdateTrace(Path(d)/'trace',limit=1,identity={'test':True})
   restore_rng_state(rng)
   before=fingerprint(capture_rng())
   loss=backward_weighted(b,batches,3,device='cpu',observer=lambda i,x,y,p:t.microbatch(0,b,i,x,y,p));ob.step()
   self.assertEqual(fingerprint(a.state_dict()),fingerprint(b.state_dict()));self.assertEqual(fingerprint(oa.state_dict()),fingerprint(ob.state_dict()))
   self.assertEqual(before,fingerprint(capture_rng()));self.assertTrue(loss>0)
   self.assertEqual(len(list(t.path.glob('*.json'))),4)
   t.record('ignored',1,bad=object());self.assertEqual(len(list(t.path.glob('*.json'))),4)
   with self.assertRaises(FileExistsError):UpdateTrace(t.path,limit=1,identity={})
 def test_partial_gradients_are_captured_before_rollback(self):
  torch.manual_seed(7);m=TinyLM();o=torch.optim.AdamW(m.parameters());rng=capture_rng();model=fingerprint(m.state_dict());optim=fingerprint(o.state_dict())
  calls=[]
  with tempfile.TemporaryDirectory() as d:
   trace=UpdateTrace(Path(d)/'trace',limit=2,identity={'fixture':1})
   def stop():calls.append(1);return len(calls)==2
   with self.assertRaises(InterruptedError):backward_weighted(m,[([[1]],[[2]]),([[2]],[[3]])],2,device='cpu',stop_check=stop,observer=lambda i,x,y,p:trace.microbatch(0,m,i,x,y,p))
   self.assertTrue(any(p.grad is not None for p in m.parameters()))
   rows=[json.loads(p.read_text()) for p in sorted(trace.path.glob('*.json'))];self.assertEqual([r['event'] for r in rows],['microbatch_before','microbatch_after'])
   self.assertIn('gradients',rows[-1]['values'])
   m.zero_grad(set_to_none=True);restore_rng_state(rng)
   self.assertEqual(model,fingerprint(m.state_dict()));self.assertEqual(optim,fingerprint(o.state_dict()))
 def test_write_failure_and_invalid_limits_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):UpdateTrace(Path(d)/'bad',limit=3,identity={})
   trace=UpdateTrace(Path(d)/'trace',limit=1,identity={});trace.path.rmdir()
   with self.assertRaises(OSError):trace.record('boundary',0,value=1)
if __name__=='__main__':unittest.main()
