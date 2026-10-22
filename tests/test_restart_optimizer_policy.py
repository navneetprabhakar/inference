"""Standalone arithmetic fixtures: no network initialization or training data."""
import numpy as np
import pytest

@pytest.mark.parametrize('backend',['torch','mlx'])
def test_matrix_only_decay_includes_tied_embedding(backend):
    # Zero gradients isolate decay from the adaptive update. Names must not
    # silently exempt a matrix from the frozen restart recipe.
    if backend=='torch':
        import torch
        from slm.backends.torch_backend import adamw
        array=lambda x:torch.tensor(x,dtype=torch.float32)
        export=lambda x:x.detach().numpy()
    else:
        import mlx.core as mx
        from slm.backends.mlx_backend import adamw
        array=lambda x:mx.array(x,dtype=mx.float32)
        export=lambda x:np.array(x)
    fixtures={'embedding':np.array([[1.,-2.],[3.,4.]],np.float32),
              'layers.0.q':np.array([[.5,-.5],[2.,-2.]],np.float32),
              'final_norm':np.array([1.,2.],np.float32)}
    p={k:array(x) for k,x in fixtures.items()};g={k:array(np.zeros_like(x)) for k,x in fixtures.items()}
    result,state=adamw(p,g,{},1,lr=.02,decay=.1)
    for k,x in fixtures.items():
        expected=x*(1-.02*.1) if x.ndim==2 else x
        np.testing.assert_allclose(export(result[k]),expected,rtol=0,atol=1e-7)
        for moment in state[k]:np.testing.assert_array_equal(export(moment),np.zeros_like(x))

@pytest.mark.parametrize('backend',['torch','mlx'])
def test_clipped_update_matches_independent_native_adamw(backend):
    import torch
    values={'embedding':np.array([[.2,-.3],[.8,-.9]],np.float32),
            'projection':np.array([[.4,.1],[-.2,.7]],np.float32),
            'norm':np.array([1.,.8],np.float32)}
    gradients={k:np.arange(1,x.size+1,dtype=np.float32).reshape(x.shape) for k,x in values.items()}
    native={k:torch.tensor(x,requires_grad=True) for k,x in values.items()}
    optimizer=torch.optim.AdamW([
        {'params':[x for x in native.values() if x.ndim==2],'weight_decay':.1},
        {'params':[x for x in native.values() if x.ndim!=2],'weight_decay':0.}],
        lr=2e-4,betas=(.9,.95),eps=1e-8,foreach=False)
    for k,x in native.items():x.grad=torch.tensor(gradients[k])
    torch.nn.utils.clip_grad_norm_(list(native.values()),1.)
    optimizer.step()
    if backend=='torch':
        from slm.backends.torch_backend import adamw
        array=lambda x:torch.tensor(x)
        export=lambda x:x.detach().numpy()
    else:
        import mlx.core as mx
        from slm.backends.mlx_backend import adamw
        array=lambda x:mx.array(x)
        export=lambda x:np.array(x)
    out,moments=adamw({k:array(x) for k,x in values.items()},
                      {k:array(x) for k,x in gradients.items()}, {},1,2e-4)
    for k in values:
        np.testing.assert_allclose(export(out[k]),native[k].detach().numpy(),rtol=0,atol=1e-6)
        for actual,key in zip(moments[k],['exp_avg','exp_avg_sq']):
            np.testing.assert_allclose(export(actual),optimizer.state[native[k]][key].numpy(),rtol=0,atol=1e-6)
