"""Meaningful smoke check: the throughput model must not see future tokens."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mlx.core as mx
import mlx.nn as nn
from mlx.utils import tree_flatten
from benchmark_mlx import Model
class ProbeTest(unittest.TestCase):
    def test_causality_and_finite_gradients(self):
        mx.random.seed(7);m=Model(64,2,128)
        a=mx.random.randint(0,128,(2,513));b=mx.concatenate([a[:,:3],mx.random.randint(0,128,(2,510))],axis=1)
        self.assertTrue(bool(mx.allclose(m(a)[:,:3],m(b)[:,:3],atol=1e-5)))
        def loss(model,x):return nn.losses.cross_entropy(model(x[:,:-1]),x[:,1:]).mean()
        value,grads=nn.value_and_grad(m,loss)(m,a)
        self.assertTrue(bool(mx.isfinite(value)))
        self.assertTrue(all(bool(mx.all(mx.isfinite(g))) for _,g in tree_flatten(grads)))
if __name__=='__main__':unittest.main()
