"""Mutation checks for review/content binding, using a disposable copy of one row."""
import copy,hashlib,importlib.util,json,pathlib,tempfile,unittest
P=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('selection_verifier',P/'verify_selection.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class SelectionContract(unittest.TestCase):
 def setUp(self):
  self.row=json.loads((P/'root/accepted.jsonl').read_text().splitlines()[0])
  self.tmp=tempfile.TemporaryDirectory(dir=v.ROOT/'runs');self.addCleanup(self.tmp.cleanup)
 def altered_review(self,mutate):
  r=copy.deepcopy(self.row);ref=r['review_receipts'][0];d=json.loads((v.ROOT/ref['path']).read_text());entry=next(x for x in d['reviews'] if x['group']==r['group']);mutate(entry)
  p=pathlib.Path(self.tmp.name)/'review.json';p.write_text(json.dumps(d));r['review_receipts']=[{'path':str(p.relative_to(v.ROOT)),'sha256':v.sha(p)}];return r
 def test_unchanged(self):v.verify_new(self.row)
 def test_text_changed_after_review(self):
  r=copy.deepcopy(self.row);r['messages'][-1]['content']+=' Unsupported addition.'
  with self.assertRaises(AssertionError):v.verify_new(r)
 def test_missing_last_reviewed_turn(self):
  r=self.altered_review(lambda e:e['turn_reviews'].pop())
  with self.assertRaises(AssertionError):v.verify_new(r)
 def test_failed_target_despite_accept_overall(self):
  r=self.altered_review(lambda e:e['turn_reviews'][0].update(decision='fail'))
  with self.assertRaises(AssertionError):v.verify_new(r)
 def test_wrong_content_binding(self):
  r=self.altered_review(lambda e:e.update(content_sha256='0'*64))
  with self.assertRaises(AssertionError):v.verify_new(r)
 def test_model_substitution(self):
  r=copy.deepcopy(self.row);r['generation']['requested_model']='different-model'
  with self.assertRaises(AssertionError):v.verify_new(r)
if __name__=='__main__':unittest.main()
