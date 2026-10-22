"""Oracle/harness checks use arithmetic, never neural parameter initialization."""
import numpy as np
import pytest
from slm.restart.numerical_oracles import ce_reference,cross_entropy_cases,tied_embedding_case,finite_difference_case


def test_ce_reference_matches_uniform_analytic_and_preserves_tail():
    loss,g=ce_reference([0.,0.,0.,0.],0)
    assert loss==pytest.approx(np.log(4))
    np.testing.assert_allclose(g,[-.75,.25,.25,.25],atol=1e-15)
    loss,g=ce_reference([60.,0.,0.,0.],0)
    assert loss>0 and g[0]<0 and np.all(g[1:]>0)
    assert abs(g.sum())<1e-40


def ce_stub(fault=None):
    def invoke(backend,x,y):
        loss,g=ce_reference(x[0],int(y[0]));g=g[None,:]
        if fault=='tail' and x[0,0]-x[0,1]>50:g[:]=0
        if fault=='offset' and x[0,1]>0:loss+=.1
        return loss,g
    return invoke


def test_ce_cases_and_tiny_gradient_failure_detection():
    assert all(v['passed'] for v in cross_entropy_cases(ce_stub())['cases'].values())
    assert not cross_entropy_cases(ce_stub('tail'))['cases']['gradients:stable_ce_confident_tail']['passed']
    assert not cross_entropy_cases(ce_stub('offset'))['cases']['gradients:stable_ce_common_offset']['passed']


def test_tied_embedding_decomposition_requires_both_paths():
    result=tied_embedding_case(lambda _: (np.array([3.,5.]),np.array([1.,2.]),np.array([2.,3.])))
    assert result['gradients:tied_embedding_both_paths']['passed']
    assert not tied_embedding_case(lambda _: (np.ones(2),np.zeros(2),np.ones(2)))['gradients:tied_embedding_both_paths']['passed']
    assert not tied_embedding_case(lambda _: (np.ones(2),np.ones(2),np.ones(2)))['gradients:tied_embedding_both_paths']['passed']


def test_finite_difference_oracle_detects_bad_analytic_gradient():
    p={n:np.array([.5,1.],np.float32) for n in ('embedding','layers.0.q','layers.0.down','final_norm')}
    analytic={b:{k:2*v for k,v in p.items()} for b in ('mlx','torch')}
    base=sum(float(np.square(v.astype(np.float64)).sum()) for v in p.values())
    def loss(name,index,replacement):return base-float(p[name][index])**2+replacement**2
    r=finite_difference_case(p,analytic,loss)
    assert r['cases']['gradients:finite_difference_selected_parameters']['passed'] and r['fp64_forward_calls']==16
    analytic['mlx']['final_norm'][1]+=.1
    assert not finite_difference_case(p,analytic,loss)['cases']['gradients:finite_difference_selected_parameters']['passed']


def test_nonfinite_oracle_never_passes():
    with pytest.raises(ValueError):cross_entropy_cases(lambda *a:(float('nan'),np.ones((1,4))))
    with pytest.raises(ValueError):tied_embedding_case(lambda _:(np.ones(2),np.ones(2),np.array([1.,float('nan')])))
