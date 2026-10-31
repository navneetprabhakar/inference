import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sft_v3 import *
from prepare_sft_v3 import make_case,assigned
from evaluate_sft_v3 import evaluate_case,summarize
class V3Test(unittest.TestCase):
 def infer(self,outputs):
  it=iter(outputs)
  return lambda messages:{'output':next(it),'stop':'eos','repeated_4gram_fraction':0}
 def test_counterfactual_result_pairs(self):
  r=make_case('train','result',3,0);s=make_case('train','result',3,1)
  self.assertEqual(r['family'],s['family']);self.assertEqual(r['provided_call'],s['provided_call']);self.assertNotEqual(r['provided_result'],s['provided_result']);self.assertNotEqual(r['expected_answer'],s['expected_answer'])
 def test_numeric_sign_and_contradiction(self):
  r=make_case('test','single',0);call=r['calls'][0];wrong=json.loads(json.dumps(call));wrong['arguments']['a']=-wrong['arguments']['a']
  self.assertFalse(compare_call(r,wrong,call)['call_exact']);self.assertFalse(exact_answer('5. Not 5.','5.'))
  wrong['arguments']['a']=True;self.assertFalse(compare_call(r,wrong,call)['schema_valid'])
 def test_valid_wrong_chain_continues_without_gold_result(self):
  r=make_case('test','chain',1);wrong=json.loads(json.dumps(r['calls'][0]));wrong['arguments']['a']+=10
  rr=evaluate_case(r,self.infer([call_text(wrong),call_text(r['calls'][1]),r['expected_answer']]))
  self.assertEqual(len(rr['generations']),3);self.assertFalse(rr['success']);self.assertIsNone(rr['answer_after_exact_calls']);self.assertFalse(rr['steps'][1]['prefix_correct_before']);self.assertNotEqual(rr['steps'][0]['executed_result'],r['results'][0])
 def test_malformed_chain_has_unreached_step_denominator(self):
  r=make_case('test','chain',0);rr=evaluate_case(r,self.infer(['not json']));m=summarize([rr])['chain']
  self.assertEqual(m['expected_steps'],2);self.assertEqual(m['attempted_steps'],1);self.assertEqual(m['per_step']['2']['reached'],0)
 def test_unknown_tool_rejected_and_aliases_cover_all_tools(self):
  covered=set()
  for i in range(200):
   r=make_case('train','single',i)
   if r['aliases']:
    covered.add(canonical_call(r,r['calls'][0])['name']);self.assertEqual(run_fixture(r,r['calls'][0],0),r['results'][0])
  self.assertEqual(covered,set(SCHEMAS))
  r=make_case('test','single',0)
  with self.assertRaises(ValueError):valid_call(r,{'name':'unknown','arguments':{}})
 def test_missing_slot_requires_full_reference_not_keyword(self):
  r=make_case('test','clarify',0);rr=evaluate_case(r,self.infer(['number? tracking reference?']));self.assertFalse(rr['missing_slot_reference_match'])
  rr=evaluate_case(r,self.infer([r['accepted_answers'][-1]]));self.assertTrue(rr['missing_slot_reference_match'])
 def test_provided_error_call_is_context_not_target(self):
  from tokenizers import Tokenizer
  tok=Tokenizer.from_file(str(ROOT/'data/sft-v2/tokenizer.json'))
  for kind in ['error','result']:
   r=make_case('train',kind,4);ids,mask,n=encode_record(tok,r)
   target=tok.decode(ids[1:][mask.astype(bool)].tolist(),skip_special_tokens=False)
   self.assertNotIn(CALL,target);self.assertNotIn('yard',target);self.assertEqual(target,r['expected_answer']+EOS)
 def test_replay_supervises_all_next_tokens(self):
  t,m,n=encode_record(None,{'objective':'causal_lm','tokens':list(range(513))});self.assertEqual(n,513);self.assertEqual(int(m.sum()),512)
 def test_gold_all_kinds(self):
  for kind in ['single','chain','clarify','result','error','none']:
   for i in range(25):
    r=make_case('dev',kind,i);outputs=[call_text(c) for c in r['calls']]+[r['expected_answer']]
    self.assertTrue(evaluate_case(r,self.infer(outputs))['success'],(kind,i))
if __name__=='__main__':unittest.main()
