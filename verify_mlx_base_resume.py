"""Prospectively frozen tiny CPU conversion, accumulation and fresh-process resume check."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import mlx_checkpoint_bridge as bridge

ROOT = Path(__file__).resolve().parent
REPORT = ROOT/'reports/mlx-own-base-resume-feasibility'


def protocol():
    value = json.loads((REPORT/'protocol.json').read_text())
    for name, expected in value['code_sha256'].items():
        if bridge.sha(ROOT/name) != expected:
            raise ValueError('frozen implementation changed: '+name)
    return value, bridge.sha(REPORT/'protocol.json')


def torch_export(spec, identity):
    import torch
    from gpt2 import Config, GPT2
    from train import optimizer_for, backward_rows
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    records = []
    for seed in spec['seeds']:
        prior = ROOT/f'reports/mlx-own-base-feasibility/torch-seed-{seed}.npz'
        if bridge.sha(prior) != spec['initial_fixture_sha256'][str(seed)]:
            raise ValueError('previous random initialization fixture changed')
        torch.manual_seed(seed)
        cfg = Config(**spec['config'])
        model = GPT2(cfg).cpu().eval()
        with np.load(prior, allow_pickle=False) as saved:
            model.load_state_dict({n.removeprefix('initial::'):torch.from_numpy(saved[n]) for n in saved.files if n.startswith('initial::')})
        optimizer = optimizer_for(model)
        for group in optimizer.param_groups:
            group['lr'] = spec['learning_rate']
        batches = np.random.default_rng(seed+1).integers(cfg.vocabulary, size=(spec['total_steps'], 3, 13), dtype=np.int64)
        batches[:, :, 3] = batches[:, :, 1]
        reference = {'batches':batches}
        for i, batch in enumerate(batches):
            step = i+1
            sequence = torch.from_numpy(batch)
            optimizer.zero_grad(set_to_none=True)
            loss = 0.
            for micro in (sequence[:1], sequence[1:]):
                loss += backward_rows(model, micro[:, :-1], micro[:, 1:], 36).item()
            reference[f'loss::{step}'] = np.array(loss)
            if step > spec['conversion_step']:
                with torch.no_grad():
                    reference[f'logits::{step}'] = model(sequence[:, :-1]).numpy().copy()
                for name, p in model.named_parameters():
                    reference[f'gradient::{step}::{name}'] = p.grad.numpy().copy()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
            optimizer.step()
            if step == spec['conversion_step']:
                meta, arrays = bridge.from_torch(model, optimizer, step=step, effective_tokens=36,
                                                 experiment=identity, config=cfg, rng_state=torch.get_rng_state(), seed=seed)
                bridge.write_bundle(REPORT/f'torch-state-{seed}', meta, arrays)
            if step > spec['conversion_step']:
                for name, p in model.named_parameters():
                    for kind, tensor in [('weight',p), ('m',optimizer.state[p]['exp_avg']), ('v',optimizer.state[p]['exp_avg_sq'])]:
                        reference[f'{kind}::{step}::{name}'] = tensor.detach().numpy().copy()
        file = REPORT/f'reference-{seed}.npz'
        np.savez(file, **reference)
        records.append(dict(seed=seed, file=file.name, sha256=bridge.sha(file)))
    (REPORT/'references.json').write_text(json.dumps(dict(torch=str(torch.__version__),records=records),indent=2)+'\n')


def reference(seed):
    records = json.loads((REPORT/'references.json').read_text())['records']
    entry = next(row for row in records if row['seed'] == seed)
    path = REPORT/entry['file']
    if bridge.sha(path) != entry['sha256']:
        raise ValueError('reference corpus/state changed')
    with np.load(path, allow_pickle=False) as saved:
        return {name:saved[name] for name in saved.files}


def train_step(params, optimizer, key, cursor, cfg, data):
    import mlx.core as mx
    import mlx_base as own
    sequence = mx.array(data[cursor['step']].astype('int32'))
    total, grads = None, None
    for micro in (sequence[:1], sequence[1:]):
        value, current = mx.value_and_grad(lambda p: own.causal_loss(p, micro, cfg) * (micro.shape[0]/3))(params)
        total = value if total is None else total+value
        grads = current if grads is None else {name:grads[name]+current[name] for name in grads}
        mx.eval(total, grads)
    clipped, _ = own.clip_gradients(grads)
    updated = optimizer.update(params, clipped)
    split = mx.random.split(key, 2, stream=mx.cpu)
    key = split[0]
    canary = mx.random.uniform(shape=(4,), key=split[1], stream=mx.cpu)
    mx.eval(updated, optimizer.state, key, canary)
    cursor = dict(step=cursor['step']+1, offset=cursor['offset']+36, trained_tokens=cursor['trained_tokens']+36)
    return updated, key, cursor, float(total.item()), grads, np.array(canary)


def negative_tests(meta, arrays, identity):
    import copy
    tests = {}
    cases = ('corrupt_bytes', 'missing_moment', 'wrong_optimizer_step', 'missing_rng', 'wrong_cursor', 'wrong_decay', 'wrong_identity')
    for name in cases:
        with tempfile.TemporaryDirectory(dir=REPORT) as temp:
            directory = Path(temp)/'fixture'
            bridge.write_bundle(directory, meta, arrays)
            receipt = json.loads((directory/'receipt.json').read_text())
            modified = {key:value.copy() for key,value in arrays.items()}
            if name == 'corrupt_bytes':
                body = bytearray((directory/'state.npz').read_bytes());body[-1] ^= 1
                (directory/'state.npz').write_bytes(body)
            else:
                if name == 'missing_moment': del modified['m::'+meta['parameter_order'][0]]
                elif name == 'wrong_optimizer_step': modified['group_step::0'] += np.uint64(1)
                elif name == 'missing_rng': del modified['mlx_key']
                elif name == 'wrong_cursor': receipt['metadata'] = copy.deepcopy(meta);receipt['metadata']['cursor']['offset'] += 1
                elif name == 'wrong_decay': receipt['metadata'] = copy.deepcopy(meta);receipt['metadata']['optimizer']['decay'] = [.1,.1]
                np.savez(directory/'state.npz', **modified)
                receipt.update(data_bytes=(directory/'state.npz').stat().st_size, data_sha256=bridge.sha(directory/'state.npz'))
                receipt.pop('sha256')
                import hashlib
                receipt['sha256'] = hashlib.sha256(bridge.canonical(receipt)).hexdigest()
                (directory/'receipt.json').write_text(json.dumps(receipt))
            try:
                bridge.read_bundle(directory, 'wrong' if name == 'wrong_identity' else identity)
            except (ValueError, KeyError) as error:
                tests[name] = dict(refused=True, reason=str(error))
            else:
                tests[name] = dict(refused=False)
    return tests


def mlx_run(spec, identity, resume_seed=None):
    import mlx.core as mx
    mx.set_default_device(mx.cpu)
    import mlx_base as own
    if resume_seed is not None:
        seed = resume_seed
        meta, arrays = bridge.read_bundle(REPORT/f'mlx-paused-{seed}', identity)
        params, opt, key, cursor, cfg = bridge.to_mlx(meta, arrays, identity)
        expected_meta, expected = bridge.read_bundle(REPORT/f'mlx-final-{seed}', identity)
        ref = reference(seed)
        tail = []
        while cursor['step'] < spec['total_steps']:
            params, key, cursor, loss, _, canary = train_step(params, opt, key, cursor, cfg, ref['batches'])
            tail.append(dict(step=cursor['step'], loss=loss, canary=canary.tolist()))
        final_meta, actual = bridge.from_mlx(params,opt,key,cursor,meta,arrays)
        expected_tail = json.loads((REPORT/f'trace-{seed}.json').read_text())[spec['pause_step']-spec['conversion_step']:]
        exact = all(np.array_equal(actual[n],expected[n]) for n in expected)
        passed = exact and tail == expected_tail and cursor == expected_meta['cursor']
        result = dict(seed=seed,passed=passed,all_arrays_bit_identical=exact,trace_rng_and_loss_exact=tail==expected_tail,
                      cursor_exact=cursor==expected_meta['cursor'],cursor=cursor,compared_arrays=len(expected),fresh_process=True)
        (REPORT/f'resume-{seed}.json').write_text(json.dumps(result,indent=2)+'\n')
        return passed
    result = dict(state='running',device=str(mx.default_device()),cases=[],gpu_operations=False,full_model_allocated=False,protocol_sha256=identity)
    for seed in spec['seeds']:
        meta, arrays = bridge.read_bundle(REPORT/f'torch-state-{seed}', identity)
        params, opt, key, cursor, cfg = bridge.to_mlx(meta,arrays,identity)
        if not np.array_equal(np.array(mx.random.key(seed)),arrays['mlx_key']):
            raise ValueError('explicit target RNG key encoding mismatch')
        round_meta, round_arrays = bridge.from_mlx(params,opt,key,cursor,meta,arrays)
        conversion_exact = all(np.array_equal(arrays[n],round_arrays[n]) for n in arrays)
        ref = reference(seed)
        case = dict(seed=seed,conversion_exact=conversion_exact,updates=[],negative_tests=negative_tests(meta,arrays,identity))
        traces = []
        while cursor['step'] < spec['total_steps']:
            step = cursor['step']+1
            sequence = mx.array(ref['batches'][cursor['step']].astype('int32'))
            # Independent whole-batch gradient checks unequal microbatch weighting.
            _, full_grad = mx.value_and_grad(lambda p: own.causal_loss(p,sequence,cfg))(params)
            logits = own.forward(params,sequence[:,:-1],cfg)
            mx.eval(logits,full_grad)
            params,key,cursor,loss,grads,canary = train_step(params,opt,key,cursor,cfg,ref['batches'])
            traces.append(dict(step=step,loss=loss,canary=canary.tolist()))
            stats = dict(step=step,loss_error=abs(loss-float(ref[f'loss::{step}'])),
                         logits_max_abs=float(np.max(np.abs(np.array(logits)-ref[f'logits::{step}']))),
                         gradient_max_abs=max(float(np.max(np.abs(np.array(g)-ref[f'gradient::{step}::{n}']))) for n,g in grads.items()),
                         accumulation_gradient_max_abs=max(float(np.max(np.abs(np.array(grads[n])-np.array(full_grad[n])))) for n in grads))
            _, snap = bridge.from_mlx(params,opt,key,cursor,meta,arrays)
            for kind in ('weight','m','v'):
                stats[kind+'_max_abs'] = max(float(np.max(np.abs(snap[kind+'::'+n]-ref[f'{kind}::{step}::{n}']))) for n in params)
            stats['passed'] = all(np.isfinite(stats[n]) and stats[n] <= bound for n,bound in spec['maximum_errors'].items())
            case['updates'].append(stats)
            if step == spec['pause_step']:
                pause_meta,pause_arrays = bridge.from_mlx(params,opt,key,cursor,meta,arrays)
                bridge.write_bundle(REPORT/f'mlx-paused-{seed}',pause_meta,pause_arrays)
        final_meta,final_arrays = bridge.from_mlx(params,opt,key,cursor,meta,arrays)
        bridge.write_bundle(REPORT/f'mlx-final-{seed}',final_meta,final_arrays)
        (REPORT/f'trace-{seed}.json').write_text(json.dumps(traces,indent=2)+'\n')
        completed = subprocess.run([sys.executable,str(Path(__file__).resolve()),'--resume-seed',str(seed)],cwd=ROOT,timeout=60)
        case['resume'] = json.loads((REPORT/f'resume-{seed}.json').read_text())
        case['passed'] = conversion_exact and all(s['passed'] for s in case['updates']) and all(s['refused'] for s in case['negative_tests'].values()) and completed.returncode==0 and case['resume']['passed']
        result['cases'].append(case)
    result['state'] = 'passed' if all(c['passed'] for c in result['cases']) else 'failed'
    (REPORT/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return result['state']=='passed'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mlx-check',action='store_true')
    parser.add_argument('--resume-seed',type=int)
    args=parser.parse_args()
    spec,identity=protocol()
    if args.mlx_check or args.resume_seed is not None:
        raise SystemExit(0 if mlx_run(spec,identity,args.resume_seed) else 1)
    if (REPORT/'references.json').exists():
        raise ValueError('preserve prior execution; new attempt requires a new version')
    torch_export(spec,identity)
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
    command=[str(ROOT/'.venv-mlx-own-base/bin/python'),str(Path(__file__).resolve()),'--mlx-check']
    raise SystemExit(subprocess.run(command,cwd=ROOT,env=env,timeout=180).returncode)


if __name__=='__main__':
    main()
