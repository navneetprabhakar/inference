import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from train_approved_next_three_sft import reason
from evaluate_approved_next_three_sft import main as evaluate

class StageTwoBoundsTest(unittest.TestCase):
 def test_resource_guards(self):
  base={'swap_used_mb':100};h={'thermal_state':3,'free_disk_bytes':99*2**30,'mlx_peak_bytes':0,'mlx_allocator_bytes':0,'swap_used_mb':100};self.assertEqual(reason(h,base),'critical_thermal')
  h['thermal_state']=0;h['free_disk_bytes']=14*2**30;self.assertEqual(reason(h,base),'disk_reserve')
  h['free_disk_bytes']=99*2**30;h['swap_used_mb']=1125;self.assertEqual(reason(h,base),'swap_growth')
 def test_config_envelope(self):
  c=json.loads((Path(__file__).resolve().parents[1]/'configs/approved_next_three_sft_v1.json').read_text())
  self.assertEqual(c['max_nonpadding_input_tokens'],1000000);self.assertEqual(c['max_novel_candidate_passes'],2);self.assertEqual(c['max_active_seconds'],14400);self.assertEqual(c['learning_rate'],1e-5)
 def test_frozen_mixture_has_no_selection_records_and_two_candidate_passes(self):
  root=Path(__file__).resolve().parents[1];m=json.loads((root/'data/approved-next-three-sft-v1/manifest.json').read_text());order=json.loads((root/'data/approved-next-three-sft-v1/order.json').read_text())
  self.assertEqual(m['candidate_exposures'],4690);self.assertIn('confirmation-cases.jsonl',m['selection_data_excluded'][1])
  seen={}
  for r in order:
   if r['source']=='candidate':seen[r['id']]=seen.get(r['id'],0)+1
  self.assertEqual(len(seen),2345);self.assertTrue(all(v==2 for v in seen.values()))
 def test_confirmation_fails_closed_without_selection(self):
  class A: pass
  a=A();a.split='confirmation';a.selection='this-does-not-exist';a.output=tempfile.mkdtemp();a.baseline='x';a.experiment='y'
  with self.assertRaisesRegex(RuntimeError,'confirmation prohibited'):evaluate(a)
if __name__=='__main__':unittest.main()
