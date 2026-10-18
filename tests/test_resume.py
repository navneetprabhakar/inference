import numpy as np
import pytest
from slm.common.config import Config, initialize
from slm.common.training import Batches, Recipe, Trainer


def dataset(seed=1):
    rng = np.random.default_rng(seed)
    return Batches([(rng.integers(0, 64, (2, t)), rng.integers(0, 64, (2, t)),
                     np.ones((2, t))) for t in [4, 6, 3, 8, 5, 7]], 64)


def compare(a, b, exact=False):
    aw, bw = a.impl.export(a.params), b.impl.export(b.params)
    for k in aw:
        if exact:
            np.testing.assert_array_equal(aw[k], bw[k])
        else:
            np.testing.assert_allclose(aw[k], bw[k], atol=1e-5, rtol=1e-4)
    assert (a.step,a.cursor,a.tokens,a.supervised_tokens) == (b.step,b.cursor,b.tokens,b.supervised_tokens)
    for slot in range(2):
        am = a.impl.export({k: v[slot] for k,v in a.moments.items()})
        bm = b.impl.export({k: v[slot] for k,v in b.moments.items()})
        for k in am:
            np.testing.assert_allclose(am[k], bm[k], atol=0 if exact else 1e-6, rtol=0 if exact else 1e-4)


@pytest.mark.parametrize('backend', ['torch', 'mlx'])
def test_same_backend_resume(tmp_path, backend):
    if backend == 'mlx': pytest.importorskip('mlx.core')
    c=Config(); data=dataset()
    a=Trainer(c,initialize(c),data,backend)
    for _ in range(3): a.update()
    a.save(tmp_path/'step3')
    b=Trainer.resume(tmp_path/'step3',data,backend)
    compare(a,b,True)
    for _ in range(3):
        assert a.update() == b.update()
        compare(a,b,True)
    with pytest.raises(StopIteration): b.update()


def test_cross_backend_continuation(tmp_path):
    pytest.importorskip('mlx.core')
    c=Config(); data=dataset()
    reference=Trainer(c,initialize(c),data,'mlx')
    for _ in range(2): reference.update()
    reference.save(tmp_path/'mlx')
    moved=Trainer.resume(tmp_path/'mlx',data,'torch')
    for _ in range(2): reference.update(); moved.update()
    compare(reference,moved)
    moved.save(tmp_path/'torch')
    returned=Trainer.resume(tmp_path/'torch',data,'mlx')
    for _ in range(2): reference.update(); returned.update()
    compare(reference,returned)


def test_reject_mismatch_corruption_and_overwrite(tmp_path):
    data=dataset(); a=Trainer(Config(),initialize(Config()),data)
    a.update(); a.save(tmp_path/'good')
    with pytest.raises(FileExistsError): a.save(tmp_path/'good')
    with pytest.raises(ValueError,match='mismatch'): Trainer.resume(tmp_path/'good',dataset(2))
    with pytest.raises(ValueError,match='mismatch'): Trainer.resume(tmp_path/'good',data,tokenizer_hash='different')
    with (tmp_path/'good'/'optimizer.safetensors').open('ab') as f: f.write(b'bad')
    with pytest.raises(ValueError,match='Checksum'): Trainer.resume(tmp_path/'good',data)


def test_interrupted_save_preserves_previous(tmp_path,monkeypatch):
    import slm.common.training as module
    a=Trainer(Config(),initialize(Config()),dataset()); a.update(); a.save(tmp_path/'old')
    def fail(*args, **kwargs): raise OSError('disk full')
    monkeypatch.setattr(module,'save_file',fail)
    with pytest.raises(OSError): a.save(tmp_path/'new')
    assert not (tmp_path/'new').exists()
    assert not list(tmp_path.glob('.training-*'))
    compare(a,Trainer.resume(tmp_path/'old',dataset()),True)


def test_initial_resume_and_schedule(tmp_path):
    a=Trainer(Config(),initialize(Config()),dataset())
    a.save(tmp_path/'zero'); b=Trainer.resume(tmp_path/'zero',dataset())
    assert a.update() == b.update()
    assert a.recipe.rate(50) == .0005
    assert a.recipe.rate(200) == .001
    compare(a,b,True)
    with pytest.raises(ValueError): Recipe(beta1=1.)
