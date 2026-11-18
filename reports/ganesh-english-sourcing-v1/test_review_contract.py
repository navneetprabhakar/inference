"""Negative tests for evidence drift; no test claims to replace semantic review."""
import copy,importlib.util,json,unittest
from pathlib import Path
from candidate_review_contract import validate_review
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fixture',R/'authored_source_b03.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ROW=next(x for x in m.ROWS if x['group']=='archive_box_location')
REVIEW=next(x for x in json.loads((R/'authored-review-b03.json').read_text()) if x['group']==ROW['group'])
class ReviewContractTests(unittest.TestCase):
 def setUp(self):self.row=copy.deepcopy(ROW);self.review=copy.deepcopy(REVIEW)
 def reject(self):
  with self.assertRaises(ValueError):validate_review(self.row,self.review)
 def test_bound_review(self):self.assertEqual(len(validate_review(self.row,self.review)),len(self.row['turns'])*2)
 def test_changed_answer(self):
  turns=list(self.row['turns']);turns[-1]=(turns[-1][0],'The green box is on the bottom shelf.');self.row['turns']=turns;self.reject()
 def test_wrong_group(self):self.review['group']='different_scenario';self.reject()
 def test_incomplete_review(self):self.review['assistant_turns_reviewed']-=1;self.reject()
 def test_missing_turn(self):self.review['reviewed_turn_numbers'].pop();self.reject()
 def test_unreviewed_admission(self):self.review['training_admitted']=True;self.reject()
 def test_false_independent_claim(self):self.review['independent_review']=True;self.reject()
 def test_inflated_delay(self):self.review['recall_probe']['intervening_complete_turns']+=2;self.reject()
 def test_future_support(self):self.review['recall_probe']['last_supporting_turn']=99;self.reject()
 def test_wrong_probe_target(self):self.review['recall_probe']['expected_assistant_exact']='Made up answer';self.reject()
 def test_unshortlisted(self):self.review['decision']='pending';self.reject()
if __name__=='__main__':unittest.main()
