"""CPU-only small ledger/guard/comparison tests; no model or GPU."""
import json,tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch
import numpy as np
import mlx_sequential_fit as f

class Checks(unittest.TestCase):
 def budget(self,root):
  root=Path(root);f.rt.atomic(root/'launch.json',dict(baseline_swap_bytes=0));f.rt.atomic(root/'ledger.json',dict(reserved_targets=0,committed_targets=0,pending=None));return f.Budget({'stop_paths':[]},root,f.rt.make_ticket(600),probe=False)
 def test_two_updates_exact_nonrefundable_reservations(self):
  with tempfile.TemporaryDirectory()as td:
   b=self.budget(td);b.reserve()
   with self.assertRaises(f.rt.RunnerStop):b.reserve()
   self.assertEqual(f.read(Path(td)/'ledger.json')['reserved_targets'],8192);b.commit({'loss':1});b.reserve();b.commit({'loss':2})
   with self.assertRaises(f.rt.RunnerStop):b.reserve()
   self.assertEqual(f.read(Path(td)/'ledger.json'),dict(reserved_targets=16384,committed_targets=16384,pending=None))
 def test_stop_deadline_and_output_headroom(self):
  with tempfile.TemporaryDirectory()as td:
   b=self.budget(td);b.ticket['deadline']=time.time()-1
   with self.assertRaises(f.rt.RunnerStop):b.check()
   b.ticket=f.rt.make_ticket(600);stop=Path(td)/'STOP';stop.touch();b.spec['stop_paths']=[str(stop)]
   with self.assertRaises(f.rt.RunnerStop):b.check()
   stop.unlink()
   with patch.object(f,'output_bytes',return_value=64*1024**2-1024**2):
    with self.assertRaises(f.rt.RunnerStop):b.check()
 def test_unreviewed_spec_refuses_before_input_reads(self):
  with self.assertRaisesRegex(f.rt.RunnerStop,'reviewed'):f.validate({'state':'pending_root_review'})
 def test_comparison_streams_all_weights_moments_and_delta(self):
  with tempfile.TemporaryDirectory()as td:
   b=self.budget(td);p=np.array([[1.,2.],[3.,4.]],np.float32);m=np.ones_like(p)*.01;v=np.ones_like(p)*.001
   class Opt:state={'x':{'m':m,'v':v}}
   class Core:params={'x':p};optimizers=[Opt(),Opt()]
   path=Path(td)/'reference.npz';np.savez(path,**{'weight::x':p,'m::x':m,'v::x':v});source={'weight::x':p-.1};result=f.compare_state(Core(),source,path,b);self.assertEqual(result['weight']['max_abs'],0);self.assertEqual(result['weight']['update_delta_relative_l2'],0)
   bad=v.copy();bad[0,0]+=.01;np.savez(path,**{'weight::x':p,'m::x':m,'v::x':bad})
   with self.assertRaises(f.rt.RunnerStop):f.compare_state(Core(),source,path,b)
 def test_supervisor_reuse_enforces_owned_ticket(self):
  with self.assertRaises(f.rt.RunnerStop):f.rt.consume_ticket(0)

if __name__=='__main__':unittest.main()
