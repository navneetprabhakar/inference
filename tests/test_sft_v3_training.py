import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
import mlx.core as mx
import mlx.nn as nn
from benchmark_mlx import Model
from train_sft_v3 import weighted_loss,batch,lr_at
class WeightedTrainingTest(unittest.TestCase):
 def test_fractional_mass_gradient_accumulation(self):
  model=Model(64,2,128);tokens=mx.random.randint(0,128,(2,33));mask=mx.zeros((2,32));mask=mask.at[0,0].add(.4);mask=mask.at[1,1:3].add(2.9)
  fn=nn.value_and_grad(model,weighted_loss);loss,g=fn(model,tokens,mask);l1,g1=fn(model,tokens[:1],mask[:1]);l2,g2=fn(model,tokens[1:],mask[1:]);mx.eval(loss,l1,l2)
  self.assertAlmostEqual(float(loss),float((l1*.4+l2*5.8)/6.2),places=5)
  from mlx.utils import tree_flatten
  for (_,v),(_,a),(_,b) in zip(tree_flatten(g),tree_flatten(g1),tree_flatten(g2)):
   self.assertTrue(bool(mx.allclose(v,(a*.4+b*5.8)/6.2,atol=1e-5)))
 def test_masked_roles_and_partial_budget_survive_weighting(self):
  arrays={'train_ids':np.ones((2,6),np.int32),'train_mask':np.array([[0,1,0,1,0],[0,0,1,1,1]],np.float32),'train_source':np.array([1,3]),'train_length':np.array([6,6])}
  t,m,mass,nonpad,c=batch(arrays,np.array([0,1]),0,8,{0:1,1:2.9,2:1,3:.4})
  self.assertAlmostEqual(mass,6.2,places=5);self.assertEqual(c[1],2);self.assertEqual(c[3],1);self.assertEqual(nonpad,8);self.assertEqual(float(m[1,3]),0)
 def test_schedule_is_bounded_at_two_million(self):
  self.assertAlmostEqual(lr_at(100000,3e-5),3e-5);self.assertAlmostEqual(lr_at(2000000,3e-5),1e-6)
if __name__=='__main__':unittest.main()
