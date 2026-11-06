"""Frozen tiny CPU parity diagnostic, separate Torch/MLX subprocess environments."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'reports/mlx-own-base-feasibility'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_protocol():
    protocol = json.loads((REPORT / 'protocol.json').read_text())
    for name, expected in protocol['code_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('diagnostic code differs from frozen protocol: ' + name)
    return protocol


def torch_export(protocol):
    import numpy as np
    import torch
    from gpt2 import Config, GPT2, next_token_loss
    from train import optimizer_for
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    records = []
    for seed in protocol['seeds']:
        torch.manual_seed(seed)
        cfg = Config(**protocol['tiny_config'])
        model = GPT2(cfg).cpu().eval()
        sequence = torch.randint(cfg.vocabulary, (2, 13), device='cpu')
        # Repeated IDs exercise embedding-gradient aggregation and tied output weights.
        sequence[:, 3] = sequence[:, 1]
        arrays = {'sequence': sequence.numpy()}
        arrays.update({'initial::'+n: p.detach().numpy().copy() for n, p in model.named_parameters()})
        logits = model(sequence[:, :-1])
        loss = next_token_loss(model, sequence)
        loss.backward()
        arrays['logits'] = logits.detach().numpy()
        arrays['loss'] = np.array(loss.item())
        arrays.update({'gradient::'+n: p.grad.numpy().copy() for n, p in model.named_parameters()})
        gradient_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
        arrays['gradient_norm'] = np.array(gradient_norm.item())
        arrays.update({'clipped::'+n: p.grad.numpy().copy() for n, p in model.named_parameters()})
        optimizer = optimizer_for(model)
        for group in optimizer.param_groups:
            group['lr'] = protocol['learning_rate']
        optimizer.step()
        arrays.update({'updated::'+n: p.detach().numpy().copy() for n, p in model.named_parameters()})
        arrays.update({'moment1::'+n: optimizer.state[p]['exp_avg'].numpy().copy() for n, p in model.named_parameters()})
        arrays.update({'moment2::'+n: optimizer.state[p]['exp_avg_sq'].numpy().copy() for n, p in model.named_parameters()})
        file = REPORT / f'torch-seed-{seed}.npz'
        np.savez(file, **arrays)
        records.append(dict(seed=seed, file=file.name, sha256=sha(file), parameters=sum(p.numel() for p in model.parameters()),
                            loss=loss.item(), gradient_norm=gradient_norm.item()))
    (REPORT / 'torch-reference.json').write_text(json.dumps(dict(torch=str(torch.__version__), device='cpu', records=records), indent=2)+'\n')


def mlx_check(protocol):
    import numpy as np
    import mlx.core as mx
    mx.set_default_device(mx.cpu)  # Before any arrays, optimizer, or model operations.
    if mx.default_device() != mx.cpu:
        raise RuntimeError('MLX CPU backend unavailable; diagnostic stops')
    import mlx_base as own
    cfg = own.Config(**protocol['tiny_config'])
    result = dict(device=str(mx.default_device()), dtype='float32', state='running', cases=[],
                  full_architecture_parameters_without_allocation=own.parameter_count(),
                  full_model_allocated=False, gpu_operations=False, protocol_sha256=sha(REPORT/'protocol.json'))
    assert own.parameter_count() == 124439808
    references = json.loads((REPORT/'torch-reference.json').read_text())
    all_passed = True
    for record in references['records']:
        source = REPORT / record['file']
        if sha(source) != record['sha256']:
            raise ValueError('Torch fixture changed')
        with np.load(source, allow_pickle=False) as saved:
            data = {key: saved[key] for key in saved.files}
        arrays = {k.removeprefix('initial::'): v for k, v in data.items() if k.startswith('initial::')}
        params = own.from_numpy(arrays, cfg)
        sequence = mx.array(data['sequence'].astype('int32'))
        loss, grads = mx.value_and_grad(lambda weights: own.causal_loss(weights, sequence, cfg))(params)
        logits = own.forward(params, sequence[:, :-1], cfg)
        clipped, gradient_norm = own.clip_gradients(grads)
        optimizer = own.AdamW(protocol['learning_rate'])
        updated = optimizer.update(params, clipped)
        # Explicit evaluation is required for actual lazy-execution parity, not graph construction.
        mx.eval(loss, logits, grads, clipped, gradient_norm, updated, optimizer.state)
        stats = dict(seed=record['seed'], parameters=sum(v.size for v in params.values()),
                     loss=float(loss.item()), loss_error=abs(float(loss.item())-float(data['loss'])),
                     logits_max_abs=float(np.max(np.abs(np.array(logits)-data['logits']))),
                     gradient_norm=float(gradient_norm.item()),
                     gradient_norm_error=abs(float(gradient_norm.item())-float(data['gradient_norm'])))
        for label, actual in [('gradient', grads), ('clipped', clipped), ('updated', updated)]:
            errors = {name: float(np.max(np.abs(np.array(value)-data[label+'::'+name]))) for name, value in actual.items()}
            stats[label+'_max_abs'] = max(errors.values())
            stats[label+'_worst_parameter'] = max(errors, key=errors.get)
        g_error = sum(float(np.sum((np.array(grads[n])-data['gradient::'+n]).astype('float64')**2)) for n in grads)
        g_norm = sum(float(np.sum(data['gradient::'+n].astype('float64')**2)) for n in grads)
        stats['gradient_relative_l2'] = (g_error/g_norm)**.5
        update_error = sum(float(np.sum((np.array(updated[n])-data['updated::'+n]).astype('float64')**2)) for n in updated)
        update_norm = sum(float(np.sum((data['updated::'+n]-arrays[n]).astype('float64')**2)) for n in updated)
        stats['update_relative_l2'] = (update_error/update_norm)**.5
        moments = {name: optimizer.groups[0 if p.ndim >= 2 else 1].state[name] for name, p in params.items()}
        for index, key in [(1, 'm'), (2, 'v')]:
            stats[f'moment{index}_max_abs'] = max(float(np.max(np.abs(np.array(moments[n][key])-data[f'moment{index}::'+n]))) for n in params)
        alternate = data['sequence'][:, :-1].copy()
        alternate[:, 6:] = (alternate[:, 6:]+7) % cfg.vocabulary
        causal = own.forward(params, mx.array(alternate.astype('int32')), cfg)
        mx.eval(causal)
        stats['causal_prefix_max_abs'] = float(np.max(np.abs(np.array(causal)[:, :6]-np.array(logits)[:, :6])))
        thresholds = protocol['maximum_errors']
        stats['passed'] = all(np.isfinite(stats[name]) and stats[name] <= bound for name, bound in thresholds.items())
        all_passed = all_passed and stats['passed']
        result['cases'].append(stats)
    result['state'] = 'passed' if all_passed else 'failed'
    (REPORT/'results.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, indent=2))
    return all_passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mlx-check', action='store_true')
    args = parser.parse_args()
    protocol = read_protocol()
    if args.mlx_check:
        try:
            success = mlx_check(protocol)
        except Exception as error:
            (REPORT/'execution-error.json').write_text(json.dumps(dict(state='failed', error=f'{type(error).__name__}: {error}',
                                                                       gpu_operations=False), indent=2)+'\n')
            raise
        raise SystemExit(0 if success else 1)
    if (REPORT/'results.json').exists() or (REPORT/'execution-error.json').exists():
        raise ValueError('diagnostic result already exists; preserve original attempt')
    torch_export(protocol)
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    completed = subprocess.run([str(ROOT/'.venv-mlx-own-base/bin/python'), str(Path(__file__).resolve()), '--mlx-check'],
                               cwd=ROOT, env=env, timeout=120, check=False)
    raise SystemExit(completed.returncode)


if __name__ == '__main__':
    main()
