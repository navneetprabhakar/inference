"""Tiny CPU feasibility checkpoint bridge. Not a production campaign migrator."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(meta, arrays, expected_identity):
    if meta.get('experiment') != expected_identity or meta.get('schema') != 1:
        raise ValueError('experiment identity/schema mismatch')
    if meta.get('lineage') != 'own-random-tiny-fixture; no live checkpoint':
        raise ValueError('unexpected fixture lineage')
    cursor = meta['cursor']
    step = cursor['step']
    effective = meta['effective_tokens']
    if (type(step) is not int or step < 1 or type(effective) is not int or effective <= 0
            or cursor['offset'] != step*effective or cursor['trained_tokens'] != step*effective):
        raise ValueError('optimizer/cursor mismatch')
    optimizer = meta['optimizer']
    if (optimizer['betas'] != [.9, .95] or optimizer['eps'] != 1e-8
            or optimizer['decay'] != [.1, 0.] or optimizer['bias_correction'] is not True
            or not np.isfinite(optimizer['learning_rate']) or optimizer['learning_rate'] <= 0):
        raise ValueError('optimizer configuration mismatch')
    names = meta['parameter_order']
    if len(names) != len(set(names)) or set(names) != set(meta['shapes']):
        raise ValueError('parameter inventory mismatch')
    required = {kind+'::'+name for name in names for kind in ('weight', 'm', 'v')}
    required |= {'group_lr::0', 'group_lr::1', 'group_step::0', 'group_step::1', 'torch_rng', 'mlx_key'}
    if set(arrays) != required:
        raise ValueError('missing or extra checkpoint state')
    for name in names:
        shape = tuple(meta['shapes'][name])
        for kind in ('weight', 'm', 'v'):
            value = arrays[kind+'::'+name]
            if value.shape != shape or value.dtype != np.float32 or not np.isfinite(value).all():
                raise ValueError('invalid parameter/moment tensor')
        if (arrays['v::'+name] < 0).any():
            raise ValueError('negative second moment')
    for group in (0, 1):
        value = arrays[f'group_step::{group}']
        lr = arrays[f'group_lr::{group}']
        if value.shape != () or value.dtype != np.uint64 or int(value) != step:
            raise ValueError('group optimizer step mismatch')
        if lr.shape != () or lr.dtype != np.float32 or lr != np.float32(optimizer['learning_rate']):
            raise ValueError('group learning rate mismatch')
    if arrays['mlx_key'].dtype != np.uint32 or arrays['mlx_key'].shape != (2,):
        raise ValueError('invalid explicit MLX PRNG key')
    if arrays['torch_rng'].dtype != np.uint8 or arrays['torch_rng'].ndim != 1 or arrays['torch_rng'].size == 0:
        raise ValueError('invalid preserved Torch RNG state')


def write_bundle(directory, meta, arrays):
    validate(meta, arrays, meta['experiment'])
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    path = directory/'state.npz'
    np.savez(path, **arrays)
    receipt = dict(metadata=meta, data_file='state.npz', data_bytes=path.stat().st_size, data_sha256=sha(path))
    receipt['sha256'] = hashlib.sha256(canonical(receipt)).hexdigest()
    (directory/'receipt.json').write_bytes(canonical(receipt)+b'\n')


def read_bundle(directory, expected_identity):
    directory = Path(directory)
    receipt = json.loads((directory/'receipt.json').read_bytes())
    signature = receipt.pop('sha256')
    if signature != hashlib.sha256(canonical(receipt)).hexdigest():
        raise ValueError('receipt checksum mismatch')
    if receipt['data_file'] != 'state.npz':
        raise ValueError('unexpected checkpoint filename')
    path = directory/'state.npz'
    if path.is_symlink() or path.stat().st_size != receipt['data_bytes'] or sha(path) != receipt['data_sha256']:
        raise ValueError('checkpoint bytes/checksum mismatch')
    with np.load(path, allow_pickle=False) as saved:
        arrays = {name: saved[name] for name in saved.files}
    meta = receipt['metadata']
    validate(meta, arrays, expected_identity)
    return meta, arrays


def from_torch(model, optimizer, *, step, effective_tokens, experiment, config, rng_state, seed):
    """Export by parameter object/name, never by guessed optimizer integer IDs."""
    named = dict(model.named_parameters())
    groups = optimizer.param_groups
    if len(groups) != 2:
        raise ValueError('expected matrix and nonmatrix AdamW groups')
    for index, group in enumerate(groups):
        expected = {id(p) for p in named.values() if (p.ndim >= 2) == (index == 0)}
        if ({id(p) for p in group['params']} != expected or group['weight_decay'] != (.1, 0.)[index]
                or tuple(group['betas']) != (.9, .95) or group['eps'] != 1e-8
                or group.get('amsgrad', False) or group.get('maximize', False)):
            raise ValueError('Torch optimizer grouping/hyperparameters mismatch')
    if groups[0]['lr'] != groups[1]['lr']:
        raise ValueError('learning rate differs across groups')
    arrays = {}
    for name, parameter in named.items():
        state = optimizer.state[parameter]
        if parameter.device.type != 'cpu' or float(state['step']) != step:
            raise ValueError('non-CPU tensor or inconsistent per-parameter step')
        for kind, tensor in [('weight', parameter), ('m', state['exp_avg']), ('v', state['exp_avg_sq'])]:
            arrays[kind+'::'+name] = tensor.detach().cpu().numpy().copy()
    for group in (0, 1):
        arrays[f'group_step::{group}'] = np.array(step, dtype=np.uint64)
        arrays[f'group_lr::{group}'] = np.array(groups[group]['lr'], dtype=np.float32)
    arrays['torch_rng'] = rng_state.numpy().copy()
    # MLX's explicit key encoding starts with [0,seed]. This is a newly assigned
    # target-runtime stream, NOT a conversion of Torch's different PRNG algorithm.
    arrays['mlx_key'] = np.array([0, seed], dtype=np.uint32)
    meta = dict(schema=1, experiment=experiment, config=asdict(config),
                lineage='own-random-tiny-fixture; no live checkpoint', source='torch',
                effective_tokens=effective_tokens,
                cursor=dict(step=step, offset=step*effective_tokens, trained_tokens=step*effective_tokens),
                optimizer=dict(betas=[.9, .95], eps=1e-8, decay=[.1, 0.], bias_correction=True, learning_rate=groups[0]['lr']),
                parameter_order=list(named), shapes={name:list(p.shape) for name,p in named.items()},
                rng_policy='Torch state preserved opaquely; new explicit MLX stream assigned; no cross-framework random-stream equivalence')
    validate(meta, arrays, experiment)
    return meta, arrays


def to_mlx(meta, arrays, expected_identity):
    import mlx.core as mx
    import mlx_base as own
    own.cpu_only()
    validate(meta, arrays, expected_identity)
    cfg = own.Config(**meta['config'])
    if {k:tuple(v) for k,v in meta['shapes'].items()} != own.parameter_shapes(cfg):
        raise ValueError('model architecture shape mismatch')
    params = own.from_numpy({name:arrays['weight::'+name] for name in meta['parameter_order']}, cfg)
    optimizer = own.AdamW(meta['optimizer']['learning_rate'])
    for group, native in enumerate(optimizer.groups):
        state = dict(step=mx.array(arrays[f'group_step::{group}']), learning_rate=mx.array(arrays[f'group_lr::{group}']))
        for name, p in params.items():
            if (p.ndim >= 2) == (group == 0):
                state[name] = dict(m=mx.array(arrays['m::'+name]), v=mx.array(arrays['v::'+name]))
        native.state = state
    return params, optimizer, mx.array(arrays['mlx_key']), dict(meta['cursor']), cfg


def from_mlx(params, optimizer, key, cursor, source_meta, source_arrays):
    import mlx.core as mx
    import mlx_base as own
    own.cpu_only()
    mx.eval(params, optimizer.state, key)
    meta = dict(source_meta, source='mlx-resume', cursor=dict(cursor), parameter_order=list(params))
    arrays = {'torch_rng':source_arrays['torch_rng'].copy(), 'mlx_key':np.array(key)}
    for name, p in params.items():
        state = optimizer.groups[0 if p.ndim >= 2 else 1].state[name]
        arrays['weight::'+name] = np.array(p)
        arrays['m::'+name] = np.array(state['m'])
        arrays['v::'+name] = np.array(state['v'])
    for group, native in enumerate(optimizer.groups):
        arrays[f'group_step::{group}'] = np.array(native.step)
        arrays[f'group_lr::{group}'] = np.array(native.learning_rate)
    validate(meta, arrays, meta['experiment'])
    return meta, arrays
