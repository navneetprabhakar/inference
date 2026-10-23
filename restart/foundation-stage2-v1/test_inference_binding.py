"""CPU-only regression, fixed 2x2 arrays; no student/model checkpoint loading."""
from types import SimpleNamespace
import mlx.core as mx
import numpy as np
from inference_binding import bind_compute_views

def main():
    mx.set_default_device(mx.cpu)
    class Model:
        def update(self,params):self.w=params['w']
        def __call__(self,x):return x@self.w
    model=Model();weights=mx.array([[1.,2.],[3.,4.]],dtype=mx.float32)
    x=mx.array([[2.,1.]],dtype=mx.bfloat16)
    @mx.compile
    def validation(params,x):
        model.update({'w':params['w'].astype(mx.bfloat16)})
        return model(x)
    params={'w':weights};output=validation(params,x);mx.eval(output)
    reproduced=False
    try:mx.eval(model(x))
    except RuntimeError as error:
        assert 'without a primitive' in str(error);reproduced=True
    assert reproduced,'Regression must reproduce the original compile-state leak'
    engine=SimpleNamespace(model=model,params=params,dtype=mx.bfloat16)
    bound=bind_compute_views(engine);fixed=bound(x);mx.eval(fixed)
    np.testing.assert_array_equal(np.array(fixed.astype(mx.float32)),np.array([[5.,8.]],np.float32))
    assert engine.params['w'].dtype==mx.float32 and model.w.dtype==mx.bfloat16
    np.testing.assert_array_equal(np.array(weights),np.array([[1.,2.],[3.,4.]],np.float32))
    # Changing the master arrays must also refresh the direct-inference binding.
    engine.params={'w':mx.array([[2.,0.],[0.,2.]],dtype=mx.float32)}
    refreshed=bind_compute_views(engine)(x);mx.eval(refreshed)
    np.testing.assert_array_equal(np.array(refreshed.astype(mx.float32)),np.array([[4.,2.]],np.float32))
    print('PASS: original tracing leak reproduced; real compute-view rebinding fixes it; FP32 masters preserved; latest arrays used; CPU only.')
if __name__=='__main__':main()
