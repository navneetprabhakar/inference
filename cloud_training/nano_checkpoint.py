"""Immutable, verified single-writer checkpoints for own-base training.

A bundle is publishable only after COMMITTED exists. For GCS, upload payload.pt,
metadata.json and manifest.json first, verify their remote hashes, then upload
COMMITTED last. Download into a staging directory and call validate_bundle before
restoring. Hashes detect corruption, not malicious replacement: accept only our
trusted, access-controlled bucket. This module does not itself upload to GCS.

Call only at a completed optimizer-update boundary. The caller must serialize the
*next* batch position, packing/prefetch buffers, and any private data generators.
An upstream parquet row-group cursor alone is NOT an exact data state.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import struct
import tempfile

import torch

VERSION = 1
FILES = ('payload.pt', 'metadata.json')


def _sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _json_write(path, value):
    with path.open('w', encoding='utf8') as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def _cpu(value):
    if isinstance(value, torch.Tensor):
        return value.detach().cpu()
    if isinstance(value, dict):
        return {k: _cpu(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_cpu(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_cpu(v) for v in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f'Unsupported checkpoint state type: {type(value).__name__}')


def capture_rng():
    state = {'python': random.getstate(), 'torch_cpu': torch.get_rng_state(),
             'torch_cuda': torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else None,
             'numpy': None}
    try:
        import numpy as np
        rng = np.random.get_state()
        state['numpy'] = (rng[0], rng[1].tolist(), *rng[2:])
    except ImportError:
        pass
    return state


def restore_rng_state(state):
    cuda = state['torch_cuda']
    if cuda is not None:
        if not torch.cuda.is_available() or len(cuda) != torch.cuda.device_count():
            raise ValueError('Exact CUDA RNG restore requires matching device count')
        torch.cuda.set_rng_state_all(cuda)
    random.setstate(state['python'])
    torch.set_rng_state(state['torch_cpu'])
    if state['numpy'] is not None:
        import numpy as np
        rng = state['numpy']
        np.random.set_state((rng[0], np.asarray(rng[1], dtype=np.uint32), *rng[2:]))


def _check_metadata(metadata):
    if not isinstance(metadata, dict):
        raise ValueError('metadata must be a dict')
    if type(metadata.get('step')) is not int or metadata['step'] < 0:
        raise ValueError('metadata.step must count completed updates')
    if not isinstance(metadata.get('identity'), dict) or not metadata['identity']:
        raise ValueError('metadata.identity must bind code/model/data configuration')
    json.dumps(metadata, allow_nan=False)


def _check_data(data_state):
    if not isinstance(data_state, dict) or data_state.get('exact') is not True:
        raise ValueError('data_state must explicitly certify exact=True')
    if 'next_batch' not in data_state:
        raise ValueError('data_state.next_batch must identify the next unread batch')


def save_bundle(path, *, model, optimizer, metadata, data_state, scheduler=None):
    """Save synchronous CPU-portable state at a completed update boundary.

    metadata requires step and a nonempty identity dict. data_state requires
    exact=True and next_batch, plus caller-specific buffer/generator state.
    Destination is immutable; choose a new directory for every snapshot.
    """
    path = Path(path).absolute()
    _check_metadata(metadata)
    _check_data(data_state)
    if optimizer is None:
        raise ValueError('Training recovery requires optimizer state')
    path.parent.mkdir(parents=True, exist_ok=True)
    with (path.parent / ('.' + path.name + '.lock')).open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            raise FileExistsError(path)
        stage = Path(tempfile.mkdtemp(prefix='.' + path.name + '.partial-', dir=path.parent))
        try:
            payload = _cpu({'model': model.state_dict(), 'optimizer': optimizer.state_dict(),
                            'scheduler': scheduler.state_dict() if scheduler is not None else None,
                            'rng': capture_rng(), 'data_state': data_state})
            with (stage / 'payload.pt').open('wb') as handle:
                torch.save(payload, handle)
                handle.flush()
                os.fsync(handle.fileno())
            _json_write(stage / 'metadata.json', metadata)
            manifest = {'version': VERSION, 'step': metadata['step'], 'files': {
                name: {'sha256': _sha(stage / name), 'bytes': (stage / name).stat().st_size}
                for name in FILES}}
            _json_write(stage / 'manifest.json', manifest)
            _json_write(stage / 'COMMITTED', {'version': VERSION,
                                             'manifest_sha256': _sha(stage / 'manifest.json')})
            validate_bundle(stage)
            _fsync_dir(stage)
            os.rename(stage, path)
            _fsync_dir(path.parent)
            return manifest
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def validate_bundle(path):
    """Validate the complete bundle before deserializing or mutating a model."""
    path = Path(path)
    for name in (*FILES, 'manifest.json', 'COMMITTED'):
        if not (path / name).is_file() or (path / name).is_symlink():
            raise ValueError(f'Missing or invalid checkpoint component: {name}')
    marker = json.loads((path / 'COMMITTED').read_text())
    if marker.get('version') != VERSION or marker.get('manifest_sha256') != _sha(path / 'manifest.json'):
        raise ValueError('Uncommitted or corrupt checkpoint manifest')
    manifest = json.loads((path / 'manifest.json').read_text())
    if manifest.get('version') != VERSION or set(manifest.get('files', {})) != set(FILES):
        raise ValueError('Unsupported checkpoint manifest')
    for name, item in manifest['files'].items():
        if (path / name).stat().st_size != item['bytes'] or _sha(path / name) != item['sha256']:
            raise ValueError(f'Corrupt checkpoint component: {name}')
    metadata = json.loads((path / 'metadata.json').read_text())
    _check_metadata(metadata)
    if metadata['step'] != manifest.get('step'):
        raise ValueError('Checkpoint step mismatch')
    return manifest


def _exact_fingerprint(value):
    """Typed recursive byte fingerprints; at most one tensor CPU copy at a time.

    Capture BEFORE load_state_dict: CPU optimizer loads may alias payload tensors,
    so comparing the mutated payload afterward would miss in-place corruption.
    Device and strides are intentionally excluded for CPU-portable recovery.
    """
    if isinstance(value, torch.Tensor):
        if value.layout != torch.strided:
            raise ValueError('Exact restore verification requires dense strided tensors')
        raw = value.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy()
        digest = hashlib.sha256(memoryview(raw)).hexdigest()
        return ('tensor', str(value.dtype), tuple(value.shape), digest)
    if isinstance(value, dict):
        return ('dict', {k: _exact_fingerprint(v) for k,v in value.items()})
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, tuple(_exact_fingerprint(v) for v in value))
    if type(value) is float:
        return ('float', struct.pack('>d',value))
    if value is None or type(value) in (str,int,bool):
        return (type(value).__name__,value)
    raise TypeError(f'Unsupported exact state type: {type(value).__name__}')


def _verify_exact(expected, actual, component):
    if expected != _exact_fingerprint(actual):
        raise ValueError(f'Post-load exact state verification failed: {component}')


def load_bundle(path, *, model, optimizer, scheduler=None, restore_rng=True, expected_identity=None):
    """Restore a validated bundle; returns exact caller-owned data state.

    Build the same uncompiled model/optimizer first. Identity comparison is exact
    when supplied. Set restore_rng=False only for evaluation, not resumed training.
    The caller restores returned private data-generator/buffer state before reading.
    """
    path = Path(path)
    manifest = validate_bundle(path)
    metadata = json.loads((path / 'metadata.json').read_text())
    if expected_identity is not None and metadata['identity'] != expected_identity:
        raise ValueError('Checkpoint identity differs from requested run')
    payload = torch.load(path / 'payload.pt', map_location='cpu', weights_only=True)
    _check_data(payload['data_state'])
    if (payload['scheduler'] is None) != (scheduler is None):
        raise ValueError('Scheduler presence differs from saved checkpoint')
    if optimizer is None:
        raise ValueError('Training recovery requires optimizer state')
    if restore_rng and payload['rng']['torch_cuda'] is not None:
        if not torch.cuda.is_available() or len(payload['rng']['torch_cuda']) != torch.cuda.device_count():
            raise ValueError('Exact CUDA RNG restore requires matching device count')
    expected = {key: _exact_fingerprint(payload[key]) for key in ('model','optimizer','scheduler','rng')}
    model.load_state_dict(payload['model'], strict=True)
    optimizer.load_state_dict(payload['optimizer'])
    if scheduler is not None:
        scheduler.load_state_dict(payload['scheduler'])
    if restore_rng:
        restore_rng_state(payload['rng'])
    _verify_exact(expected['model'], model.state_dict(), 'model')
    _verify_exact(expected['optimizer'], optimizer.state_dict(), 'optimizer')
    _verify_exact(expected['scheduler'], scheduler.state_dict() if scheduler is not None else None, 'scheduler')
    if restore_rng:
        _verify_exact(expected['rng'], capture_rng(), 'rng')
    verification = {'exact_state_verified': True, 'model': True, 'optimizer': True,
                    'scheduler': scheduler is not None, 'rng': bool(restore_rng),
                    'method': 'recursive typed SHA256 of exact tensor bytes and scalar metadata'}
    return {'metadata': metadata, 'data_state': payload['data_state'], 'manifest': manifest,
            'verification': verification}
