import numpy as np
import torch
from slm.common.config import Config,initialize
from slm.eval.precision import forward64
from slm.backends import torch_backend as impl


def test_independent_oracle_matches_fp32_reference_and_causality():
    c=Config();w=initialize(c)
    tokens=torch.tensor([[1,2,3,4]])
    p={k:torch.tensor(v,dtype=torch.float64,requires_grad=True) for k,v in w.items()}
    precise,layers=forward64(p,c,tokens)
    approximate,_,traces=impl.forward(impl.load(c,w),c,tokens)
    np.testing.assert_allclose(approximate.detach(),precise.detach(),atol=1e-6,rtol=1e-4)
    changed=tokens.clone();changed[:,-1]=12
    other,_=forward64(p,c,changed)
    torch.testing.assert_close(precise[:,:-1],other[:,:-1],atol=0,rtol=0)
    assert len(layers)==len(traces)==c.num_layers and precise.dtype==torch.float64


def test_oracle_complex_rotation_gradient_matches_finite_difference():
    c=Config();w=initialize(c)
    p={k:torch.tensor(v,dtype=torch.float64,requires_grad=True) for k,v in w.items()}
    x=torch.tensor([[1,2,3,4]]);y=torch.tensor([2,3,4,5])
    def objective():
        return torch.nn.functional.cross_entropy(forward64(p,c,x)[0].reshape(-1,c.vocab_size),y)
    gradient=torch.autograd.grad(objective(),p['layers.0.q'])[0][0,0]
    epsilon=1e-5
    with torch.no_grad():
        original=p['layers.0.q'][0,0].item()
        p['layers.0.q'][0,0]=original+epsilon;plus=objective().item()
        p['layers.0.q'][0,0]=original-epsilon;minus=objective().item()
        p['layers.0.q'][0,0]=original
    assert abs((plus-minus)/(2*epsilon)-gradient.item())<1e-8
