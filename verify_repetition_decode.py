import unittest
import torch
from repetition_decode import penalize,greedy
from evaluate import greedy as original
class Model(torch.nn.Module):
    def __init__(self):super().__init__();self.p=torch.nn.Parameter(torch.zeros(1))
    def forward(self,x):return torch.tensor([[[4.,3.,-2.]]]).expand(1,x.shape[1],3)
class Guard:
    def __init__(self):self.calls=0
    def check(self):self.calls+=1
class Tests(unittest.TestCase):
    def test_sign_unique_and_immutable(self):
        x=torch.tensor([4.,-2.,3.]);y=penalize(x,[0,0,1],2.)
        self.assertEqual(y.tolist(),[2.,-4.,3.]);self.assertEqual(x.tolist(),[4.,-2.,3.])
    def test_default_exact_and_penalty_changes_loop(self):
        m=Model();a=Guard();b=Guard()
        self.assertEqual(greedy(m,[1],4,a),original(m,[1],4,b))
        self.assertEqual(a.calls,4)
        self.assertEqual(greedy(m,[1],2,Guard(),repetition_penalty=2.),[0,1])
    def test_invalid(self):
        for p in [0,-1,float('nan'),float('inf'),True]:
            with self.assertRaises(ValueError):penalize(torch.ones(3),[],p)
if __name__=='__main__':unittest.main(verbosity=2)
