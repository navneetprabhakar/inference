"""Three bounded own-base optimizer branches with a common, explicit LR restart.

The preserve arm retains Adam moments/step, not an uninterrupted LR trajectory.
Only the CLI's verified production configuration may use MPS. Tiny CPU fixtures
exercise the same update/checkpoint loop without loading a production model.
"""
import argparse
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
import torch
from torch.nn import functional as F

import checkpoint
from base_run_control import Campaign, CampaignStop
from base_train import Corpus, precision, document_losses, compare_losses, language_diagnostics
from gpt2 import Config, GPT2
from pretrained_base import continuation_parent
from pretrain import atomic_status
from tokenizer import ASSETS, load
from train import optimizer_for

ROOT = Path(__file__).resolve().parent
FOUNDATION_BUDGET = ROOT/'reports/base-foundation-100m/budget.json'
FOUNDATION_SHA = '658702f471c49b4362c29f46795f5fc6b3135f7e7c7bd540e50d34c2c547fb7d'
BRANCHES = {'preserve-095': .95, 'reset-095': .95, 'reset-scaled': .95**(8192/524288)}
RUNTIME = ('optimizer_ablation_train.py', 'base_train.py', 'base_run_control.py',
           'gpt2.py', 'train.py', 'guards.py', 'checkpoint.py', 'tokenizer.py',
           'pretrained_base.py', 'pretrain.py')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@contextmanager
def parent_lock(run):
    with (run/'.checkpoint.lock').open('rb') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('parent checkpoint publication active') from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def verify_code(code):
    if not isinstance(code, dict) or not set(RUNTIME) <= code.keys():
        raise ValueError('complete runtime code pins required')
    for name, expected in code.items():
        path = (ROOT/name).resolve()
        if path.parent != ROOT or checkpoint.checksum(path) != expected:
            raise ValueError('frozen code changed: '+name)


def verify_parent(spec, config=None):
    """Verify the completed, exact 100M foundation endpoint before allocation.

    Returns mmap-backed CPU payload and receipt; callers must release them after
    copying weights/moments. Hashes are integrity receipts, not signatures.
    """
    config = config or Config()
    supplied = spec['parent']
    if set(supplied) != {'run', 'checkpoint', 'sha256', 'bytes',
                         'campaign_spec_sha256', 'ledger_sha256'}:
        raise ValueError('incomplete parent artifact receipt')
    if checkpoint.checksum(FOUNDATION_BUDGET) != FOUNDATION_SHA:
        raise ValueError('original foundation budget changed')
    foundation = json.loads(FOUNDATION_BUDGET.read_text())
    run = Path(supplied['run']).resolve()
    if run != (ROOT/'runs/own-base-foundation-01').resolve():
        raise ValueError('unexpected foundation run')
    with parent_lock(run):
        if (checkpoint.checksum(run/'campaign.json') != supplied['ledger_sha256']
                or checkpoint.checksum(run/'campaign-spec.json') != supplied['campaign_spec_sha256']):
            raise ValueError('parent ledger/spec byte identity changed')
        ledger = json.loads((run/'campaign.json').read_text())
        digest = ledger.pop('sha256')
        if hashlib.sha256(canonical(ledger)).hexdigest() != digest:
            raise ValueError('parent ledger checksum mismatch')
        frozen = json.loads((run/'campaign-spec.json').read_text())
        if (ledger['spec'] != frozen or hashlib.sha256(canonical(frozen)).hexdigest()
                != supplied['campaign_spec_sha256']):
            raise ValueError('parent immutable campaign identity mismatch')
        identity = frozen['identity']
        if (identity['model'] != asdict(config) or identity['tokenizer'] != ASSETS
                or identity['protocol'] != foundation
                or identity['scheduler'] != foundation['scheduler']
                or identity['seed'] != foundation['seed']
                or identity['torch_version'] != str(torch.__version__)
                or frozen['token_limit'] != foundation['target_tokens']):
            raise ValueError('parent architecture/tokenizer/protocol identity mismatch')
        if config == Config() and (identity.get('device') != 'mps' or identity.get('corpus') !=
                dict(directory=foundation['corpus'], manifest=foundation['manifest_sha256'],
                     validation=foundation['validation_blocks_sha256'])):
            raise ValueError('parent device/corpus identity mismatch')
        for name, expected in foundation['code_sha256'].items():
            if checkpoint.checksum(ROOT/name) != expected:
                raise ValueError('parent runtime changed: '+name)
            if name != 'base_supervise.py' and identity['code'].get(name) != expected:
                raise ValueError('parent payload runtime identity mismatch')
        origin = continuation_parent(foundation, config)
        expected_origin = dict(mode='own_pretraining', path=origin['path'], sha256=origin['sha256'],
                               random_lineage_root=origin['acceptance_report_sha256'])
        if identity['initialization'] != expected_origin or checkpoint.checksum(Path(origin['path'])) != origin['sha256']:
            raise ValueError('own random-initialization ancestry mismatch')
        target = foundation['target_tokens']
        if (ledger['state'] != 'completed' or ledger['trained_tokens'] != target
                or ledger['reserved_tokens'] != target or spec['source_offset'] != target):
            raise ValueError('parent is not the complete no-replay-loss foundation endpoint')
        entry = ledger['checkpoints'][0]
        latest = json.loads((run/'latest.json').read_text())
        protected = json.loads((run/'protected.json').read_text())
        if (entry != latest[0] or entry['file'] != supplied['checkpoint']
                or entry['file'] not in protected or entry['sha256'] != supplied['sha256']
                or entry['bytes'] != supplied['bytes']):
            raise ValueError('parent is not the protected receipted terminal artifact')
        name = entry['file']
        if not checkpoint.FILE_NAME.fullmatch(name) or Path(name).name != name:
            raise ValueError('invalid parent checkpoint basename')
        path = run/name
        if path.is_symlink() or path.stat().st_size != entry['bytes'] or checkpoint.checksum(path) != entry['sha256']:
            raise ValueError('parent artifact checksum/size mismatch')
        before = path.stat()
        payload = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
        after = path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError('parent changed during load')
        if (payload['identity'] != identity or payload['campaign_id'] != ledger['campaign_id']
                or payload['spec_sha256'] != supplied['campaign_spec_sha256']
                or payload['step'] != ledger['step'] or payload['trained_tokens'] != target
                or payload['offset'] != target
                or payload['step']*foundation['targets_per_update'] != target):
            raise ValueError('parent payload identity/cursor mismatch')
        if (not payload['history'] or payload['history'][-1]['trained_tokens'] != target
                or not math.isfinite(payload['history'][-1]['mean_ce'])):
            raise ValueError('parent lacks complete endpoint evaluation')
        for name, key in [('corpus', 'corpus'), ('manifest_sha256', 'manifest_sha256'),
                          ('validation_blocks_sha256', 'validation_blocks_sha256'),
                          ('diagnostics', 'diagnostics'), ('diagnostics_sha256', 'diagnostics_sha256')]:
            if spec[name] != foundation[key]:
                raise ValueError('branch data differs from parent corpus identity')
        return payload, dict(supplied, step=payload['step'], trained_tokens=target,
                             random_lineage_root=origin['acceptance_report_sha256'],
                             baseline_ce=payload['history'][-1]['mean_ce'])


def validate_spec(spec, config, device):
    if device not in ('cpu', 'mps') or (device == 'mps' and config != Config()):
        raise ValueError('production device/configuration mismatch')
    if spec['branch'] not in BRANCHES:
        raise ValueError('unknown ablation branch')
    length, batch, effective, target = (spec[k] for k in
                                      ('length', 'microbatch', 'targets_per_update', 'target_tokens'))
    if (any(type(x) is not int for x in (length, batch, effective, target, spec['source_offset']))
            or min(length, batch, effective, target) <= 0 or effective % (length*batch)
            or target % effective or spec['source_offset'] < 0):
        raise ValueError('invalid data layout/cursor/budget')
    if config == Config() and (length, batch, effective, target, spec['source_offset']) != (512, 2, 8192, 19996672, 99999744):
        raise ValueError('production experiment layout differs from preregistration')
    if config == Config() and (type(spec['seed']) is not int or spec['seed'] != 20261106 or spec['bf16'] is not True):
        raise ValueError('production seed/precision differs from preregistration')
    schedule = spec['scheduler']
    if (set(schedule) != {'mode', 'start_lr', 'peak_lr', 'warmup_tokens', 'horizon_tokens'}
            or schedule['mode'] != 'linear-rewarm-flat'
            or schedule['start_lr'] != 6e-6 or schedule['peak_lr'] != 6e-5
            or type(schedule['warmup_tokens']) is not int
            or not 0 < schedule['warmup_tokens'] < target
            or schedule['horizon_tokens'] != target):
        raise ValueError('invalid common explicit LR restart')
    if config == Config() and schedule['warmup_tokens'] != 1000000:
        raise ValueError('production rewarmup differs from preregistration')
    verify_code(spec['code_sha256'])
    if checkpoint.checksum(Path(spec['protocol_path'])) != spec['protocol_sha256']:
        raise ValueError('ablation protocol changed')


def learning_rate(tokens, schedule):
    if tokens >= schedule['warmup_tokens']:
        return schedule['peak_lr']
    fraction = min(1., max(0., tokens/schedule['warmup_tokens']))
    return schedule['start_lr']+(schedule['peak_lr']-schedule['start_lr'])*fraction


def validate_optimizer(opt, step, beta2):
    if len(opt.param_groups) != 2:
        raise ValueError('optimizer group count mismatch')
    for index, group in enumerate(opt.param_groups):
        if (tuple(group['betas']) != (.9, beta2) or group['eps'] != 1e-8
                or group['weight_decay'] != (.1, 0.)[index]
                or group.get('amsgrad', False) or group.get('maximize', False)):
            raise ValueError('optimizer hyperparameter mismatch')
        for parameter in group['params']:
            if (parameter.ndim >= 2) != (index == 0):
                raise ValueError('optimizer parameter grouping mismatch')
            state = opt.state.get(parameter, {})
            if step == 0:
                if state:
                    raise ValueError('fresh optimizer is not empty')
                continue
            if set(state) != {'step', 'exp_avg', 'exp_avg_sq'} or float(state['step']) != step:
                raise ValueError('optimizer step/moment inventory mismatch')
            for name in ('exp_avg', 'exp_avg_sq'):
                value = state[name]
                if (value.shape != parameter.shape or value.dtype != torch.float32
                        or not bool(torch.isfinite(value).all())):
                    raise ValueError('invalid optimizer moment')
            if bool((state['exp_avg_sq'] < 0).any()):
                raise ValueError('negative optimizer second moment')


def initialize_optimizer(model, parent, branch):
    opt = optimizer_for(model)
    # Validate source states for all arms, including those which discard them.
    source = optimizer_for(model)
    source.load_state_dict(parent['optimizer'])
    validate_optimizer(source, parent['step'], .95)
    if branch == 'preserve-095':
        opt = source
        initial_step = parent['step']
    else:
        initial_step = 0
        for group in opt.param_groups:
            group['betas'] = (.9, BRANCHES[branch])
    for group in opt.param_groups:
        group['lr'] = 6e-6
    validate_optimizer(opt, initial_step, BRANCHES[branch])
    return opt, initial_step


def train(spec_path, run_path, *, resume=False, device='mps', model_config=None):
    spec_path, run_path = Path(spec_path), Path(run_path)
    spec = json.loads(spec_path.read_text())
    config = model_config or Config()
    validate_spec(spec, config, device)
    parent, receipt = verify_parent(spec, config)
    length, batch, effective = (spec[k] for k in ('length', 'microbatch', 'targets_per_update'))
    initial_offset = spec['source_offset']
    corpus = Corpus(spec['corpus'], spec['manifest_sha256'], spec['validation_blocks_sha256'],
                    length, batch, device=device)
    if initial_offset+spec['target_tokens'] >= len(corpus.arrays['train']):
        raise ValueError('insufficient unseen corpus positions for full branch')
    path = Path(spec['diagnostics'])
    if checkpoint.checksum(path) != spec['diagnostics_sha256']:
        raise ValueError('fixed diagnostics changed')
    diagnostics = json.loads(path.read_text())
    identity = dict(seed=spec['seed'], model=asdict(config), tokenizer=ASSETS,
                    initialization=dict(mode='own_pretraining', path=str(Path(spec['parent']['run'])/spec['parent']['checkpoint']),
                                        sha256=spec['parent']['sha256'], random_lineage_root=receipt['random_lineage_root']),
                    corpus=dict(directory=spec['corpus'], manifest=spec['manifest_sha256'],
                                validation=spec['validation_blocks_sha256'], source_offset=initial_offset),
                    scheduler=spec['scheduler'], protocol=spec, parent_receipt=receipt,
                    device=device, torch_version=str(torch.__version__), code=spec['code_sha256'])
    torch.set_num_threads(1)
    with Campaign(run_path, identity, token_limit=spec['target_tokens'], active_seconds=spec['active_seconds'],
                  calendar_seconds=spec['calendar_seconds'], lease_seconds=spec['lease_seconds'], resume=resume) as campaign:
        torch.manual_seed(spec['seed'])
        model = GPT2(config).to(device)
        history, best, bad_windows, step, trained = [], None, 0, 0, 0
        initial_optimizer_step = receipt['step'] if spec['branch'] == 'preserve-095' else 0
        tokenizer = load()
        if resume:
            saved = campaign.load()
            model.load_state_dict(saved['model'], strict=True)
            opt = optimizer_for(model)
            opt.load_state_dict(saved['optimizer'])
            step, trained = saved['step'], saved['trained_tokens']
            if (trained != step*effective or saved['offset'] != initial_offset+trained
                    or saved['initial_optimizer_step'] != initial_optimizer_step):
                raise ValueError('resume source/branch/optimizer cursor mismatch')
            validate_optimizer(opt, initial_optimizer_step+step, BRANCHES[spec['branch']])
            history, best, bad_windows = saved['history'], saved['best'], saved['bad_windows']
            torch.set_rng_state(saved['cpu_rng'])
            if device == 'mps':
                torch.mps.set_rng_state(saved['mps_rng'])
            del saved
        else:
            if any(value.dtype != torch.float32 or not bool(torch.isfinite(value).all())
                   for value in parent['model'].values()):
                raise ValueError('parent master weights must be finite FP32')
            model.load_state_dict(parent['model'], strict=True)
            opt, initial_optimizer_step = initialize_optimizer(model, parent, spec['branch'])
            # Identical initial RNG state in all branches, in addition to identical data.
            torch.set_rng_state(parent['cpu_rng'])
            if device == 'mps':
                torch.mps.set_rng_state(parent['mps_rng'])
        del parent
        last_save = time.monotonic()
        milestones = {0, spec['target_tokens']} | {
            math.ceil(n/effective)*effective for n in (1000000, 5000000, 10000000, 15000000)
            if n < spec['target_tokens']}

        def save(protect=False):
            nonlocal last_save
            campaign.save(dict(step=step, model=model.state_dict(), optimizer=opt.state_dict(),
                               offset=initial_offset+trained, initial_optimizer_step=initial_optimizer_step,
                               cpu_rng=torch.get_rng_state(), mps_rng=torch.mps.get_rng_state() if device == 'mps' else None,
                               history=history, best=best, bad_windows=bad_windows))
            if protect:
                checkpoint.protect(run_path)
            last_save = time.monotonic()

        def status(**extra):
            snapshot = campaign.snapshot()
            rate = trained/max(snapshot['active_seconds'], 1e-9)
            values = dict(snapshot, stage='own-base optimizer ablation', branch=spec['branch'],
                          timestamp=time.time(), target_tokens=spec['target_tokens'],
                          source_offset=initial_offset+trained, initial_source_offset=initial_offset,
                          branch_trained_tokens=trained, optimizer_step=initial_optimizer_step+step,
                          parent_endpoint_ce=receipt['baseline_ce'],
                          end_to_end_targets_per_second=rate,
                          estimated_remaining_active_hours=snapshot['remaining_tokens']/rate/3600 if rate else None,
                          reason=campaign.ledger.get('reason', ''), **extra)
            atomic_status(run_path/'status.json', values)
            return values

        try:
            if not resume:
                save()  # Rolling initial checkpoint; only the endpoint is protected.
            while True:
                campaign.check()
                ending = trained >= spec['target_tokens'] or campaign.snapshot()['remaining_tokens'] < effective
                if (trained in milestones or ending) and not any(h['trained_tokens'] == trained for h in history):
                    losses = document_losses(model, corpus, campaign.check)
                    row = dict(step=step, trained_tokens=trained, source_offset=initial_offset+trained,
                               optimizer_step=initial_optimizer_step+step,
                               document_losses=losses, mean_ce=float(np.mean(losses)))
                    next_bad = bad_windows
                    if best is not None:
                        row['versus_best'] = compare_losses(losses, best['document_losses'])
                        next_bad = bad_windows+1 if row['versus_best']['materially_worse'] else 0
                    next_best = dict(row) if best is None or row['mean_ce'] < best['mean_ce'] else best
                    row['diagnostics'] = language_diagnostics(model, tokenizer, diagnostics, campaign.check, completions=True)
                    history, best, bad_windows = history+[row], next_best, next_bad
                    atomic_status(run_path/'validation.json', history)
                    save()  # Evaluations do not accumulate protected 1.4GiB artifacts.
                    status(validation_ce=row['mean_ce'], context_pair_accuracy=row['diagnostics']['pair_accuracy'])
                if bad_windows >= 2:
                    repeated = document_losses(model, corpus, campaign.check)
                    if compare_losses(repeated, best['document_losses'])['materially_worse']:
                        campaign.finish('diverged', 'two successive material regressions confirmed')
                        break
                if ending:
                    save(protect=True)
                    campaign.finish('completed', 'bounded optimizer comparison ended; capability not established')
                    break
                if time.monotonic()-last_save >= 600:
                    save()
                if campaign.snapshot()['remaining_lease_seconds'] < 20:
                    raise CampaignStop('paused-lease', 'lease checkpoint margin reached')
                campaign.reserve(effective)
                model.train()
                opt.zero_grad(set_to_none=True)
                lr = learning_rate(trained, spec['scheduler'])
                for group in opt.param_groups:
                    group['lr'] = lr
                losses = torch.zeros((), device=device)
                for offset in range(initial_offset+trained, initial_offset+trained+effective, length*batch):
                    campaign.check()
                    rows = corpus.row('train', offset, length, batch)
                    with precision(spec['bf16'] and device == 'mps'):
                        logits = model(rows[:, :-1])
                        loss = F.cross_entropy(logits.flatten(0, 1), rows[:, 1:].flatten(), reduction='sum')/effective
                    loss.backward()
                    losses += loss.detach()
                norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
                opt.step()
                if device == 'mps':
                    torch.mps.synchronize()
                value = float(losses.item())
                if not math.isfinite(value):
                    raise ValueError('nonfinite training loss')
                step += 1
                trained += effective
                campaign.commit(step, trained)
                values = status(train_ce=value, gradient_norm=float(norm.item()), lr=lr)
                if step % 10 == 0:
                    with (run_path/'metrics.jsonl').open('a') as stream:
                        stream.write(json.dumps(values, allow_nan=False)+'\n')
        except (CampaignStop, KeyboardInterrupt) as error:
            if campaign.pending == 0:
                try:
                    save()
                except (OSError, RuntimeError) as save_error:
                    atomic_status(run_path/'pause-save-error.json', dict(error=str(save_error)))
            campaign.finish(error.state if isinstance(error, CampaignStop) else 'interrupted', str(error))
        except Exception as error:
            campaign.finish('failed', f'{type(error).__name__}: {error}')
            raise
        finally:
            status()
        return campaign.ledger['state']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path)
    parser.add_argument('run', type=Path)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    print(train(args.spec, args.run, resume=args.resume), flush=True)
