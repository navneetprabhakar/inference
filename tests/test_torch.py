import numpy as np
import pytest
import torch
from slm.common.config import Config, initialize
from slm.backends import torch_backend as tb


def test_rope_known_rotation():
    x = torch.tensor([[[[1., 0., 0., 1.]]]])
    out = tb.rope(x, torch.tensor([1.]), 10000.)
    expected = torch.tensor([[[[np.cos(1), np.sin(1), -np.sin(.01), np.cos(.01)]]]], dtype=torch.float32)
    torch.testing.assert_close(out, expected)


def test_loss_matches_native_cross_entropy_and_mask():
    c = Config()
    p = tb.load(c, initialize(c))
    x = torch.tensor([[1, 2, 3, 4]])
    y = torch.tensor([[2, 3, 4, 5]])
    mask = torch.tensor([[0., 1., 0., 1.]])
    logits, _, _ = tb.forward(p, c, x)
    expected = torch.nn.functional.cross_entropy(logits.reshape(-1, c.vocab_size), y.flatten(), reduction='none')
    torch.testing.assert_close(tb.loss(p, c, x, y, mask), (expected*mask.flatten()).sum()/mask.sum())
    with pytest.raises(ValueError):
        tb.loss(p, c, x, y, mask*0)


def test_reference_adamw_against_native():
    c = Config()
    p = tb.load(c, initialize(c))
    native = tb.load(c, initialize(c))
    groups = [dict(params=[w for k, w in native.items() if w.ndim == 2 and k != 'embedding'], weight_decay=.1),
              dict(params=[w for k, w in native.items() if w.ndim != 2 or k == 'embedding'], weight_decay=0.)]
    opt = torch.optim.AdamW(groups, lr=.001, betas=(.9, .95), eps=1e-8, foreach=False, fused=False)
    state = {}
    rng = np.random.default_rng(7)
    for step in range(1, 5):
        grads = {k: torch.tensor(rng.normal(size=w.shape).astype('float32')) for k, w in p.items()}
        if step == 4:
            grads = {k: torch.zeros_like(w) for k, w in p.items()}
        for k in native:
            native[k].grad = grads[k].clone()
        torch.nn.utils.clip_grad_norm_(list(native.values()), 1.)
        opt.step()
        p, state = tb.adamw(p, grads, state, step, .001)
        for k in p:
            torch.testing.assert_close(p[k], native[k], atol=1e-7, rtol=1e-5)
            torch.testing.assert_close(state[k][0], opt.state[native[k]]['exp_avg'], atol=1e-7, rtol=1e-5)


def test_causality_padding_and_cache():
    c = Config(max_seq_len=16)
    p = tb.load(c, initialize(c))
    x = torch.arange(16).reshape(1, 16)
    logits, _, _ = tb.forward(p, c, x)
    changed = x.clone(); changed[:, 8:] = 30
    torch.testing.assert_close(logits[:, :8], tb.forward(p, c, changed)[0][:, :8])
    cache, chunks = None, []
    for i in range(16):
        part, cache, _ = tb.forward(p, c, x[:, i:i+1], cache=cache)
        chunks.append(part)
    torch.testing.assert_close(logits, torch.cat(chunks, dim=1), atol=1e-6, rtol=1e-5)
    with pytest.raises(ValueError):
        tb.forward(p, c, x[:, :1], cache=cache)
    tokens = torch.tensor([[1, 2, 3, 0], [4, 5, 6, 7]])
    mask = torch.tensor([[True, True, True, False], [True]*4])
    padded = tb.forward(p, c, tokens, mask)[0]
    torch.testing.assert_close(padded[:1, :3], tb.forward(p, c, tokens[:1, :3])[0])


@pytest.mark.skipif(not torch.cuda.is_available(), reason='NVIDIA CUDA device unavailable')
def test_cuda_matches_cpu():
    torch.backends.cuda.matmul.allow_tf32 = False
    c, x = Config(), np.array([[1, 2, 3, 4]])
    w = initialize(c)
    cpu = tb.forward(tb.load(c, w), c, torch.tensor(x))[0]
    gpu = tb.forward(tb.load(c, w, 'cuda'), c, torch.tensor(x, device='cuda'))[0]
    torch.testing.assert_close(cpu, gpu.cpu(), atol=1e-5, rtol=1e-4)
