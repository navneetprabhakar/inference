"""Portable cross-host training fixtures. No cloud provisioning or credentials."""
import argparse
import hashlib
import json
import platform
import time
import resource
from pathlib import Path
from importlib.metadata import version
import numpy as np
from safetensors.numpy import load_file, save_file
from slm.common.config import Config, initialize
from slm.common.training import Batches, Trainer, Recipe


def memory_snapshot(backend, device):
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {'process_peak_rss_bytes': int(rss if platform.system() == 'Darwin' else rss*1024),
              'scope': 'Process lifetime high-water mark; allocator memory overlaps RSS on unified memory.'}
    if backend == 'mlx':
        import mlx.core as mx
        result.update(allocator_peak_bytes=mx.get_peak_memory(), allocator_active_bytes=mx.get_active_memory(),
                      allocator_cache_bytes=mx.get_cache_memory())
    elif device.startswith('cuda'):
        import torch
        result.update(allocator_peak_bytes=torch.cuda.max_memory_allocated(device),
                      allocator_reserved_bytes=torch.cuda.max_memory_reserved(device))
    return result


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
    metadata = Path(root)/'fixture.json'
    spec = json.loads(metadata.read_text()) if metadata.exists() else {'vocab_size':64,'batch_count':6}
    with np.load(Path(root)/'batches.npz', allow_pickle=False) as raw:
        return Batches([(raw[f'x{i}'], raw[f'y{i}'], raw[f'mask{i}']) for i in range(spec['batch_count'])], spec['vocab_size'])


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


def full_depth_budget(config):
    if (config is None or (config.num_layers,config.hidden_size,config.intermediate_size,
        config.num_heads,config.num_kv_heads)!=(24,512,1536,8,2)
        or config.vocab_size not in (16384,24576)):
        raise ValueError('Full-depth policy is restricted to the documented target architecture')
    # Engineering accuracy budget, not a worst-case theorem for a trained network.
    return config.num_layers*np.sqrt(config.hidden_size)*(np.finfo(np.float32).eps/2)


def compare(actual, expected, policy='tiny_fp32_v1', config=None):
    if policy not in ('tiny_fp32_v1','full_depth_fp32_v1'):
        raise ValueError('Unknown numerical policy')
    budget=full_depth_budget(config) if policy=='full_depth_fp32_v1' else None
    if actual.keys() != expected.keys():
        raise ValueError('Probe tensor keys differ')
    metrics = {}
    for name in actual:
        a, e = actual[name], expected[name]
        if a.shape != e.shape or not np.isfinite(a).all() or not np.isfinite(e).all():
            raise ValueError(f'Invalid probe tensor: {name}')
        # Prototype/state bounds remain fixed; the named full-depth branch is explicit.
        atol = 1e-6 if name.startswith(('gradient:', 'moment_')) else 1e-5
        delta = np.abs(a-e)
        metrics[name] = {'max_abs_error': float(delta.max()), 'mean_abs_error': float(delta.mean()),
                         'atol': atol, 'rtol': 1e-4}
        if budget is not None and (name.startswith('gradient:') or name in ('logits','cached_logits')):
            difference=a.astype(np.float64)-e
            norm=float(np.linalg.norm(e.astype(np.float64).ravel()))
            relative=float(np.linalg.norm(difference.ravel())/norm) if norm else None
            bound=float(budget*max(1.,float(np.abs(e).max()))) if norm else atol
            metrics[name].update(policy=policy,relative_l2_error=relative,relative_l2_limit=float(budget),
                max_abs_limit=bound,prototype_pointwise_violations=int((delta>atol+1e-4*np.abs(e)).sum()))
            if float(delta.max())>bound or (norm and relative>budget):
                raise AssertionError(f'{name}: full-depth accuracy budget exceeded: {metrics[name]}')
        else:
            np.testing.assert_allclose(a, e, atol=atol, rtol=1e-4, err_msg=name)
    return metrics


def create(destination, backend='mlx', device='cpu', config=None, recipe=None, seed=91, initialization_seed=42,
           comparison_policy='tiny_fp32_v1'):
    start_time = time.perf_counter()
    env = environment(backend, device)
    config = config or Config()
    if comparison_policy=='full_depth_fp32_v1':full_depth_budget(config)
    elif comparison_policy!='tiny_fp32_v1':raise ValueError('Unknown numerical policy')
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(seed)
    arrays = {}
    for i, length in enumerate((6, 8, 5, 9, 4, 7)):
        if length > config.max_seq_len: raise ValueError('Fixture exceeds configured context')
        arrays[f'x{i}'] = rng.integers(0, config.vocab_size, (2, length), dtype=np.int64)
        arrays[f'y{i}'] = rng.integers(0, config.vocab_size, (2, length), dtype=np.int64)
        arrays[f'mask{i}'] = rng.integers(0, 2, (2, length)).astype(np.float32)
        arrays[f'mask{i}'][:, 0] = 1
    np.savez(root/'batches.npz', **arrays)
    (root/'fixture.json').write_text(json.dumps({'vocab_size':config.vocab_size,'batch_count':6,
          'architecture':config.to_dict(),'probe_steps':[2,4,6], 'seed':seed,
          'initialization_seed':initialization_seed,'comparison_policy':comparison_policy},indent=2)+'\n')
    trainer = Trainer(config, initialize(config,initialization_seed), get_batches(root), backend, device,recipe=recipe)
    for _ in range(2): trainer.update()
    trainer.save(root/'initial')
    for step in (2, 4, 6):
        while trainer.step < step: trainer.update()
        save_file(capture(trainer), str(root/f'expected-{step}.safetensors'))
    (root/'origin.json').write_text(json.dumps(env, indent=2)+'\n')
    measurement = {'seconds':time.perf_counter()-start_time,'parameters':config.parameter_count,
                   'model_fp32_bytes':config.parameter_count*4,'memory':memory_snapshot(backend,device)}
    (root/'measurement.json').write_text(json.dumps(measurement,indent=2)+'\n')
    write_manifest(root)
    return {'bundle': str(root), 'bundle_hash': validate_bundle(root), 'origin': env,'measurement':measurement}


def verify(bundle, output, backend='torch', device='cpu', resume=None):
    start_time = time.perf_counter()
    env = environment(backend, device)
    bundle, output = Path(bundle), Path(output)
    digest = validate_bundle(bundle)
    output.mkdir(parents=True, exist_ok=False)
    report = {'passed': False, 'bundle_hash': digest, 'origin': json.loads((bundle/'origin.json').read_text()),
              'destination': env, 'checks': {}}
    trainer=None
    try:
        trainer = Trainer.resume(resume or bundle/'initial', get_batches(bundle), backend, device)
        spec=json.loads((bundle/'fixture.json').read_text()) if (bundle/'fixture.json').exists() else {}
        policy=spec.get('comparison_policy','tiny_fp32_v1')
        report['comparison_policy']=policy
        start = trainer.step
        report.update(start_step=start,parameters=trainer.config.parameter_count)
        if start not in (2, 4):
            raise ValueError('Fixture continuation must begin at update 2 or 4')
        for step in (start, start+2):
            report['attempted_probe_step']=step
            while trainer.step < step: trainer.update()
            report['checks'][str(step)] = compare(capture(trainer), load_file(str(bundle/f'expected-{step}.safetensors')),policy,trainer.config)
        trainer.save(output/'checkpoint')
        report.update(passed=True, start_step=start, final_step=trainer.step,
                      processed_tokens=trainer.tokens, supervised_tokens=trainer.supervised_tokens,
                      parameters=trainer.config.parameter_count,seconds=time.perf_counter()-start_time,
                      memory=memory_snapshot(backend,device))
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        report.setdefault('seconds',time.perf_counter()-start_time)
        report.setdefault('memory',memory_snapshot(backend,device))
        if trainer is not None:report['completed_update_step']=trainer.step
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
        else:
            child.add_argument('--config',help='Architecture JSON; default is the tiny prototype')
            child.add_argument('--recipe',help='Explicit optimizer recipe JSON; default retains the tiny recipe')
            child.add_argument('--seed',type=int,default=91,help='Synthetic batch seed')
            child.add_argument('--initialization-seed',type=int,default=42)
            child.add_argument('--comparison-policy',choices=['tiny_fp32_v1','full_depth_fp32_v1'],default='tiny_fp32_v1')
    args = parser.parse_args()
    if args.command == 'create':
        config=Config(**json.loads(Path(args.config).read_text())) if args.config else None
        recipe=Recipe(**json.loads(Path(args.recipe).read_text())) if args.recipe else None
        result = create(args.output, args.backend, args.device,config,recipe,args.seed,args.initialization_seed,args.comparison_policy)
        print(json.dumps(result, indent=2))
    else:
        result = verify(args.bundle, args.output, args.backend, args.device, args.resume)
        print(json.dumps({k:v for k,v in result.items() if k != 'checks'}, indent=2))


if __name__ == '__main__':
    main()
