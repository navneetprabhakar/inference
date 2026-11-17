import json,tempfile,unittest
from pathlib import Path
from cloud_training.nano_fit_probe import sha,validate_inputs
class BoundProbe(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  (self.root/'manifest.json').write_text('{}');self.p=self.root/'suite.json'
  self.s={'purpose':'training_fit_exposed_never_release','sessions':[{'id':'a','turns':[{'user':'Hello'}]}]};self.p.write_text(json.dumps(self.s))
 def check(self,scope='exposed_fit'):
  return validate_inputs(self.root,sha(self.root/'manifest.json'),self.p,sha(self.p),scope)
 def test_valid(self):self.assertEqual(len(self.check()['sessions']),1)
 def test_fit_not_development(self):
  with self.assertRaises(ValueError):self.check('development')
 def test_release_forbidden(self):
  with self.assertRaises(ValueError):self.check('release')
 def test_hash_mismatch(self):
  with self.assertRaises(ValueError):validate_inputs(self.root,'f'*64,self.p,sha(self.p),'exposed_fit')
  with self.assertRaises(ValueError):validate_inputs(self.root,sha(self.root/'manifest.json'),self.p,'f'*64,'exposed_fit')
 def test_release_cannot_be_relabeled(self):
  self.s['purpose']='heldout_release_never_train';self.p.write_text(json.dumps(self.s))
  with self.assertRaises(ValueError):self.check('development')
 def test_budget_expansion_rejected(self):
  self.s['sessions'][0]['turns'][0]['reply_budget']=2048;self.p.write_text(json.dumps(self.s))
  with self.assertRaises(ValueError):self.check()
 def test_actual_frozen_development_budget(self):
  p=Path('reports/english-first-v1/development-suite.json')
  validate_inputs(self.root,sha(self.root/'manifest.json'),p,sha(p),'development')
 def test_empty_and_duplicate(self):
  for sessions in ([],[{'id':'a','turns':[]}],[{'id':'a','turns':[{'user':'Hello'}]},{'id':'a','turns':[{'user':'Hello'}]}]):
   self.s['sessions']=sessions;self.p.write_text(json.dumps(self.s))
   with self.assertRaises(ValueError):self.check()
if __name__=='__main__':unittest.main()
