"""Unfused FP32 MLX reference, independently expressed from PyTorch."""
import math
import numpy as np
import mlx.core as mx
from slm.common.config import validate_weights

DEFAULT_LOSS_IMPLEMENTATION = 'legacy-logsumexp-minus-target-v1'
STABLE_LOSS_IMPLEMENTATION = 'max-centered-target-tail-softplus-v1'


def load(config, weights):
    validate_weights(config, weights)
    return {k: mx.array(weights[k]) for k in config.shapes()}


def export(params):
    mx.eval(params)
    # Canonical row-major buffers also preserve scalar shapes for serialization.
    return {k: np.array(v, order='C', copy=True) for k, v in params.items()}


def rope(x, positions, theta):
    d = x.shape[-1]
    inv = theta ** (-mx.arange(0, d, 2, dtype=mx.float32)/d)
    angle = positions[:, None]*inv[None, :]
    c, s = mx.cos(angle)[None, None], mx.sin(angle)[None, None]
    even, odd = x[..., ::2], x[..., 1::2]
    return mx.stack((even*c-odd*s, even*s+odd*c), axis=-1).reshape(x.shape)


def forward(p, c, tokens, padding_mask=None, cache=None, embedding_implementation='native-gather-v1'):
    b, t = tokens.shape
    offset = 0 if cache is None else cache[0][0].shape[2]
    if t == 0 or offset+t > c.max_seq_len:
        raise ValueError('Sequence outside context window')
    if cache is not None and padding_mask is not None:
        raise ValueError('Padded cache decoding is not supported')
    if cache is not None and len(cache) != c.num_layers:
        raise ValueError('Invalid cache layer count')
    if padding_mask is not None:
        if padding_mask.shape != tokens.shape or not bool(mx.all(padding_mask[:, 0])):
            raise ValueError('Each right-padded sequence must start with a valid token')
        if bool(mx.any(padding_mask[:, 1:] & ~padding_mask[:, :-1])):
            raise ValueError('Only right padding supported')
    positions = mx.arange(offset, offset+t, dtype=mx.float32)
    allowed = mx.arange(offset+t)[None, :] <= positions[:, None]
    allowed = allowed[None, None]
    if padding_mask is not None:
        allowed = allowed & padding_mask[:, None, None, :]
    if embedding_implementation == 'native-gather-v1':
        x = p['embedding'][tokens]
    elif embedding_implementation == 'dense-onehot-v1':
        x = (tokens[..., None] == mx.arange(c.vocab_size)).astype(p['embedding'].dtype) @ p['embedding']
    else:
        raise ValueError('Unknown embedding implementation')
    new_cache, traces = [], []
    def norm(z, w):
        return z*mx.rsqrt(mx.mean(mx.square(z), axis=-1, keepdims=True)+c.norm_eps)*w
    for i in range(c.num_layers):
        prefix = f'layers.{i}.'
        h = norm(x, p[prefix+'attn_norm'])
        def proj(name, heads):
            return (h @ p[prefix+name].T).reshape(b, t, heads, c.head_dim).transpose(0, 2, 1, 3)
        q = rope(proj('q', c.num_heads), positions, c.rope_theta)
        k = rope(proj('k', c.num_kv_heads), positions, c.rope_theta)
        v = proj('v', c.num_kv_heads)
        if cache is not None:
            k = mx.concatenate((cache[i][0], k), axis=2)
            v = mx.concatenate((cache[i][1], v), axis=2)
        new_cache.append((k, v))
        k = mx.repeat(k, c.num_heads//c.num_kv_heads, axis=1)
        v = mx.repeat(v, c.num_heads//c.num_kv_heads, axis=1)
        scores = q @ k.swapaxes(-1, -2)/math.sqrt(c.head_dim)
        probs = mx.softmax(mx.where(allowed, scores, -float('inf')), axis=-1)
        a = (probs @ v).transpose(0, 2, 1, 3).reshape(b, t, c.hidden_size)
        x = x+a @ p[prefix+'o'].T
        h = norm(x, p[prefix+'ffn_norm'])
        gate = h @ p[prefix+'gate'].T
        x = x+((gate*mx.sigmoid(gate))*(h @ p[prefix+'up'].T)) @ p[prefix+'down'].T
        traces.append(x)
    x = norm(x, p['final_norm'])
    return x @ p['embedding'].T, new_cache, traces


def cross_entropy_logits(logits, targets):
    """Equivalent centered softplus CE with an explicit target derivative."""
    selected = mx.take_along_axis(logits,targets[..., None],axis=-1).squeeze(-1)
    if logits.shape[-1] == 1:
        return selected*0
    center = mx.stop_gradient(mx.max(logits,axis=-1))
    shifted = logits-center[..., None]
    is_target = mx.arange(logits.shape[-1]) == targets[..., None]
    others = mx.where(is_target,-float('inf'),shifted)
    margin = mx.logsumexp(others,axis=-1)-(selected-center)
    # Margin first preserves its small gradient on the validated MLX runtime;
    # the symmetric argument order loses that gradient at high confidence.
    return mx.logaddexp(margin,mx.zeros_like(margin))


def loss(p, c, tokens, targets, mask, padding_mask=None, loss_implementation=DEFAULT_LOSS_IMPLEMENTATION, embedding_implementation='native-gather-v1'):
    if mask.shape != targets.shape or not bool(mx.all(mask >= 0)) or float(mx.sum(mask)) <= 0:
        raise ValueError('Loss requires nonnegative weights and supervised tokens')
    logits, _, _ = forward(p, c, tokens, padding_mask, embedding_implementation=embedding_implementation)
    if loss_implementation == DEFAULT_LOSS_IMPLEMENTATION:
        selected = mx.take_along_axis(logits,targets[...,None],axis=-1).squeeze(-1)
        per_token = mx.logsumexp(logits,axis=-1)-selected
    elif loss_implementation == STABLE_LOSS_IMPLEMENTATION:
        per_token = cross_entropy_logits(logits,targets)
    else:
        raise ValueError('Unknown loss implementation')
    return mx.sum(per_token*mask)/mx.sum(mask)


def value_and_grad(p, c, tokens, targets, mask, padding_mask=None, loss_implementation=DEFAULT_LOSS_IMPLEMENTATION, embedding_implementation='native-gather-v1'):
    value, grads = mx.value_and_grad(lambda w: loss(w, c, tokens, targets, mask, padding_mask,loss_implementation,embedding_implementation))(p)
    mx.eval(value, grads)
    return value, grads


def adamw(p, grads, state, step, lr, beta1=.9, beta2=.95, eps=1e-8, decay=.1, clip=1.):
    if step < 1:
        raise ValueError('step is 1-based')
    norm = mx.sqrt(sum(mx.sum(mx.square(g)) for g in grads.values()))
    factor = mx.minimum(clip/(norm+1e-6), 1.)
    out, moments = {}, {}
    for name, w in p.items():
        g = grads[name]*factor
        m, v = state.get(name, (mx.zeros_like(w), mx.zeros_like(w)))
        m = beta1*m+(1-beta1)*g
        v = beta2*v+(1-beta2)*mx.square(g)
        wd = decay if w.ndim == 2 and name != 'embedding' else 0.
        out[name] = w*(1-lr*wd)-lr*(m/(1-beta1**step))/(mx.sqrt(v/(1-beta2**step))+eps)
        moments[name] = (m, v)
    mx.eval(out, moments)
    return out, moments
