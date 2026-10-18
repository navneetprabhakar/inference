"""Portable cross-host training fixtures. No cloud provisioning or credentials."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
from importlib.metadata import version
import numpy as np
from safetensors.numpy import load_file, save_file
from slm.common.config import Config, initialize
from slm.common.training import Batches, Trainer


def environment(backend, device):
    info = {'backend': backend, 'platform': platform.platform(), 'python': platform.python_version()}
    if backend == 'torch':
        import torch
        requested = torch.device(device)
        if requested.type not in ('cpu', 'cuda'):
            raise ValueError('Verification supports PyTorch CPU or CUDA only')
        if requested.type == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('CUDA requested but unavailable; no CPU fallback')
        if requested.type == 'cuda':
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
        info.update(device=str(requested), version=version('torch'),
                    cuda_runtime=torch.version.cuda,
                    hardware=torch.cuda.get_device_name(requested) if requested.type == 'cuda' else platform.machine())
    else:
        import mlx.core as mx
        info.update(device=str(mx.default_device()), version=version('mlx'), hardware=platform.machine())
    return info


def write_manifest(root):
    files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in root.rglob('*') if p.is_file() and p != root/'bundle.json'}
    (root/'bundle.json').write_text(json.dumps({'version': 1, 'files': files}, indent=2)+'\n')


def validate_bundle(root):
    root = Path(root)
    manifest = json.loads((root/'bundle.json').read_text())
    if manifest['version'] != 1:
        raise ValueError('Unknown fixture version')
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p != root/'bundle.json'}
    if set(manifest['files']) != actual:
        raise ValueError('Fixture files missing or unexpected')
    for name, digest in manifest['files'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Fixture checksum mismatch: {name}')
    return hashlib.sha256((root/'bundle.json').read_bytes()).hexdigest()


def get_batches(root):
    with np.load(Path(root)/'batches.npz', allow_pickle=False) as raw:
        return Batches([(raw[f'x{i}'], raw[f'y{i}'], raw[f'mask{i}']) for i in range(6)], 64)


def capture(trainer):
    """Probe one fixed batch independently of the next training batch."""
    x, y, mask = trainer.batches.items[0]
    a = trainer.array
    logits, _, layers = trainer.impl.forward(trainer.params, trainer.config, a(x))
    loss, grads = trainer.impl.value_and_grad(trainer.params, trainer.config, a(x), a(y), a(mask))
    tensors = {'logits': logits, 'loss': loss}
    tensors.update({f'layer:{i}': v for i, v in enumerate(layers)})
    tensors.update({f'gradient:{k}': v for k, v in grads.items()})
    tensors.update({f'weight:{k}': v for k, v in trainer.params.items()})
    for k, moments in trainer.moments.items():
        tensors[f'moment_m:{k}'], tensors[f'moment_v:{k}'] = moments
    # Probe chunked cached decoding against the full forward pass.
    _, cache, _ = trainer.impl.forward(trainer.params, trainer.config, a(x[:, :2]))
    cached, _, _ = trainer.impl.forward(trainer.params, trainer.config, a(x[:, 2:]), cache=cache)
    tensors['cached_logits'] = cached
    raw = trainer.impl.export(tensors)
    np.testing.assert_allclose(raw['cached_logits'], raw['logits'][:, 2:], atol=1e-5, rtol=1e-4)
    return raw


def compare(actual, expected):
    if actual.keys() != expected.keys():
        raise ValueError('Probe tensor keys differ')
    metrics = {}
    for name in actual:
        a, e = actual[name], expected[name]
        if a.shape != e.shape or not np.isfinite(a).all() or not np.isfinite(e).all():
            raise ValueError(f'Invalid probe tensor: {name}')
        # Use the already-established prototype bounds; no caller tolerance override.
        atol = 1e-6 if name.startswith(('gradient:', 'moment_')) else 1e-5
        delta = np.abs(a-e)
        metrics[name] = {'max_abs_error': float(delta.max()), 'mean_abs_error': float(delta.mean()),
                         'atol': atol, 'rtol': 1e-4}
        np.testing.assert_allclose(a, e, atol=atol, rtol=1e-4, err_msg=name)
    return metrics


def create(destination, backend='mlx', device='cpu'):
    env = environment(backend, device)
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(91)
    arrays = {}
    for i, length in enumerate((6, 8, 5, 9, 4, 7)):
        arrays[f'x{i}'] = rng.integers(0, 64, (2, length), dtype=np.int64)
        arrays[f'y{i}'] = rng.integers(0, 64, (2, length), dtype=np.int64)
        arrays[f'mask{i}'] = rng.integers(0, 2, (2, length)).astype(np.float32)
        arrays[f'mask{i}'][:, 0] = 1
    np.savez(root/'batches.npz', **arrays)
    trainer = Trainer(Config(), initialize(Config()), get_batches(root), backend, device)
    for _ in range(2): trainer.update()
    trainer.save(root/'initial')
    for step in (2, 4, 6):
        while trainer.step < step: trainer.update()
        save_file(capture(trainer), str(root/f'expected-{step}.safetensors'))
    (root/'origin.json').write_text(json.dumps(env, indent=2)+'\n')
    write_manifest(root)
    return {'bundle': str(root), 'bundle_hash': validate_bundle(root), 'origin': env}


def verify(bundle, output, backend='torch', device='cpu', resume=None):
    env = environment(backend, device)
    bundle, output = Path(bundle), Path(output)
    digest = validate_bundle(bundle)
    output.mkdir(parents=True, exist_ok=False)
    report = {'passed': False, 'bundle_hash': digest, 'origin': json.loads((bundle/'origin.json').read_text()),
              'destination': env, 'checks': {}}
    try:
        trainer = Trainer.resume(resume or bundle/'initial', get_batches(bundle), backend, device)
        start = trainer.step
        if start not in (2, 4):
            raise ValueError('Fixture continuation must begin at update 2 or 4')
        for step in (start, start+2):
            while trainer.step < step: trainer.update()
            report['checks'][str(step)] = compare(capture(trainer), load_file(str(bundle/f'expected-{step}.safetensors')))
        trainer.save(output/'checkpoint')
        report.update(passed=True, start_step=start, final_step=trainer.step,
                      processed_tokens=trainer.tokens, supervised_tokens=trainer.supervised_tokens)
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        (output/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('create', 'verify'):
        child = sub.add_parser(name)
        child.add_argument('--output', required=True)
        child.add_argument('--backend', choices=['mlx', 'torch'], default='mlx' if name == 'create' else 'torch')
        child.add_argument('--device', default='cpu', help='PyTorch device; MLX uses its current default')
        if name == 'verify':
            child.add_argument('--bundle', required=True)
            child.add_argument('--resume', help='Returned checkpoint for the second leg')
    args = parser.parse_args()
    if args.command == 'create':
        result = create(args.output, args.backend, args.device)
        print(json.dumps(result, indent=2))
    else:
        result = verify(args.bundle, args.output, args.backend, args.device, args.resume)
        print(json.dumps({k:v for k,v in result.items() if k != 'checks'}, indent=2))


if __name__ == '__main__':
    main()
