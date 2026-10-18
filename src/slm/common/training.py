"""Deterministic FP32 training and backend-neutral resume state."""
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import os
import platform
from importlib.metadata import version
import numpy as np
from safetensors.numpy import load_file, save_file
from slm.common import checkpoint


@dataclass(frozen=True)
class Recipe:
    lr: float = .001
    warmup_tokens: int = 100
    beta1: float = .9
    beta2: float = .95
    eps: float = 1e-8
    decay: float = .1
    clip: float = 1.
    loss_implementation: str = 'legacy-logsumexp-minus-target-v1'

    def __post_init__(self):
        if self.loss_implementation not in ('legacy-logsumexp-minus-target-v1','max-centered-target-tail-softplus-v1'):
            raise ValueError('Unknown loss implementation')
        if not all(np.isfinite(v) for k,v in asdict(self).items() if k != 'loss_implementation'):
            raise ValueError('Nonfinite optimizer setting')
        if self.lr <= 0 or self.eps <= 0 or self.clip <= 0 or self.decay < 0:
            raise ValueError('Invalid optimizer settings')
        if not 0 <= self.beta1 < 1 or not 0 <= self.beta2 < 1:
            raise ValueError('Invalid betas')
        if type(self.warmup_tokens) is not int or self.warmup_tokens < 0:
            raise ValueError('Invalid warmup')

    def rate(self, tokens_after_update):
        return self.lr * min(1., tokens_after_update/max(1, self.warmup_tokens))


def recipe_from_state(state):
    values = dict(state['recipe'])
    recorded = state.get('reproduction',{}).get('loss_implementation')
    if 'loss_implementation' in values and recorded is not None and values['loss_implementation'] != recorded:
        raise ValueError('Loss implementation metadata mismatch')
    if 'loss_implementation' not in values:
        values['loss_implementation'] = recorded or 'legacy-logsumexp-minus-target-v1'
    return Recipe(**values)


class Batches:
    """Immutable ordered fixtures. Cursor counts consumed batches; no hidden RNG."""
    def __init__(self, batches, vocab_size):
        self.items = []
        self.vocab_size = vocab_size
        digest = hashlib.sha256()
        for x, y, mask in batches:
            x, y, mask = np.asarray(x), np.asarray(y), np.asarray(mask)
            if x.ndim != 2 or x.shape != y.shape or x.shape != mask.shape or x.size == 0:
                raise ValueError('Invalid batch shapes')
            if x.dtype.kind not in 'iu' or y.dtype.kind not in 'iu':
                raise ValueError('Token IDs must be integers')
            if min(x.min(), y.min()) < 0 or max(x.max(), y.max()) >= vocab_size:
                raise ValueError('Token ID outside vocabulary')
            if not np.isfinite(mask).all() or not np.isin(mask, [0, 1]).all() or mask.sum() == 0:
                raise ValueError('Mask must contain supervised tokens and be binary')
            arrays = (x.astype(np.int64), y.astype(np.int64), mask.astype(np.float32))
            for a in arrays:
                digest.update(str((a.shape, a.dtype.str)).encode())
                digest.update(a.tobytes())
                a.flags.writeable = False
            self.items.append(arrays)
        if not self.items:
            raise ValueError('Empty dataset')
        self.fingerprint = digest.hexdigest()

    def counts(self, cursor):
        return (sum(x.size for x, _, _ in self.items[:cursor]),
                sum(int(m.sum()) for _, _, m in self.items[:cursor]))


class Trainer:
    def __init__(self, config, weights, batches, backend='torch', device='cpu',
                 recipe=None, tokenizer_hash='synthetic-token-ids-v1'):
        if getattr(batches,'vocab_size',config.vocab_size)!=config.vocab_size:
            raise ValueError('Dataset/model vocabulary mismatch')
        if getattr(batches,'max_length',0)>config.max_seq_len:
            raise ValueError('Dataset context exceeds model window')
        if getattr(batches,'tokenizer_hash',tokenizer_hash)!=tokenizer_hash:
            raise ValueError('Dataset/tokenizer mismatch')
        self.config, self.batches = config, batches
        self.recipe = recipe or Recipe()
        self.tokenizer_hash = tokenizer_hash
        self.backend, self.device = backend, device
        if backend == 'torch':
            import torch
            from slm.backends import torch_backend as impl
            self.array = lambda a: torch.tensor(np.array(a), device=device)
            self.params = impl.load(config, weights, device)
        elif backend == 'mlx':
            import mlx.core as mx
            from slm.backends import mlx_backend as impl
            self.array = mx.array
            self.params = impl.load(config, weights)
        else:
            raise ValueError('Unknown backend')
        self.impl = impl
        self.moments = {}
        self.cursor = self.step = self.tokens = self.supervised_tokens = 0

    def update(self):
        if self.cursor >= len(self.batches.items):
            raise StopIteration('Dataset exhausted; no implicit wraparound')
        x, y, mask = self.batches.items[self.cursor]
        value, grads = self.impl.value_and_grad(self.params, self.config,
                                              *(self.array(a) for a in (x, y, mask)),
                                              loss_implementation=self.recipe.loss_implementation)
        scalar = float(value.detach()) if self.backend == 'torch' else float(value)
        if not np.isfinite(scalar):
            raise FloatingPointError('Nonfinite loss')
        if not all(np.isfinite(a).all() for a in self.impl.export(grads).values()):
            raise FloatingPointError('Nonfinite gradients')
        rate = self.recipe.rate(self.tokens+x.size)
        settings = asdict(self.recipe)
        settings.pop('warmup_tokens'); settings.pop('loss_implementation'); settings['lr'] = rate
        params, moments = self.impl.adamw(self.params, grads, self.moments, self.step+1, **settings)
        if self.backend == 'mlx':
            import mlx.core as mx
            # Checkpoint loading produces contiguous tensors; match that layout at
            # every boundary so resumed and uninterrupted kernels see the same strides.
            params = {k: mx.contiguous(v) for k, v in params.items()}
            moments = {k: tuple(mx.contiguous(a) for a in v) for k, v in moments.items()}
            mx.eval(params, moments)
        self.params, self.moments = params, moments
        self.cursor += 1; self.step += 1
        self.tokens += x.size; self.supervised_tokens += int(mask.sum())
        return {'loss': float(value.detach()) if self.backend == 'torch' else float(value),
                'lr': rate, 'step': self.step, 'tokens': self.tokens}

    def save(self, destination):
        destination = Path(destination)
        if destination.exists():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = Path(tempfile.mkdtemp(prefix='.training-', dir=destination.parent))
        try:
            checkpoint.save(temp/'model', self.config, self.impl.export(self.params))
            raw = {f'{slot}:{k}': v[i] for k, v in self.moments.items()
                   for i, slot in enumerate(('m', 'v'))}
            save_file(self.impl.export(raw), str(temp/'optimizer.safetensors'))
            state = {'version': 1, 'step': self.step, 'cursor': self.cursor,
                     'tokens': self.tokens, 'supervised_tokens': self.supervised_tokens,
                     'recipe': asdict(self.recipe), 'dataset_hash': self.batches.fingerprint,
                     'tokenizer_hash': self.tokenizer_hash, 'source_backend': self.backend,
                     'reproduction': {'python': platform.python_version(),
                                      'platform': platform.platform(),
                                      'backend_version': version('torch' if self.backend == 'torch' else 'mlx'),
                                      'numpy_version': np.__version__,
                                      'loss_implementation': self.recipe.loss_implementation,
                                      'implementation_sha256': hashlib.sha256(Path(self.impl.__file__).read_bytes()).hexdigest()},
                     'precision': 'fp32', 'rng_policy': 'precomputed-order-no-stochastic-ops',
                     'schedule': 'linear-warmup-then-constant-tokens-after-update'}
            (temp/'state.json').write_text(json.dumps(state, indent=2)+'\n')
            hashes = {str(p.relative_to(temp)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in temp.rglob('*') if p.is_file()}
            (temp/'manifest.json').write_text(json.dumps(hashes, indent=2)+'\n')
            for p in temp.rglob('*'):
                if p.is_file():
                    with p.open('rb') as handle:
                        os.fsync(handle.fileno())
            os.rename(temp, destination)
        except BaseException:
            shutil.rmtree(temp, ignore_errors=True)
            raise

    @classmethod
    def resume(cls, path, batches, backend='torch', device='cpu', tokenizer_hash='synthetic-token-ids-v1'):
        path = Path(path)
        hashes = json.loads((path/'manifest.json').read_text())
        expected = {'model/config.json', 'model/model.safetensors', 'model/manifest.json',
                    'optimizer.safetensors', 'state.json'}
        if set(hashes) != expected:
            raise ValueError('Invalid training manifest')
        for name, digest in hashes.items():
            if hashlib.sha256((path/name).read_bytes()).hexdigest() != digest:
                raise ValueError(f'Checksum mismatch: {name}')
        state = json.loads((path/'state.json').read_text())
        if state['version'] != 1 or state['precision'] != 'fp32':
            raise ValueError('Unsupported training state')
        if state['schedule'] != 'linear-warmup-then-constant-tokens-after-update':
            raise ValueError('Unsupported schedule')
        if state['dataset_hash'] != batches.fingerprint or state['tokenizer_hash'] != tokenizer_hash:
            raise ValueError('Dataset/tokenizer mismatch')
        for name in ('step', 'cursor', 'tokens', 'supervised_tokens'):
            if type(state[name]) is not int or state[name] < 0:
                raise ValueError('Invalid training counters')
        cursor = state['cursor']
        if cursor != state['step'] or cursor > len(batches.items) or batches.counts(cursor) != (state['tokens'], state['supervised_tokens']):
            raise ValueError('Inconsistent data cursor/counters')
        config, weights = checkpoint.load(path/'model')
        trainer = cls(config, weights, batches, backend, device, recipe_from_state(state), tokenizer_hash)
        raw = load_file(str(path/'optimizer.safetensors'))
        keys = {f'{s}:{k}' for k in weights for s in ('m', 'v')} if state['step'] else set()
        if raw.keys() != keys:
            raise ValueError('Incomplete optimizer state')
        for name, tensor in raw.items():
            k = name.split(':', 1)[1]
            if tensor.shape != weights[k].shape or tensor.dtype != np.float32 or not np.isfinite(tensor).all():
                raise ValueError('Invalid optimizer tensor')
            if name.startswith('v:') and (tensor < 0).any():
                raise ValueError('Negative second moment')
        trainer.moments = {k: (trainer.array(raw[f'm:{k}']), trainer.array(raw[f'v:{k}']))
                           for k in weights} if state['step'] else {}
        trainer.step, trainer.cursor = state['step'], cursor
        trainer.tokens, trainer.supervised_tokens = state['tokens'], state['supervised_tokens']
        return trainer
