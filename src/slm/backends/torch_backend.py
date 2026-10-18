"""Unfused FP32 PyTorch reference. Flat parameters use canonical names."""
import math
import numpy as np
import torch
from slm.common.config import validate_weights


def load(config, weights, device='cpu'):
    validate_weights(config, weights)
    return {k: torch.tensor(v, device=device, requires_grad=True) for k, v in weights.items()}


def export(params):
    return {k: v.detach().cpu().numpy().copy() for k, v in params.items()}


def rope(x, positions, theta):
    d = x.shape[-1]
    inv = theta ** (-torch.arange(0, d, 2, device=x.device, dtype=torch.float32)/d)
    angle = positions[:, None]*inv[None, :]
    c, s = angle.cos()[None, None], angle.sin()[None, None]
    even, odd = x[..., ::2], x[..., 1::2]
    return torch.stack((even*c-odd*s, even*s+odd*c), dim=-1).flatten(-2)


def forward(p, c, tokens, padding_mask=None, cache=None):
    """Right-padding only. Cache is a list of (rotated K, V); no padded caching."""
    b, t = tokens.shape
    offset = 0 if cache is None else cache[0][0].shape[2]
    if t == 0 or offset+t > c.max_seq_len:
        raise ValueError('Sequence outside context window')
    if cache is not None and padding_mask is not None:
        raise ValueError('Padded cache decoding is not supported')
    if cache is not None and len(cache) != c.num_layers:
        raise ValueError('Invalid cache layer count')
    if padding_mask is not None:
        if padding_mask.shape != tokens.shape or not bool(padding_mask[:, 0].all()):
            raise ValueError('Each right-padded sequence must start with a valid token')
        if bool((padding_mask[:, 1:] & ~padding_mask[:, :-1]).any()):
            raise ValueError('Only right padding supported')
    device = tokens.device
    positions = torch.arange(offset, offset+t, device=device, dtype=torch.float32)
    allowed = torch.arange(offset+t, device=device)[None, :] <= positions[:, None]
    allowed = allowed[None, None]
    if padding_mask is not None:
        allowed = allowed & padding_mask[:, None, None, :]
    x = p['embedding'][tokens]
    new_cache, traces = [], []
    def norm(z, w):
        return z * torch.rsqrt(z.square().mean(-1, keepdim=True)+c.norm_eps)*w
    for i in range(c.num_layers):
        prefix = f'layers.{i}.'
        h = norm(x, p[prefix+'attn_norm'])
        def proj(name, heads):
            return (h @ p[prefix+name].T).reshape(b, t, heads, c.head_dim).transpose(1, 2)
        q = rope(proj('q', c.num_heads), positions, c.rope_theta)
        k = rope(proj('k', c.num_kv_heads), positions, c.rope_theta)
        v = proj('v', c.num_kv_heads)
        if cache is not None:
            k = torch.cat((cache[i][0], k), dim=2)
            v = torch.cat((cache[i][1], v), dim=2)
        new_cache.append((k, v))
        k = k.repeat_interleave(c.num_heads//c.num_kv_heads, dim=1)
        v = v.repeat_interleave(c.num_heads//c.num_kv_heads, dim=1)
        scores = q @ k.transpose(-1, -2) / math.sqrt(c.head_dim)
        probs = scores.masked_fill(~allowed, -float('inf')).softmax(-1)
        a = (probs @ v).transpose(1, 2).reshape(b, t, c.hidden_size)
        x = x + a @ p[prefix+'o'].T
        h = norm(x, p[prefix+'ffn_norm'])
        gate = h @ p[prefix+'gate'].T
        x = x + ((gate*torch.sigmoid(gate))*(h @ p[prefix+'up'].T)) @ p[prefix+'down'].T
        traces.append(x)
    x = norm(x, p['final_norm'])
    return x @ p['embedding'].T, new_cache, traces


def loss(p, c, tokens, targets, mask, padding_mask=None):
    if mask.shape != targets.shape or not bool((mask >= 0).all()) or float(mask.sum()) <= 0:
        raise ValueError('Loss requires nonnegative weights and supervised tokens')
    logits, _, _ = forward(p, c, tokens, padding_mask)
    per_token = torch.logsumexp(logits, -1)-logits.gather(-1, targets[..., None]).squeeze(-1)
    return (per_token*mask).sum()/mask.sum()


def value_and_grad(p, c, tokens, targets, mask, padding_mask=None):
    value = loss(p, c, tokens, targets, mask, padding_mask)
    grads = torch.autograd.grad(value, tuple(p.values()))
    return value, dict(zip(p, grads))


def adamw(p, grads, state, step, lr, beta1=.9, beta2=.95, eps=1e-8, decay=.1, clip=1.):
    """One update: caller supplies 1-based step; moments stay FP32."""
    if step < 1:
        raise ValueError('step is 1-based')
    norm = torch.sqrt(sum(g.square().sum() for g in grads.values()))
    factor = torch.clamp(clip/(norm+1e-6), max=1.)
    out, moments = {}, {}
    with torch.no_grad():
        for name, w in p.items():
            g = grads[name]*factor
            m, v = state.get(name, (torch.zeros_like(w), torch.zeros_like(w)))
            m = beta1*m+(1-beta1)*g
            v = beta2*v+(1-beta2)*g.square()
            wd = decay if w.ndim == 2 and name != 'embedding' else 0.
            updated = w*(1-lr*wd)-lr*(m/(1-beta1**step))/(torch.sqrt(v/(1-beta2**step))+eps)
            out[name] = updated.detach().requires_grad_(True)
            moments[name] = (m, v)
    return out, moments
