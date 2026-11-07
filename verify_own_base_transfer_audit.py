"""CPU-only audit controls. No corpus/candidate/private inputs or MPS."""
import copy,unittest
import torch
import own_base_transfer_audit as a
from tokenizer import load,EOT
from own_base_chat import policy_text
from own_base_sft_rows import last_turn_row
from dialogue import assistant_prompt

class AuditTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.tok=load()
 def history(self):return [dict(role='system',text=policy_text()),dict(role='user',text='Keep red.'),dict(role='assistant',text='red'),dict(role='user',text='Now keep blue.'),dict(role='assistant',text='blue')]
 def test_reconstruction_and_nonmutation(self):
  h=self.history();r=last_turn_row(self.tok,h);self.assertEqual(a.decode_history(self.tok,r.inputs,r.labels),h);before=copy.deepcopy(h);c=a.encode_case(self.tok,h,'Keep green instead.')
  self.assertEqual(h,before);self.assertEqual(c['prefix'],assistant_prompt(self.tok,h[:-1],reply_budget=256));self.assertEqual(c['correct']['labels'],r.labels)
  self.assertEqual([y for y in c['correct']['labels']if y!=-100],[y for y in c['swapped']['labels']if y!=-100]);self.assertNotEqual(c['correct']['inputs'],c['swapped']['inputs'])
 def test_first_call_not_teacher_call_contents(self):
  call=dict(name='calculate',arguments=dict(op='add',a=2,b=3));record=dict(call_id='c1',name='calculate',arguments=call['arguments'],ok=True,data={'result':5},source='offline fixture',schema_version=1)
  h=[dict(role='system',text=policy_text()),dict(role='user',text='Add2and3.'),dict(role='assistant',call=call,call_id='c1'),dict(role='tool',record=record),dict(role='assistant',text='5')]
  r=last_turn_row(self.tok,h);self.assertEqual(a.decode_history(self.tok,r.inputs,r.labels),h);c=a.encode_case(self.tok,h,'Multiply4and5.')
  self.assertEqual(c['prefix'],assistant_prompt(self.tok,h[:2],reply_budget=256));self.assertEqual(set(c['correct']['groups']),{'first_call','teacher_observed_readback'});self.assertEqual(c['expected_first_frame'],{'call':call})
 def test_ce_category_math(self):
  class Uniform(torch.nn.Module):
   def forward(self,x,prediction_mask):return torch.zeros(int(prediction_mask.sum()),7)
  row=dict(inputs=[1,2,3,4],labels=[-100,2,3,4],groups={'first_call':[1],'teacher_observed_readback':[2,3]});result=a.ce(Uniform(),row,'cpu');self.assertAlmostEqual(result['first_call']['loss_sum'],float(torch.log(torch.tensor(7.))),places=6);self.assertAlmostEqual(result['teacher_observed_readback']['loss_sum'],2*result['first_call']['loss_sum'],places=6)
 def test_selection_order_and_whole_doc(self):
  rows=[dict(doc_id=str(i))for i in range(20)];self.assertEqual(a.select_ids(rows,'chat','train'),a.select_ids(rows[::-1]+rows,'chat','train'));self.assertEqual(len(set(a.select_ids(rows,'chat','train'))),8)
  with self.assertRaises(ValueError):a.select_ids(rows[:7],'chat','train')
 def test_refusals(self):
  h=self.history();r=last_turn_row(self.tok,h)
  with self.assertRaises(ValueError):a.decode_history(self.tok,r.inputs,r.labels[:-1]+[1])
  changed=list(r.labels);changed[-2]=-100
  with self.assertRaises(ValueError):a.decode_history(self.tok,r.inputs,changed)
  with self.assertRaises(ValueError):a.encode_case(self.tok,h,'unfit '*2000)
 def test_equal_swap_explicit(self):
  h=self.history();self.assertTrue(a.encode_case(self.tok,h,h[-2]['text'])['swap_equal'])

if __name__=='__main__':torch.set_num_threads(1);unittest.main()
