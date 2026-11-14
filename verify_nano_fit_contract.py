import copy,json,unittest,hashlib
from pathlib import Path
from cloud_training.nano_fit_contract import errors,validate_review_file
from cloud_training.nano_quality_gate import release_decision
from cloud_training.nano_sft import FiniteEpochDataset
from verify_nano_sft import FakeDataset
P=Path('reports/english-first-v1')
class FitTests(unittest.TestCase):
 def inputs(self):
  m=json.loads((P/'diagnostic-manifest.json').read_text());m['_sha256']=hashlib.sha256((P/'diagnostic-manifest.json').read_bytes()).hexdigest()
  return dict(contract=json.loads((P/'diagnostic-contract.json').read_text()),manifest=m,admission=json.loads((P/'diagnostic-admission.json').read_text()),train={'sessions':24,'assistant_targets':656,'turn_modes':{'enabled_no_call':24,'disabled_no_call':48}},dev={'sessions':12,'assistant_targets':556,'turn_modes':{'enabled_no_call':18,'disabled_no_call':18}},epochs=64,lr_multiplier=.25,eval_interval=5,max_updates=64)
 def test_review_binds_actual_rows(self):
  a=self.inputs();validate_review_file(P/'diagnostic-manifest.json',a['admission'],a['contract'])
  a['contract']['review_sha256']='f'*64
  with self.assertRaises(ValueError):validate_review_file(P/'diagnostic-manifest.json',a['admission'],a['contract'])
 def test_exact_diagnostic_contract(self):self.assertEqual(errors(**self.inputs()),[])
 def test_rejects_scope_data_and_recipe_drift(self):
  for key,val in [('epochs',65),('max_updates',None),('lr_multiplier',.5),('eval_interval',10)]:
   a=self.inputs();a[key]=val;self.assertTrue(errors(**a))
  for field,value in [('diagnostic_only',False),('review_sha256','b'*64),('objective','conversation_and_tools')]:
   a=self.inputs();a['contract'][field]=value;self.assertTrue(errors(**a))
  a=self.inputs();a['train']['turn_modes']['enabled_call']=1;self.assertTrue(errors(**a))
 def test_default_epoch_bound_is_unchanged(self):
  d=FakeDataset([4,5]);d.target_counts=[3,4]
  with self.assertRaises(ValueError):FiniteEpochDataset(d,9)
  self.assertEqual(len(FiniteEpochDataset(d,64,diagnostic_only=True)),128)
  with self.assertRaises(ValueError):FiniteEpochDataset(d,65,diagnostic_only=True)
 def test_never_release_even_if_other_evidence_present(self):
  for contract,identity in [({'diagnostic_only':True},{}),({}, {'diagnostic_only':True})]:
   r=release_decision(raw={},raw_sha256='a'*64,suite={},suite_sha256='b'*64,review={},contract=contract,checkpoint_identity=identity)
   self.assertFalse(r['quality_accepted']);self.assertIn('Diagnostic fit checkpoints cannot authorize release',r['reasons'])
if __name__=='__main__':unittest.main()
