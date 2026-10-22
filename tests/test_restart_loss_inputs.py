"""Loss input validation using fixed arrays; no model or optimizer invocation."""
import numpy as np
import pytest

@pytest.fixture(params=['torch','mlx'])
def impl(request):
    if request.param=='torch':
        import torch
        from slm.backends import torch_backend as backend
        return backend,torch.tensor
    import mlx.core as mx
    from slm.backends import mlx_backend as backend
    return backend,mx.array

@pytest.mark.parametrize('bad_mask',[
 [[float('inf'),1.]], [[float('nan'),1.]], [[-1.,1.]], [[0.,0.]], [[3e38,3e38]],
])
def test_invalid_mask_rejected_before_forward(impl,monkeypatch,bad_mask):
    backend,array=impl
    def forbidden(*args,**kwargs):raise AssertionError('Forward must not run for invalid supervision')
    monkeypatch.setattr(backend,'forward',forbidden)
    with pytest.raises(ValueError):
        backend.loss({},None,array(np.array([[0,1]],np.int64)),array(np.array([[1,0]],np.int64)),array(np.array(bad_mask,np.float32)))

@pytest.mark.parametrize('logits,labels',[
 ([[0.,float('nan')]], [0]),
 ([[float('inf'),0.]], [0]),
 ([[0.,-float('inf')]], [0]),
 ([[0.,1.]], [-1]),
 ([[0.,1.]], [2]),
 ([[0.,1.]], [0.5]),
 ([[0.,1.]], [[0]]),
 ([[]], [0]),
])
def test_invalid_cross_entropy_inputs_fail_explicitly(impl,logits,labels):
    backend,array=impl
    with pytest.raises(ValueError):
        backend.cross_entropy_logits(array(np.array(logits,np.float32)),array(np.array(labels)))

@pytest.mark.parametrize('dtype',[np.int32,np.int64])
def test_valid_integer_targets_supported(impl,dtype):
    backend,array=impl
    result=backend.cross_entropy_logits(array(np.array([[0.,0.]],np.float32)),array(np.array([1],dtype)))
    if hasattr(result,'detach'):result=result.detach().numpy()
    else:result=np.array(result)
    np.testing.assert_allclose(result,[np.log(2)],rtol=0,atol=1e-7)


def test_masked_loss_and_gradient_match_fp64_reference(impl,monkeypatch):
    import torch
    backend,array=impl
    logits=(np.arange(30,dtype=np.float32).reshape(2,3,5)%7-3)*.25
    targets=np.array([[1,3,4],[2,1,0]],np.int64)
    mask=np.array([[1,1,1],[1,1,0]],np.float32)
    # A fixed logits fixture isolates the real backend loss from any model.
    monkeypatch.setattr(backend,'forward',lambda p,*args,**kwargs:(p['fixture'],[],[]))
    if backend.__name__.endswith('torch_backend'):
        values=torch.tensor(logits,requires_grad=True)
        loss=backend.loss({'fixture':values},None,array(targets),array(targets),array(mask),loss_implementation=backend.STABLE_LOSS_IMPLEMENTATION)
        gradient=torch.autograd.grad(loss,values)[0].numpy();value=loss.detach().numpy()
    else:
        import mlx.core as mx
        value,gradient=mx.value_and_grad(lambda x:backend.loss({'fixture':x},None,array(targets),array(targets),array(mask),loss_implementation=backend.STABLE_LOSS_IMPLEMENTATION))(array(logits))
        mx.eval(value,gradient);value=np.array(value);gradient=np.array(gradient)
    ref=torch.tensor(logits,dtype=torch.float64,requires_grad=True)
    per=torch.nn.functional.cross_entropy(ref.reshape(-1,5),torch.tensor(targets.reshape(-1)),reduction='none').reshape(2,3)
    expected=(per*torch.tensor(mask)).sum()/5
    expected_gradient=torch.autograd.grad(expected,ref)[0].numpy()
    np.testing.assert_allclose(value,expected.detach().numpy(),rtol=0,atol=1e-6)
    np.testing.assert_allclose(gradient,expected_gradient,rtol=0,atol=1e-6)
    np.testing.assert_array_equal(gradient[1,2],np.zeros(5))
    assert abs(gradient[0,0,1])>0 and abs(gradient[1,1,1])>0  # EOS remains supervised.
