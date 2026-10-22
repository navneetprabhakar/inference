"""Adapter wiring uses patched arithmetic forwards; no model parameters."""
from types import SimpleNamespace
import numpy as np
import pytest
from slm.restart.numerical_backend import NumericalBackend
from slm.restart.numerical_budget import NumericalBudget,NumericalBudgetError

@pytest.fixture(params=['mlx','torch'])
def adapter(request,tmp_path):
    budget=NumericalBudget(tmp_path/'budget',identity='fixture',deadline=100)
    a=NumericalBackend(request.param,{},SimpleNamespace(),budget,clock=lambda:1)
    yield a
    budget.close()


def test_forward_charged_before_backend_and_exports_numpy(adapter,monkeypatch):
    def forward(p,c,tokens,padding_mask=None,cache=None):
        with pytest.raises(NumericalBudgetError):adapter.budget.events()
        assert adapter.budget.events(require_complete=False)[0]['positions']==2
        values=adapter._array(np.ones((1,2,3),np.float32))
        return values,[],[values]
    monkeypatch.setattr(adapter.impl,'forward',forward)
    values,cache,traces=adapter.forward([[10,11]],padding_mask=[[True,True]])
    assert isinstance(values,np.ndarray) and isinstance(traces[0],np.ndarray)
    assert adapter.budget.events()[0]['kind']=='forward'


def test_gradient_charged_before_backend_and_exports_numpy(adapter,monkeypatch):
    def gradient(*args,**kwargs):
        assert adapter.budget.events(require_complete=False)[0]['kind']=='gradient'
        return adapter._array(np.array(2.,np.float32)),{'fixture':adapter._array(np.ones(2,np.float32))}
    monkeypatch.setattr(adapter.impl,'value_and_grad',gradient)
    batch={'inputs':[[0,10]],'targets':[[10,1]],'loss_mask':[[1,1]],'padding_mask':[[True,True]]}
    value,g=adapter.gradient(batch);assert value==2 and isinstance(g['fixture'],np.ndarray)
    assert adapter.budget.events()[0]['positions']==2


def test_backend_error_retains_charge_and_is_terminal(adapter,monkeypatch):
    def fail(*args,**kwargs):raise ValueError('arithmetic fixture error')
    monkeypatch.setattr(adapter.impl,'forward',fail)
    with pytest.raises(ValueError):adapter.forward([[10]])
    assert adapter.budget.events(require_complete=False)[0]['positions']==1
    with pytest.raises(NumericalBudgetError):adapter.forward([[10]])


def test_real_ce_uniform_arithmetic_no_model(adapter):
    value,g=adapter.cross_entropy(np.zeros((1,4),np.float32),np.array([0],np.int32))
    assert value==pytest.approx(np.log(4),abs=1e-6)
    np.testing.assert_allclose(g,[[-.75,.25,.25,.25]],rtol=0,atol=1e-6)
    assert adapter.budget.events()[0]['kind']=='ce_gradient'


def test_nonfinite_export_is_not_marked_complete(adapter,monkeypatch):
    def forward(*args,**kwargs):return adapter._array(np.array([[[float('nan')]]],np.float32)),[],[]
    monkeypatch.setattr(adapter.impl,'forward',forward)
    with pytest.raises(ValueError,match='Nonfinite'):adapter.forward([[10]])
    with pytest.raises(NumericalBudgetError):adapter.budget.events()


def test_real_optimizer_charged_and_state_captured(adapter):
    adapter.params={'fixture':adapter._array(np.array([[1.,2.]],np.float32))}
    moments,capture=adapter.optimize({'fixture':np.array([[3.,4.]],np.float32)},{},step=1,positions=32)
    assert capture['step']==1 and capture['lr']==.02 and capture['moments_before']=={}
    np.testing.assert_array_equal(capture['before']['fixture'],[[1.,2.]])
    np.testing.assert_array_equal(adapter.impl.export(adapter.params)['fixture'],capture['after']['fixture'])
    assert len(moments['fixture'])==2 and adapter.budget.events()[0]['optimizer_updates']==1


def test_bad_optimizer_gradient_does_not_install_new_state(adapter):
    adapter.params={'fixture':adapter._array(np.array([[1.,2.]],np.float32))}
    with pytest.raises(ValueError):adapter.optimize({'fixture':np.array([[float('nan'),1.]],np.float32)},{},step=1,positions=32)
    np.testing.assert_array_equal(adapter.impl.export(adapter.params)['fixture'],[[1.,2.]])
    with pytest.raises(NumericalBudgetError):adapter.budget.events()
