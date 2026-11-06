"""Bare-MLX CPU feasibility port of our GPT-2; no model downloads or training driver.

Flat parameter names and shapes match gpt2.py exactly, including the tied output
projection. This diagnostic deliberately refuses GPU execution.
"""
from dataclasses import dataclass
import math

import mlx.core as mx
import mlx.optimizers as optim


@dataclass(frozen=True)
class Config:
    vocabulary: int = 50257
    context: int = 1024
    width: int = 768
    heads: int = 12
    depth: int = 12


def cpu_only():
    if mx.default_device() != mx.cpu:
        raise ValueError('feasibility implementation is CPU-only; set default device to mx.cpu first')


def parameter_shapes(config=Config()):
    if config.width % config.heads:
        raise ValueError('heads must divide width')
    w = config.width
    shapes = {'tokens.weight': (config.vocabulary, w), 'positions.weight': (config.context, w),
              'final_norm.weight': (w,), 'final_norm.bias': (w,)}
    for i in range(config.depth):
        prefix = f'blocks.{i}.'
        for norm in ('before_attention', 'before_mlp'):
            shapes[prefix + norm + '.weight'] = (w,)
            shapes[prefix + norm + '.bias'] = (w,)
        for name, n_in, n_out in [('qkv', w, 3*w), ('attention_out', w, w),
                                    ('mlp.0', w, 4*w), ('mlp.2', 4*w, w)]:
            shapes[prefix + name + '.weight'] = (n_out, n_in)
            shapes[prefix + name + '.bias'] = (n_out,)
    return shapes


def parameter_count(config=Config()):
    return sum(math.prod(shape) for shape in parameter_shapes(config).values())


def from_numpy(arrays, config):
    cpu_only()
    shapes = parameter_shapes(config)
    if set(arrays) != set(shapes):
        raise ValueError('parameter keys differ from GPT-2 architecture')
    for name, shape in shapes.items():
        if tuple(arrays[name].shape) != shape or str(arrays[name].dtype) != 'float32':
            raise ValueError(f'wrong parameter shape or dtype: {name}')
    return {name: mx.array(value, dtype=mx.float32) for name, value in arrays.items()}


def linear(x, params, name):
    return x @ params[name + '.weight'].T + params[name + '.bias']


def norm(x, params, name):
    # Same affine LayerNorm and epsilon as torch.nn.LayerNorm default.
    return mx.fast.layer_norm(x, params[name + '.weight'], params[name + '.bias'], 1e-5, stream=mx.cpu)


def forward(params, token_ids, config):
    cpu_only()
    batch, length = token_ids.shape
    if not 0 < length <= config.context:
        raise ValueError('sequence length outside configured context')
    hidden = params['tokens.weight'][token_ids] + params['positions.weight'][mx.arange(length)]
    for i in range(config.depth):
        prefix = f'blocks.{i}.'
        projected = linear(norm(hidden, params, prefix + 'before_attention'), params, prefix + 'qkv')
        heads = projected.reshape(batch, length, 3, config.heads, config.width // config.heads)
        heads = heads.transpose(2, 0, 3, 1, 4)
        query, key, value = heads[0], heads[1], heads[2]
        attention = mx.fast.scaled_dot_product_attention(
            query, key, value, scale=(config.width // config.heads)**-.5, mask='causal', stream=mx.cpu)
        hidden = hidden + linear(attention.transpose(0, 2, 1, 3).reshape(hidden.shape), params, prefix + 'attention_out')
        x = linear(norm(hidden, params, prefix + 'before_mlp'), params, prefix + 'mlp.0')
        # Exact tanh approximation used by the original torch.nn.GELU(approximate='tanh').
        x = .5 * x * (1 + mx.tanh(math.sqrt(2 / math.pi) * (x + .044715 * x**3)))
        hidden = hidden + linear(x, params, prefix + 'mlp.2')
    return norm(hidden, params, 'final_norm') @ params['tokens.weight'].T


def causal_loss(params, sequence, config):
    logits = forward(params, sequence[:, :-1], config)
    targets = sequence[:, 1:]
    chosen = mx.take_along_axis(logits, targets[..., None], axis=-1).squeeze(-1)
    return mx.mean(mx.logsumexp(logits, axis=-1) - chosen)


def clip_gradients(grads, maximum=1.):
    cpu_only()
    # Torch clip_grad_norm_ uses max_norm/(total_norm+1e-6), clamped to1.
    total = mx.sqrt(sum(mx.sum(g * g) for g in grads.values()))
    scale = mx.minimum(mx.array(1., dtype=mx.float32), maximum / (total + 1e-6))
    return {name: grad * scale for name, grad in grads.items()}, total


class AdamW:
    """Two native MLX AdamW groups matching train.optimizer_for, with bias correction."""
    def __init__(self, learning_rate=3e-4):
        cpu_only()
        self.groups = [optim.AdamW(learning_rate=learning_rate, betas=(.9, .95), eps=1e-8,
                                  weight_decay=decay, bias_correction=True) for decay in (.1, 0.)]

    def update(self, params, grads):
        cpu_only()
        output = {}
        for index, optimizer in enumerate(self.groups):
            group = {name: value for name, value in params.items() if (value.ndim >= 2) == (index == 0)}
            output.update(optimizer.apply_gradients({name: grads[name] for name in group}, group))
        return output

    @property
    def state(self):
        return [optimizer.state for optimizer in self.groups]
