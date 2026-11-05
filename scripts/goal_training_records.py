"""Explicitly distinguish chat supervision from opt-in causal replay."""
import numpy as np


def encode_training_row(tok, row, allow_replay=False):
    if row.get('objective') != 'causal_lm':
        from sft_common import encode_episode
        return encode_episode(tok, row['messages'])
    if not allow_replay:
        raise ValueError('Causal replay requires explicit opt-in')
    values = row.get('tokens')
    if not isinstance(values, list) or not 2 <= len(values) <= 513:
        raise ValueError('Replay must contain 2..513 existing token IDs')
    if any(type(v) is not int or not 0 <= v < 16384 for v in values):
        raise ValueError('Invalid replay token ID')
    if any(v in {2, 3, 4, 5, 6} for v in values):
        raise ValueError('Raw replay must not contain chat/tool role markers')
    n = len(values)
    ids = np.full(513, 1, np.int32)
    mask = np.zeros(512, np.float32)
    ids[:n] = values
    mask[:n - 1] = 1
    return ids, mask, n
