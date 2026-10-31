import sys,unittest,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
import mlx.core as mx
import mlx.nn as nn
from tokenizers import Tokenizer
from sft_common import *
from train_sft import batch,batch_slots,lr_at,resource_limit
from benchmark_mlx import Model
from evaluate_sft import faithful,strict_answer,evaluate_record
from unittest.mock import patch
from prepare_sft import tool_record
class SFTTest(unittest.TestCase):
 def test_assistant_mask_and_roundtrip(self):
  tok=Tokenizer.from_file(str(ROOT/'data/pilot-v1/tokenizer.json'))
  episode=[{'role':'system','content':'Be concise.'},{'role':'user','content':'Add 2 and 3.'},{'role':'assistant','content':call_text({'name':'calculate','arguments':{'op':'add','a':2,'b':3}})},{'role':'tool','content':'{"result":5}'},{'role':'assistant','content':'The result is 5.'}]
  ids,mask,n=encode_episode(tok,episode);self.assertEqual(ids[:n].tolist(),tok.encode(render(episode)).ids)
  target=tok.decode(ids[1:][mask.astype(bool)].tolist(),skip_special_tokens=False)
  self.assertIn(CALL,target);self.assertEqual(target.count(EOS),2);self.assertNotIn('Be concise',target);self.assertNotIn('"result":5',target)
  self.assertFalse(mask[n-1:].any())
 def test_masked_targets_do_not_change_loss(self):
  m=Model(64,2,128);t=mx.random.randint(0,128,(2,513));mask=mx.zeros((2,512));mask=mask.at[:,0:3].add(1)
  changed=mx.concatenate([t[:,:4],mx.random.randint(0,128,(2,509))],axis=1)
  self.assertTrue(bool(mx.allclose(masked_loss(m,t,mask),masked_loss(m,changed,mask))))
 def test_fixtures_and_invalid_arguments(self):
  self.assertEqual(execute({'name':'calculate','arguments':{'op':'add','a':2,'b':3}}),{'result':5})
  self.assertEqual(execute({'name':'convert','arguments':{'value':2,'from_unit':'km','to_unit':'m'}})['result'],2000)
  with self.assertRaises(ValueError):execute({'name':'calculate','arguments':{'op':'add','a':True,'b':3}})
  with self.assertRaises(ValueError):execute({'name':'get_weather','arguments':{'city':'Pune','extra':1}})
 def test_partial_input_budget(self):
  a={'train_ids':np.ones((2,513),np.int32),'train_mask':np.ones((2,512),np.float32),'train_length':np.array([100,200])}
  t,m,n,p=batch(a,np.array([0,1]),0,250);self.assertEqual(t.shape,(2,200));self.assertEqual(n,250);self.assertEqual(p,99+51);self.assertEqual(float(m.sum()),250)
 def test_lr_endpoints(self):
  self.assertAlmostEqual(lr_at(250000,3e-5),3e-5);self.assertAlmostEqual(lr_at(5000000,3e-5),1e-6)
 def test_result_scoring_handles_sentence_punctuation(self):
  c={'name':'calculate','arguments':{'op':'add','a':2,'b':3}};r=execute(c)
  self.assertTrue(faithful(c,r,result_answer(c,r)));self.assertFalse(faithful(c,r,'The result is 15.'))
 def test_strict_rejects_contradictions_and_wrong_numeric_sign(self):
  c={'name':'calculate','arguments':{'op':'add','a':2,'b':3}};r=execute(c)
  for text in ['The result is 5. Actually it is 7.','The result is -5.','The result is 5.5.','Not 5.']:
   self.assertFalse(faithful(c,r,text))
  self.assertFalse(strict_answer('-5','5'));self.assertFalse(strict_answer('1.5','15'))
 def test_no_tool_gibberish_not_success(self):
  rec={'id':'x','kind':'none','messages':[],'expected_answer':'Hello.'}
  with patch('evaluate_sft.generate',return_value={'output':'asdf blarg'}):
   row=evaluate_record(None,None,rec,{})
  self.assertIsNone(row['success']);self.assertTrue(row['human_review_required'])
 def test_independent_tool_arguments_and_chain_routes(self):
  cities={};topics={}
  for split in ['train','dev','test']:
   records=[tool_record(split,i) for i in range(500)]
   cities[split]={r['calls'][0]['arguments']['city'] for r in records if r['calls'][0]['name']=='get_weather'}
   topics[split]={r['calls'][0]['arguments']['query'] for r in records if r['calls'][0]['name']=='search_notes'}
   self.assertGreaterEqual(len(cities[split]),6);self.assertGreaterEqual(len(topics[split]),6)
   chains=[tool_record(split,i,'chain') for i in range(100)]
   self.assertEqual(len({tuple(c['name'] for c in r['calls']) for r in chains}),3)
  for x,y in [('train','dev'),('train','test'),('dev','test')]:
   self.assertFalse(cities[x]&cities[y]);self.assertFalse(topics[x]&topics[y])
 def test_trimmed_loss_matches_padded_loss(self):
  model=Model(64,2,128);t=mx.random.randint(0,128,(2,513));mask=mx.zeros((2,512));mask=mask.at[:,:30].add(1)
  self.assertTrue(bool(mx.allclose(masked_loss(model,t,mask),masked_loss(model,t[:,:31],mask[:,:30]),atol=1e-5)))
 def test_resume_resource_guard_uses_session_growth(self):
  h={'free_disk_bytes':80*2**30,'mlx_peak_bytes':3*2**30,'swap_used_mb':1600}
  self.assertFalse(resource_limit(h,{'swap_used_mb':1600}))
  self.assertTrue(resource_limit(dict(h,mlx_allocator_bytes=13*2**30),{'swap_used_mb':1600}))
  self.assertTrue(resource_limit(dict(h,swap_used_mb=2625),{'swap_used_mb':1600}))
  self.assertTrue(resource_limit(dict(h,free_disk_bytes=10*2**30),h))
if __name__=='__main__':unittest.main()
