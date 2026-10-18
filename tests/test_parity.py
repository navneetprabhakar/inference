import numpy as np
import pytest
import torch
mx = pytest.importorskip('mlx.core', reason='MLX not installed on this platform')
from slm.backends import mlx_backend as mb, torch_backend as tb
from slm.common.config import Config, initialize
from slm.common.checkpoint import save, load


def close(a, b, atol=1e-5, rtol=1e-4):
    if isinstance(b, torch.Tensor):
        b = b.detach().cpu().numpy()
    np.testing.assert_allclose(np.array(a), b, atol=atol, rtol=rtol)


def fixture(c, length=12, batch=2):
    rng = np.random.default_rng(8)
    x = rng.integers(0, c.vocab_size, (batch, length), dtype=np.int32)
    y = rng.integers(0, c.vocab_size, (batch, length), dtype=np.int32)
    mask = rng.integers(0, 2, (batch, length)).astype(np.float32)
    return x, y, mask


@pytest.mark.parametrize('heads', [(4, 2), (4, 1), (4, 4)])
@pytest.mark.parametrize('length', [1, 12, 64])
def test_logits_layer_states_loss_and_gradients(heads, length):
    c = Config(num_heads=heads[0], num_kv_heads=heads[1])
    w = initialize(c)
    mp, tp = mb.load(c, w), tb.load(c, w)
    x, y, mask = fixture(c, length)
    mask[:, 0] = 1
    ma = [mx.array(a) for a in (x, y, mask)]
    ta = [torch.tensor(x, dtype=torch.long), torch.tensor(y, dtype=torch.long), torch.tensor(mask)]
    ml, _, traces = mb.forward(mp, c, ma[0])
    tl, _, ttraces = tb.forward(tp, c, ta[0])
    close(ml, tl)
    for m, t in zip(traces, ttraces):
        close(m, t)
    mv, mg = mb.value_and_grad(mp, c, *ma)
    tv, tg = tb.value_and_grad(tp, c, *ta)
    close(mv, tv)
    for k in mg:
        close(mg[k], tg[k], atol=1e-6, rtol=1e-4)


def test_mlx_cache_and_padding():
    c = Config(max_seq_len=16)
    mp, tp = mb.load(c, initialize(c)), tb.load(c, initialize(c))
    x = np.arange(32, dtype=np.int32).reshape(2, 16)
    full = mb.forward(mp, c, mx.array(x))[0]
    cache, chunks = None, []
    for start, stop in [(0, 5), (5, 9), (9, 16)]:
        part, cache, _ = mb.forward(mp, c, mx.array(x[:, start:stop]), cache=cache)
        chunks.append(part)
    close(full, mx.concatenate(chunks, axis=1))
    mask = np.ones_like(x, dtype=bool); mask[0, 10:] = False
    close(mb.forward(mp, c, mx.array(x), mx.array(mask))[0],
          tb.forward(tp, c, torch.tensor(x), torch.tensor(mask))[0])
    close(mb.forward(mp, c, mx.array(x), mx.array(mask))[0][:1, :10],
          mb.forward(mp, c, mx.array(x[:1, :10]))[0])
    with pytest.raises(ValueError):
        mb.forward(mp, c, mx.array(x[:, :1]), cache=cache)


def test_100_training_updates_and_weight_roundtrip(tmp_path):
    c = Config()
    mp, tp = mb.load(c, initialize(c)), tb.load(c, initialize(c))
    ms, ts = {}, {}
    x, y, mask = fixture(c)
    ma = [mx.array(a) for a in (x, y, mask)]
    ta = [torch.tensor(x, dtype=torch.long), torch.tensor(y, dtype=torch.long), torch.tensor(mask)]
    for step in range(1, 101):
        mv, mg = mb.value_and_grad(mp, c, *ma)
        tv, tg = tb.value_and_grad(tp, c, *ta)
        close(mv, tv)
        mp, ms = mb.adamw(mp, mg, ms, step, .001)
        tp, ts = tb.adamw(tp, tg, ts, step, .001)
        for k in mp:
            close(mp[k], tp[k])
            close(ms[k][0], ts[k][0], atol=1e-6)
            close(ms[k][1], ts[k][1], atol=1e-6)
    assert float(mv) < 1., 'Tiny fixed-batch overfit should learn'
    save(tmp_path/'mlx', c, mb.export(mp))
    c2, w = load(tmp_path/'mlx')
    transferred = tb.load(c2, w)
    close(mb.forward(mp, c, ma[0])[0], tb.forward(transferred, c, ta[0])[0])
    save(tmp_path/'torch', c2, tb.export(transferred))
    c3, w = load(tmp_path/'torch')
    for k, v in mb.export(mb.load(c3, w)).items():
        np.testing.assert_array_equal(v, mb.export(mp)[k])


def test_mlx_zero_gradient_decay_matches_torch():
    c = Config(); w = initialize(c)
    mp, tp = mb.load(c, w), tb.load(c, w)
    mg, tg = {k: mx.zeros_like(v) for k, v in mp.items()}, {k: torch.zeros_like(v) for k, v in tp.items()}
    mp, _ = mb.adamw(mp, mg, {}, 1, .01)
    tp, _ = tb.adamw(tp, tg, {}, 1, .01)
    for k in mp:
        close(mp[k], tp[k], atol=1e-7)
    np.testing.assert_array_equal(mb.export(mp)['embedding'], w['embedding'])
    assert not np.array_equal(mb.export(mp)['layers.0.q'], w['layers.0.q'])


def test_unequal_microbatch_token_accumulation():
    c = Config()
    mp, tp = mb.load(c, initialize(c)), tb.load(c, initialize(c))
    x, y, mask = fixture(c)
    mask[0] = 0; mask[0, 0] = 1
    mask[1] = 1
    ma = [mx.array(a) for a in (x, y, mask)]
    ta = [torch.tensor(x, dtype=torch.long), torch.tensor(y, dtype=torch.long), torch.tensor(mask)]
    _, full_mg = mb.value_and_grad(mp, c, *ma)
    _, full_tg = tb.value_and_grad(tp, c, *ta)
    micro_m, micro_t = [], []
    for i in range(2):
        micro_m.append(mb.value_and_grad(mp, c, *(a[i:i+1] for a in ma))[1])
        micro_t.append(tb.value_and_grad(tp, c, *(a[i:i+1] for a in ta))[1])
    counts = mask.sum(axis=1)
    for k in mp:
        accumulated_m = sum(micro_m[i][k]*float(counts[i]) for i in range(2))/float(counts.sum())
        accumulated_t = sum(micro_t[i][k]*float(counts[i]) for i in range(2))/float(counts.sum())
        close(accumulated_m, full_mg[k], atol=1e-6)
        close(accumulated_m, accumulated_t, atol=1e-6)
        close(full_mg[k], full_tg[k], atol=1e-6)


def test_padding_and_mask_errors():
    c = Config(); p = mb.load(c, initialize(c))
    x = mx.array([[1, 2, 3]])
    with pytest.raises(ValueError, match='supervised'):
        mb.loss(p, c, x, x, mx.zeros((1, 3)))
    with pytest.raises(ValueError, match='right padding'):
        mb.forward(p, c, x, mx.array([[True, False, True]]))
    with pytest.raises(ValueError):
        mb.forward(p, c, x, mx.array([[False, False, False]]))
