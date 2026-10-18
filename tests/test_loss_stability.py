import math
import numpy as np
import pytest
import torch
from slm.backends import torch_backend as tb


def evaluate(backend,logits,targets):
    if backend=='torch':
        values=torch.tensor(logits,requires_grad=True)
        losses=tb.cross_entropy_logits(values,torch.tensor(targets))
        grads=torch.autograd.grad(losses.sum(),values)[0]
        return losses.detach().numpy(),grads.detach().numpy()
    mx=pytest.importorskip('mlx.core')
    from slm.backends import mlx_backend as mb
    values=mx.array(logits);labels=mx.array(targets)
    loss,grad=mx.value_and_grad(lambda x:mx.sum(mb.cross_entropy_logits(x,labels)))(values)
    losses=mb.cross_entropy_logits(values,labels)
    mx.eval(losses,grad)
    return np.array(losses),np.array(grad)


@pytest.mark.parametrize('backend',['torch','mlx'])
@pytest.mark.parametrize('winning_logit',[-60.,0.,15.,20.,30.,60.])
def test_confident_loss_and_every_gradient_match_analytic_reference(backend,winning_logit):
    size=16384
    logits=np.zeros((1,size),dtype=np.float32);logits[0,0]=winning_logit
    loss,grad=evaluate(backend,logits,np.array([0],dtype=np.int64))
    tail=(size-1)*math.exp(-winning_logit)
    expected_loss=math.log1p(tail)
    expected_grad=np.full(logits.shape,math.exp(-winning_logit)/(1+tail),dtype=np.float64)
    expected_grad[0,0]=-tail/(1+tail)
    np.testing.assert_allclose(loss,[expected_loss],rtol=3e-6,atol=0)
    np.testing.assert_allclose(grad,expected_grad,rtol=3e-6,atol=0)
    assert abs(grad.astype(np.float64).sum()) < abs(expected_grad[0,0])*3e-6


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_loss_and_gradients_are_invariant_to_representable_common_offsets(backend):
    logits=(np.arange(18,dtype=np.float32)-8).reshape(2,9)
    targets=np.array([7,2],dtype=np.int64)
    expected=evaluate(backend,logits,targets)
    for shift in (-1_000_000.,1_000_000.):
        actual=evaluate(backend,logits+shift,targets)
        for a,e in zip(actual,expected):np.testing.assert_array_equal(a,e)


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_random_multiclass_matches_independent_fp64_native_cross_entropy(backend):
    logits=np.random.default_rng(719).normal(0,5,(3,17)).astype(np.float32)
    labels=np.array([0,8,16],dtype=np.int64)
    a=torch.tensor(logits,dtype=torch.float64,requires_grad=True)
    loss=torch.nn.functional.cross_entropy(a,torch.tensor(labels),reduction='none')
    grad=torch.autograd.grad(loss.sum(),a)[0]
    actual_loss,actual_grad=evaluate(backend,logits,labels)
    np.testing.assert_allclose(actual_loss,loss.detach().numpy(),rtol=2e-6,atol=1e-7)
    np.testing.assert_allclose(actual_grad,grad.numpy(),rtol=5e-6,atol=1e-8)


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_single_class_has_zero_loss_and_gradients(backend):
    loss,gradient=evaluate(backend,np.array([[30.],[-15.]],dtype=np.float32),np.array([0,0]))
    np.testing.assert_array_equal(loss,np.zeros(2))
    np.testing.assert_array_equal(gradient,np.zeros((2,1)))


def test_loss_version_restores_legacy_and_detects_metadata_conflicts():
    from dataclasses import asdict
    from slm.common.training import Recipe,recipe_from_state
    legacy=tb.DEFAULT_LOSS_IMPLEMENTATION;stable=tb.STABLE_LOSS_IMPLEMENTATION
    previous=asdict(Recipe());previous.pop('loss_implementation')
    assert recipe_from_state({'recipe':previous}).loss_implementation==legacy
    assert recipe_from_state({'recipe':previous,'reproduction':{'loss_implementation':stable}}).loss_implementation==stable
    with pytest.raises(ValueError,match='metadata mismatch'):
        recipe_from_state({'recipe':asdict(Recipe()),'reproduction':{'loss_implementation':stable}})
    with pytest.raises(ValueError,match='Unknown loss'):
        Recipe(loss_implementation='guess')


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_explicit_stable_loss_resumes_exactly_and_probe_uses_selected_loss(tmp_path,backend):
    if backend=='mlx':pytest.importorskip('mlx.core')
    import json
    from slm.common.config import Config,initialize
    from slm.common.training import Batches,Trainer,Recipe
    from slm.eval.portability import capture
    c=Config();x=np.array([[1,2,3,4]]);y=np.array([[2,3,4,5]]);mask=np.ones(x.shape,dtype=np.float32)
    data=Batches([(x,y,mask)]*3,c.vocab_size)
    recipe=Recipe(loss_implementation=tb.STABLE_LOSS_IMPLEMENTATION)
    original=Trainer(c,initialize(c),data,backend,recipe=recipe)
    original.update();original.save(tmp_path/'checkpoint')
    state=json.loads((tmp_path/'checkpoint/state.json').read_text())
    assert state['recipe']['loss_implementation']==recipe.loss_implementation
    assert state['reproduction']['loss_implementation']==recipe.loss_implementation
    resumed=Trainer.resume(tmp_path/'checkpoint',data,backend)
    assert resumed.recipe==recipe
    assert original.update()==resumed.update()
    for name,a in original.impl.export(original.params).items():
        np.testing.assert_array_equal(a,resumed.impl.export(resumed.params)[name])
    result=capture(resumed)
    loss,grad=resumed.impl.value_and_grad(resumed.params,c,resumed.array(x),resumed.array(y),resumed.array(mask),loss_implementation=recipe.loss_implementation)
    expected=resumed.impl.export({'loss':loss,**{f'gradient:{k}':v for k,v in grad.items()}})
    for name,value in expected.items():np.testing.assert_array_equal(result[name],value)


@pytest.mark.skipif(not torch.cuda.is_available(),reason='NVIDIA CUDA device unavailable')
@pytest.mark.parametrize('winning_logit',[20.,30.,60.])
def test_cuda_tail_loss_and_gradients_match_analytic_reference(winning_logit):
    size=16384
    logits=torch.zeros((1,size),device='cuda');logits[0,0]=winning_logit;logits.requires_grad_(True)
    loss=tb.cross_entropy_logits(logits,torch.tensor([0],device='cuda'))
    gradient=torch.autograd.grad(loss.sum(),logits)[0].detach().cpu().numpy()
    tail=(size-1)*math.exp(-winning_logit)
    expected=np.full((1,size),math.exp(-winning_logit)/(1+tail),dtype=np.float64);expected[0,0]=-tail/(1+tail)
    np.testing.assert_allclose(loss.detach().cpu().numpy(),[math.log1p(tail)],rtol=3e-6,atol=0)
    np.testing.assert_allclose(gradient,expected,rtol=3e-6,atol=0)
