"""Versioned model-only checkpoints. Training-state migration is milestone two."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import numpy as np
from safetensors.numpy import load_file, save_file
from slm.common.config import Config, validate_weights


def save(path, config, weights):
    path = Path(path)
    validate_weights(config, weights)
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.checkpoint-', dir=path.parent))
    try:
        save_file({k: np.array(v, order='C', copy=True) for k, v in weights.items()},
                  str(temp/'model.safetensors'))
        metadata = {
            'schema_version': 1, 'architecture': config.to_dict(),
            'conventions': {'linear_layout': 'out_in', 'rope_pairing': 'adjacent',
                            'dtype': 'float32', 'output_weight': 'embedding'},
        }
        (temp/'config.json').write_text(json.dumps(metadata, indent=2)+'\n')
        hashes = {name: hashlib.sha256((temp/name).read_bytes()).hexdigest()
                  for name in ('config.json', 'model.safetensors')}
        (temp/'manifest.json').write_text(json.dumps(hashes, indent=2)+'\n')
        os.rename(temp, path)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def load(path):
    from slm.common.restart_guard import require_training_approval
    require_training_approval()
    path = Path(path)
    hashes = json.loads((path/'manifest.json').read_text())
    if set(hashes) != {'config.json', 'model.safetensors'}:
        raise ValueError('Invalid checkpoint manifest')
    for name, expected in hashes.items():
        if hashlib.sha256((path/name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Checksum mismatch: {name}')
    metadata = json.loads((path/'config.json').read_text())
    if metadata['schema_version'] != 1 or metadata['conventions'] != {
        'linear_layout': 'out_in', 'rope_pairing': 'adjacent',
        'dtype': 'float32', 'output_weight': 'embedding',
    }:
        raise ValueError('Unsupported checkpoint conventions')
    config = Config(**metadata['architecture'])
    weights = load_file(str(path/'model.safetensors'))
    validate_weights(config, weights)
    return config, weights
