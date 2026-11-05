"""Accumulate gradients of token-mean losses into a token-weighted mean."""
import mlx.core as mx
from mlx.utils import tree_map

def add_weighted(total, gradient, target_tokens):
    if target_tokens <= 0:
        raise ValueError('A microbatch must contain supervised tokens')
    weighted = tree_map(lambda x: x.astype(mx.float32) * target_tokens, gradient)
    return weighted if total is None else tree_map(lambda a, b: a + b, total, weighted)

def mean_gradient(total, target_tokens):
    if total is None or target_tokens <= 0:
        raise ValueError('Cannot average an empty gradient accumulation')
    return tree_map(lambda x: x / target_tokens, total)
