import numpy as np
import pytest
import torch
from slm.common.config import Config,initialize
from slm.common.training import Batches,Trainer,Recipe,recipe_from_state
from slm.backends import torch_backend as tb
from test_resume import compare
DENSE='dense-onehot-v1'


def fixture():
    x=np.tile(np.array([[1,2,1,3,2,1,1,2]],np.int64),(2,1));y=np.roll(x,-1,axis=1)
    return x,y,np.ones(x.shape,np.float32)


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_dense_forward_and_gradients_match_native_at_original_bounds(backend):
    c=Config();x,y,m=fixture()
    if backend=='mlx':
        mx=pytest.importorskip('mlx.core');from slm.backends import mlx_backend as impl
        args=tuple(mx.array(v) for v in (x,y,m))
    else:impl=tb;args=tuple(torch.tensor(v) for v in (x,y,m))
    p=impl.load(c,initialize(c));native=impl.value_and_grad(p,c,*args);dense=impl.value_and_grad(p,c,*args,embedding_implementation=DENSE)
    a=impl.export({'value':native[0],**native[1]});b=impl.export({'value':dense[0],**dense[1]})
    for k in a:np.testing.assert_allclose(a[k],b[k],atol=1e-6,rtol=1e-4)
    plain=impl.export({'logits':impl.forward(p,c,args[0])[0]})['logits'];other=impl.export({'logits':impl.forward(p,c,args[0],embedding_implementation=DENSE)[0]})['logits']
    np.testing.assert_allclose(plain,other,atol=1e-5,rtol=1e-4)
    reference=None
    for _ in range(20):
        value,g=impl.value_and_grad(p,c,*args,embedding_implementation=DENSE);actual=impl.export({'value':value,**g})
        if reference is None:reference=actual
        for k in reference:np.testing.assert_array_equal(reference[k],actual[k])


def test_dense_existing_golden100_control_uses_unchanged_bounds():
    pytest.importorskip('mlx.core')
    from test_parity import fixture as golden
    c=Config();data=Batches([golden(c)]*100,c.vocab_size)
    recipe=Recipe(embedding_implementation=DENSE,warmup_tokens=0)
    a=Trainer(c,initialize(c),data,'mlx',recipe=recipe);b=Trainer(c,initialize(c),data,recipe=recipe)
    for _ in range(100):
        ra=a.update();rb=b.update();np.testing.assert_allclose(ra['loss'],rb['loss'],atol=1e-5,rtol=1e-4);compare(a,b)


def test_embedding_recipe_is_preserved_and_cannot_silently_change_on_resume(tmp_path):
    data=Batches([fixture()]*4,64);a=Trainer(Config(),initialize(Config()),data,recipe=Recipe(embedding_implementation=DENSE))
    a.update();a.save(tmp_path/'state');b=Trainer.resume(tmp_path/'state',data)
    assert b.recipe.embedding_implementation==DENSE
    a.update();b.update();compare(a,b,True)
    assert recipe_from_state({'recipe':{'lr':.001},'reproduction':{}}).embedding_implementation=='native-gather-v1'
    with pytest.raises(ValueError,match='metadata mismatch'):
        recipe_from_state({'recipe':{'embedding_implementation':DENSE},'reproduction':{'embedding_implementation':'native-gather-v1'}})
    with pytest.raises(ValueError):Recipe(embedding_implementation='unknown')


@pytest.mark.skipif(not torch.cuda.is_available(),reason='NVIDIA CUDA device unavailable')
def test_dense_cuda_matches_cpu_at_existing_bounds():
    c=Config();data=Batches([fixture()]*10,64);recipe=Recipe(embedding_implementation=DENSE)
    a=Trainer(c,initialize(c),data,recipe=recipe);b=Trainer(c,initialize(c),data,device='cuda',recipe=recipe)
    for _ in range(10):a.update();b.update();compare(a,b)
