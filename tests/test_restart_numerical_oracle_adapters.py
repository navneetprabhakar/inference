"""Small deterministic array expressions, no decoder model or optimizer."""
from types import SimpleNamespace
import numpy as np
import pytest
from slm.restart.numerical_backend import NumericalBackend
from slm.restart.numerical_budget import NumericalBudget

@pytest.fixture(params=['mlx','torch'])
def setup(request,tmp_path,monkeypatch):
    budget=NumericalBudget(tmp_path/'budget',identity='array-oracle',deadline=100)
    config=SimpleNamespace(norm_eps=1e-5)
    a=NumericalBackend(request.param,{},config,budget,clock=lambda:1)
    # Fixed arithmetic matrices, not Config.initialize or saved model weights.
    embedding=np.array([[.1,.2],[.2,-.1],[.3,.4],[-.2,.2]],np.float32)
    if request.param=='torch':
        a.params={'embedding':a.module.tensor(embedding,requires_grad=True),'final_norm':a.module.ones(2,requires_grad=True)}
    else:a.params={'embedding':a.module.array(embedding),'final_norm':a.module.ones(2)}
    def forward(p,c,tokens,padding_mask=None):
        residual=p['embedding'][tokens]
        if a.name=='mlx':hidden=residual*a.module.rsqrt(a.module.mean(residual**2,axis=-1,keepdims=True)+c.norm_eps)*p['final_norm']
        else:hidden=residual*a.module.rsqrt((residual**2).mean(-1,keepdim=True)+c.norm_eps)*p['final_norm']
        return hidden@p['embedding'].T,[],[residual]
    monkeypatch.setattr(a.impl,'forward',forward)
    batch={'inputs':[[0,2]],'targets':[[2,1]],'loss_mask':[[1.,1.]],'padding_mask':[[True,True]]}
    yield a,batch
    budget.close()


def test_real_autodiff_path_decomposition_and_charging(setup):
    a,b=setup;before=a.impl.export(a.params)
    full,input_only,output_only=a.tied_embedding(b)
    np.testing.assert_allclose(full,input_only+output_only,rtol=0,atol=1e-6)
    assert np.any(input_only!=0) and np.any(output_only!=0)
    for k,v in a.impl.export(a.params).items():np.testing.assert_array_equal(v,before[k])
    assert a.budget.events()[0]['positions']==6 and a.budget.events()[0]['kind']=='gradient'


def test_fp64_finite_difference_preserves_fp32_arrays(setup):
    a,b=setup
    if a.name!='torch':
        with pytest.raises(ValueError):a.loss64(b,'embedding',(0,0),.1)
        assert not a.budget.events();return
    before=a.impl.export(a.params);value=float(before['embedding'][0,0]);eps=1e-4
    plus=a.loss64(b,'embedding',(0,0),value+eps);minus=a.loss64(b,'embedding',(0,0),value-eps)
    full,_,_=a.tied_embedding(b)
    assert abs((plus-minus)/(2*eps)-float(full[0,0]))<1e-5
    for k,v in a.impl.export(a.params).items():
        assert v.dtype==np.float32;np.testing.assert_array_equal(v,before[k])
    assert [e['kind'] for e in a.budget.events()]==['fp64_loss','fp64_loss','gradient']
