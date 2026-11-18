import copy, json, unittest
from pathlib import Path
import verify_extension as gate
class Gates(unittest.TestCase):
 def setUp(self):
  self.row=json.loads((gate.P/'maths/selected.jsonl').read_text().splitlines()[0]);path=gate.P/'root-read-review.json'
  self.row['root_review_receipt']={'path':str(path.relative_to(gate.ROOT)),'sha256':gate.v.sha(path)}
 def test_valid_math_and_root(self):
  gate.verify_math(self.row);gate.verify_root_review(self.row)
 def test_changed_answer_fails_math(self):
  self.row['messages'][1]['content']='The answer is 999.'
  with self.assertRaises(AssertionError):gate.verify_math(self.row)
 def test_changed_answer_fails_root(self):
  self.row['messages'][1]['content']='The answer is 999.'
  with self.assertRaises(AssertionError):gate.verify_root_review(self.row)
 def test_missing_math_receipt_fails(self):
  del self.row['arithmetic_audit_receipt']
  with self.assertRaises(KeyError):gate.verify_math(self.row)
 def test_stale_math_receipt_fails(self):
  self.row['arithmetic_audit_receipt']['sha256']='0'*64
  with self.assertRaises(AssertionError):gate.verify_math(self.row)
 def test_wrong_arithmetic_result_fails(self):
  from supplemental_arithmetic import replay
  with self.assertRaises(AssertionError):replay('sub',['18','12'],'7')
 def test_supplemental_changed_reply_fails(self):
  rows=gate.read(gate.ROOT/'runs/ganesh-foundations-extension-v1/reviewed-v1.jsonl');row=next(r for r in rows if r['group']=='orch_019')
  gate.verify_supplemental(row)
  row['messages'][1]['content']='Seven people did not finish.'
  with self.assertRaises(AssertionError):gate.verify_supplemental(row)
 def test_root_hold_fails(self):
  rows=[json.loads(l) for l in (gate.P/'orchestration/accepted.jsonl').read_text().splitlines()]
  row=next(r for r in rows if r['group']=='orch_013');row['root_review_receipt']=self.row['root_review_receipt']
  with self.assertRaises(AssertionError):gate.verify_root_review(row)
if __name__=='__main__':unittest.main()
