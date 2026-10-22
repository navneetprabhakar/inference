import numpy as np
import pytest
from slm.restart.accumulation import TargetAccumulator

@pytest.fixture(params=['torch','mlx'])
def backend(request):
    if request.param=='torch':
        import torch
        return 'torch',lambda x:torch.tensor(x,dtype=torch.float32),lambda x:x.detach().numpy()
    import mlx.core as mx
    return 'mlx',lambda x:mx.array(np.asarray(x,dtype=np.float32)),lambda x:np.array(x)


def test_unequal_targets_match_full_batch_analytic_gradient(backend):
    name,array,numpy=backend
    # Squared-error gradients at a fixed scalar value, not model parameters.
    labels=np.array([1.,2.,4.,8.],np.float32)
    gradients=2*(.5-labels);losses=(.5-labels)**2
    acc=TargetAccumulator({'fixture':(1,)},name)
    acc.add(float(losses[:1].mean()),{'fixture':array([gradients[:1].mean()])},1)
    acc.add(float(losses[1:].mean()),{'fixture':array([gradients[1:].mean()])},3)
    value,g=acc.finish()
    assert abs(value-float(losses.mean()))<=1e-6
    np.testing.assert_allclose(numpy(g['fixture']),[gradients.mean()],rtol=0,atol=1e-6)
    assert (acc.targets,acc.microbatches)==(4,2)
    assert abs((gradients[:1].mean()+gradients[1:].mean())/2-gradients.mean())>1
    with pytest.raises(ValueError):acc.finish()
    with pytest.raises(ValueError):acc.add(1,{'fixture':array([1.])},1)


@pytest.mark.parametrize('fault',['nan','shape','missing','overflow','targets','loss'])
def test_failed_microbatch_does_not_mutate_prior_state(backend,fault):
    name,array,numpy=backend;acc=TargetAccumulator({'fixture':(1,)},name,target_cap=4)
    acc.add(2.,{'fixture':array([3.])},1)
    loss=1.;n=2;g={'fixture':array([1.])}
    if fault=='nan':g={'fixture':array([float('nan')])}
    if fault=='shape':g={'fixture':array([1.,2.])}
    if fault=='missing':g={}
    if fault=='overflow':g={'fixture':array([3e38])}
    if fault=='targets':n=4
    if fault=='loss':loss=float('inf')
    with pytest.raises(ValueError):acc.add(loss,g,n)
    assert (acc.targets,acc.microbatches)==(1,1)
    value,g=acc.finish();assert value==2
    np.testing.assert_array_equal(numpy(g['fixture']),[3.])


def test_empty_accumulator_rejected(backend):
    with pytest.raises(ValueError):TargetAccumulator({'x':(1,)},backend[0]).finish()
