"""Score the predeclared local prose smoke experiment; no capability promotion."""
# Creator: Navneet Prabhakar
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
import json
import numpy as np

from slm.common import checkpoint
from slm.common.config import initialize
from slm.common.tokenizer import BPE
from slm.data.review_stream import open_checked
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.train import Inputs, read, resolve_paths, verify_checkpoint


SELECTION_SEED = 'foundation-smoke-validation-20261019-v1'


def select_groups(index, bpe):
    """Reconstruct the frozen choice from checked validation rows, never test rows."""
    train = {g for g, in index.db.execute('SELECT DISTINCT gid FROM approved WHERE split="train"')}
    groups = {}
    for data, gid in index.db.execute('SELECT data,gid FROM approved WHERE split="validation" ORDER BY eid'):
        row = json.loads(data)
        tokens = bpe.encode(row['messages'][0]['content'])
        if len(tokens) < 129 or gid in groups:
            continue
        if gid in train:
            raise ValueError('Validation group intersects training')
        groups[gid] = dict(example_id=row['example_id'], record_sha256=digest(row), group=gid,
                           tokens=tokens[:129], prediction_positions=128)
    chosen = [groups[g] for g in sorted(groups, key=lambda g: (digest([SELECTION_SEED, g]), g))[:32]]
    if len(chosen) != 32:
        raise ValueError('Exactly 32 eligible validation groups required')
    return chosen


def verify_protocol(protocol_path, freeze_path, spec_path, spec, inputs):
    p, frozen = read(protocol_path), read(freeze_path)
    if (sha(protocol_path) != frozen['protocol_file_sha256']
        or frozen['model_updates'] != 0 or frozen['model_scores_observed'] != 0
        or frozen['selected_groups'] != 32 or digest(p['groups']) != frozen['selected_rows_sha256']):
        raise ValueError('Protocol differs from the pretraining freeze receipt')
    # Every metadata field must agree with the saved pretraining receipt.
    for key, value in p.items():
        if key != 'groups' and frozen.get(key) != value:
            raise ValueError('Protocol metadata differs from freeze receipt')
    if (p['version'] != 1 or p['scope'] != 'local_foundation_smoke_only'
        or p['selection_seed'] != SELECTION_SEED or p['test_records_used'] != 0
        or p['prediction_positions'] != 4096 or p['pilot_spec_sha256'] != sha(spec_path)
        or p['config'] != inputs.config.to_dict() or p['initialization_seed'] != spec['seed']
        or p['loss_implementation'] != inputs.recipe.loss_implementation
        or p['embedding_implementation'] != inputs.recipe.embedding_implementation
        or p['tokenizer_manifest_sha256'] != inputs.data.tokenizer_hash
        or p['release_manifest_sha256'] not in spec['releases'] or len(spec['releases']) != 1):
        raise ValueError('Frozen protocol differs from the actual pilot')
    bpe = BPE.load(spec['tokenizer'])
    with open_checked(next(iter(spec['releases'].values()))) as index:
        chosen = select_groups(index, bpe)
    if p['groups'] != chosen:
        raise ValueError('Frozen prefixes differ from checked validation selection')
    return p


def paired_summary(initial, final):
    """Fixed-size paired group bootstrap: lower bound must be strictly positive."""
    a, b = np.asarray(initial, dtype=np.float64), np.asarray(final, dtype=np.float64)
    if a.shape != (32,) or b.shape != (32,) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Exactly 32 finite paired group losses required')
    delta = a - b
    rng = np.random.default_rng(20261019)
    draws = delta[rng.integers(0, 32, size=(10000, 32))].mean(axis=1)
    lower, upper = np.percentile(draws, [2.5, 97.5])
    mean = float(delta.mean())
    return dict(initial_mean_nll=float(a.mean()), final_mean_nll=float(b.mean()),
                mean_improvement_nats=mean, improvement_95_percentile_ci=[float(lower), float(upper)],
                groups=32, prediction_positions=4096, bootstrap_resamples=10000,
                bootstrap_seed=20261019, group_improvements=delta.tolist(),
                smoke_passed=bool(mean >= .1 and lower > 0), production_accepted=False,
                conversation_capability_proved=False, resumed_backend_quality_proved=False)


def score_weights(config, weights, groups, recipe, backend):
    """No gradients, padding, generation, teacher judging or structural targets."""
    if backend == 'mlx':
        from slm.backends import mlx_backend as impl
        import mlx.core as mx
        array = mx.array
        params = impl.load(config, weights)
        context = nullcontext()
    elif backend == 'torch':
        from slm.backends import torch_backend as impl
        import torch
        array = torch.tensor
        params = impl.load(config, weights, device='cpu')
        context = torch.no_grad()
    else:
        raise ValueError('Local MLX or PyTorch CPU scoring required')
    losses = []
    with context:
        for group in groups:
            if (not isinstance(group['tokens'], list)
                or any(type(token) is not int for token in group['tokens'])):
                raise ValueError('Integer token IDs required')
            tokens = np.asarray([group['tokens']], dtype=np.int32)
            if (tokens.shape != (1, 129) or tokens.min() < 0 or tokens.max() >= config.vocab_size
                or group['prediction_positions'] != 128):
                raise ValueError('Invalid fixed prefix')
            x, y = array(tokens[:, :-1]), array(tokens[:, 1:])
            mask = array(np.ones((1, 128), dtype=np.float32))
            value = impl.loss(params, config, x, y, mask,
                              loss_implementation=recipe.loss_implementation,
                              embedding_implementation=recipe.embedding_implementation)
            scalar = float(value)
            if not np.isfinite(scalar):
                raise ValueError('Nonfinite heldout loss')
            losses.append(scalar)
    return losses


def evaluate(spec_path, protocol_path, freeze_path, run_path, backend='mlx'):
    """Require a terminal, exhausted >=1M-position run and fully checked state."""
    spec_path, run_path = Path(spec_path), Path(run_path)
    spec = resolve_paths(read(spec_path), spec_path.parent)
    report, run = read(run_path/'report.json'), read(run_path/'run.json')
    inputs = Inputs(spec)
    try:
        for path in (spec_path, Path(protocol_path), Path(freeze_path), run_path/'run.json', run_path/'report.json', run_path/'events.jsonl'):
            inputs.pin_tree(path)
        p = verify_protocol(protocol_path, freeze_path, spec_path, spec, inputs)
        if (report['plan_hash'] != inputs.identity or run['plan_hash'] != inputs.identity
            or run['logical_plan'] != inputs.plan or run['resume_manifest_sha256'] is not None
            or report['initial'] != dict(step=0, cursor=0, tokens=0, supervised_tokens=0)
            or report['status'] != 'data_exhausted_before_target'
            or report['final']['cursor'] != len(inputs.data)
            or report['final']['tokens'] < 1000000
            or report['events_sha256'] != sha(run_path/'events.jsonl')):
            raise ValueError('Complete canonical-random finite-schedule smoke run required')
        latest = Path(report['latest_checkpoint']).resolve()
        if latest.parent != (run_path/'checkpoints').resolve():
            raise ValueError('Checkpoint is outside the terminal attempt')
        if sha(latest/'manifest.json') != report['latest_manifest_sha256']:
            raise ValueError('Terminal checkpoint fingerprint differs')
        inputs.pin_tree(latest)
        _, state = verify_checkpoint(latest, inputs)
        if any(state[k] != report['final'][k] for k in ('step', 'cursor', 'tokens', 'supervised_tokens')):
            raise ValueError('Terminal counters differ from verified checkpoint')
        cfg, weights = checkpoint.load(latest/'state/model')
        # Selection was frozen before training; the baseline is reconstructed now.
        initial = score_weights(cfg, initialize(cfg, spec['seed']), p['groups'], inputs.recipe, backend)
        final = score_weights(cfg, weights, p['groups'], inputs.recipe, backend)
        inputs.check()
        result = dict(version=1, creator='Navneet Prabhakar', scope=p['scope'],
                      evaluated_at_utc=datetime.now(timezone.utc).isoformat(), backend=backend,
                      device='default' if backend == 'mlx' else 'cpu',
                      protocol_sha256=sha(protocol_path), freeze_receipt_sha256=sha(freeze_path),
                      scorer_sha256=sha(__file__), plan_hash=inputs.identity,
                      model_manifest_sha256=sha(latest/'state/model/manifest.json'),
                      checkpoint_manifest_sha256=sha(latest/'manifest.json'),
                      run_report_sha256=sha(run_path/'report.json'), training_final=report['final'],
                      baseline='Canonical initialization reconstructed after training; selection, seed and metric were frozen before launch.',
                      initial_group_nll=initial, final_group_nll=final, **paired_summary(initial, final),
                      limitations=p['limitations'])
        return result
    finally:
        inputs.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('spec', 'protocol', 'freeze', 'run', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--backend', choices=('mlx', 'torch'), default='mlx')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = evaluate(args.spec, args.protocol, args.freeze, args.run, args.backend)
    # Exclusive creation prevents accidentally replacing an earlier result.
    with args.output.open('x') as f:
        f.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps({k: result[k] for k in ('initial_mean_nll', 'final_mean_nll', 'smoke_passed')}))


if __name__ == '__main__':
    main()
