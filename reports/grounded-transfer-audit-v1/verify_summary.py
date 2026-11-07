"""Synthetic CPU controls only; never opens live audit artifacts."""
import copy,importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('summary',Path(__file__).with_name('summarize.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Controls(unittest.TestCase):
 def fixture(self):
  cases=[];events=[]
  for i,n in enumerate((1,3)):
   identity=dict(role='primary_tool',split='train',doc_id=str(i),turn=0,family='fixture',donor_doc_id=str(1-i),donor_turn=0);expected={'call':{'name':'calculate','arguments':{'op':'add','a':i,'b':1}}}
   cases.append(dict(**identity,swap_equal=False,correct={'groups':{'first_call':list(range(n))}},expected_first_frame=expected))
   events.append(dict(event='case_completed',identity=identity,swap_equal=False,ce={'correct':{'first_call':dict(targets=n,loss_sum=float(n))},'swapped':{'first_call':dict(targets=n,loss_sum=float(n*(i+2)))}},parsed=expected,protocol_failure=None,exact_teacher_frame_match=True,raw='fixture'))
  return dict(cases=cases),events,dict(state='completed_transfer_audit_not_acceptance',worker_terminal=dict(completed_rows=2,planned_histories=48))
 def test_weighted_and_paired_math(self):
  r=m.summarize(*self.fixture());g=r['conditioning'][0];self.assertEqual(g['correct_tokenweighted_ce'],1);self.assertEqual(g['swapped_tokenweighted_ce'],2.75);self.assertEqual(g['paired_row_delta_mean'],1.5);self.assertEqual(r['first_frame'][0]['exact_teacher_frame_match'],2)
 def test_incomplete_duplicate_badcounts(self):
  for mode in range(4):
   a,b,c=self.fixture()
   if mode==0:b.pop()
   elif mode==1:b.append(copy.deepcopy(b[0]))
   elif mode==2:b[0]['ce']['swapped']['first_call']['targets']=99
   else:c['state']='incomplete'
   with self.assertRaises(ValueError):m.summarize(a,b,c)
 def test_wrongvalidframe_not_exact(self):
  a,b,c=self.fixture();b[0].update(parsed={'text':'wrong'},exact_teacher_frame_match=False);r=m.summarize(a,b,c);self.assertEqual(r['first_frame'][0]['protocol_valid'],2);self.assertEqual(r['first_frame'][0]['exact_teacher_frame_match'],1);self.assertEqual(r['first_frame'][0]['generated_text'],1)
if __name__=='__main__':unittest.main()
