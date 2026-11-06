"""Substantial, resumable next-token pretraining of our own GPT-2 lineage."""
import argparse
from contextlib import nullcontext
from dataclasses import asdict
import json
import math
from pathlib import Path
import time

import numpy as np
import torch
from torch.nn import functional as F

import checkpoint
from base_run_control import Campaign, CampaignStop
from gpt2 import Config, GPT2
from pretrain import atomic_status
from pretrained_base import continuation_parent, load_base
from tokenizer import ASSETS, load
from train import optimizer_for

ROOT = Path(__file__).resolve().parent


def precision(enabled):
    return torch.autocast('mps', dtype=torch.bfloat16) if enabled else nullcontext()


def learning_rate(tokens, schedule):
    warmup, decay, total = (schedule[k] for k in ('warmup_tokens', 'decay_start_tokens', 'horizon_tokens'))
    if tokens < warmup:
        return schedule['peak_lr'] * max(tokens, 1) / warmup
    fraction = min(1., max(0., (tokens-decay) / (total-decay)))
    return schedule['peak_lr'] * (schedule['end_fraction'] + (1-schedule['end_fraction']) * (1+math.cos(math.pi*fraction))/2)


class Corpus:
    def __init__(self, directory, manifest_sha, block_sha, length, microbatch, device="mps"):
        self.device = device
        self.directory, self.length, self.microbatch = Path(directory), length, microbatch
        if checkpoint.checksum(self.directory/'manifest.json') != manifest_sha:
            raise ValueError('corpus identity mismatch')
        manifest = json.loads((self.directory/'manifest.json').read_text())
        self.arrays = {}
        for split in ('train', 'validation'):
            key = 'fineweb-'+split
            path = self.directory/(key+'.u16')
            meta = manifest['shards'][key]
            if checkpoint.checksum(path) != meta['sha256']:
                raise ValueError('corpus shard checksum mismatch')
            data = np.memmap(path, mode='r', dtype='<u2')
            if len(data) != meta['tokens'] or np.any(data > 50256):
                raise ValueError('invalid token shard')
            self.arrays[split] = data
        block_path = self.directory/'validation-blocks.json'
        if checkpoint.checksum(block_path) != block_sha:
            raise ValueError('validation selection changed')
        self.blocks = json.loads(block_path.read_text())
        if isinstance(self.blocks, dict):
            self.blocks = self.blocks['blocks']
        if len(self.blocks) < 128:
            raise ValueError('need at least 128 document-level validation blocks')

    def row(self, split, offset, length, batch=1):
        data = self.arrays[split]
        if offset < 0 or offset+batch*length >= len(data):
            raise ValueError('fresh corpus positions exhausted')
        rows = np.stack([data[offset+i*length:offset+(i+1)*length+1] for i in range(batch)]).astype(np.int64)
        return torch.from_numpy(rows).to(self.device)


@torch.inference_mode()
def document_losses(model, corpus, check):
    result = []
    model.eval()
    # Fixed FP32 validation makes precision/layout comparisons interpretable.
    for block in corpus.blocks:
        check()
        offset = block.get('offset', block.get('start'))
        if block.get('tokens', block.get('length', block.get('max_length', 0))) < corpus.length+1:
            raise ValueError('validation window cannot fit one document')
        row = corpus.row('validation', offset, corpus.length)
        loss = F.cross_entropy(model(row[:, :-1]).flatten(0, 1), row[:, 1:].flatten())
        result.append(float(loss.item()))
    if not all(math.isfinite(x) for x in result):
        raise ValueError('nonfinite validation')
    return result


def compare_losses(current, best):
    changes = np.asarray(current)-np.asarray(best)
    se = float(changes.std(ddof=1)/math.sqrt(len(changes)))
    delta = float(changes.mean())
    return dict(change_nats=delta, paired_standard_error=se,
                materially_worse=delta > max(.20, 5*se))


@torch.inference_mode()
def language_diagnostics(model, tokenizer, spec, check, *, completions):
    model.eval()
    results = {'pairs': [], 'completions': []}
    device = next(model.parameters()).device
    for pair in spec['pairs']:
        row = {'id': pair['id'], 'members': []}
        for member in pair['members']:
            prefix = tokenizer.encode(member['prefix']).ids
            scores = []
            summed_scores = []
            for answer in pair['choices']:
                ending = tokenizer.encode(answer).ids
                ids = prefix+ending
                if not prefix or not ending or len(ids) > model.positions.num_embeddings:
                    raise ValueError('diagnostic context exceeds model capacity')
                x = torch.tensor([ids[:-1]], device=device)
                mask = torch.zeros_like(x, dtype=torch.bool)
                mask[:, len(prefix)-1:] = True
                check()
                logits = model(x, prediction_mask=mask)
                loss = F.cross_entropy(logits, torch.tensor(ending, device=device))
                scores.append(-float(loss.item()))
                summed_scores.append(scores[-1]*len(ending))
            if not all(math.isfinite(score) for score in scores):
                raise ValueError('nonfinite diagnostic likelihood')
            selected = int(np.argmax(scores))
            correct = member['correct']
            probabilities = torch.softmax(torch.tensor(scores, dtype=torch.float64), dim=0).tolist()
            row['members'].append(dict(scores=scores, summed_log_probabilities=summed_scores,
                                       choice_probabilities=probabilities, selected=selected,
                                       correct=scores[correct] > scores[1-correct]))
        row['correct'] = all(m['correct'] for m in row['members'])
        results['pairs'].append(row)
    results['pair_accuracy'] = sum(r['correct'] for r in results['pairs'])/len(results['pairs'])
    if completions:
        for prefix in spec['prefixes']:
            text = prefix['text'] if isinstance(prefix, dict) else prefix
            ids = tokenizer.encode(text).ids
            original = len(ids)
            for _ in range(48):
                check()
                token = int(model(torch.tensor([ids], device=device))[0, -1].argmax().item())
                if token == 50256:
                    break
                ids.append(token)
            results['completions'].append(dict(prefix=text, generated=tokenizer.decode(ids[original:])))
    return results


def train(spec_path, run_path, *, resume=False, device="mps", model_config=None):
    spec = json.loads(spec_path.read_text())
    config = model_config or Config()
    if device not in ("cpu", "mps"):
        raise ValueError("unsupported training device")
    parent = continuation_parent(spec, config)
    if parent is None:
        raise ValueError('this protocol requires the explicit verified own pre-SFT base')
    length, batch, effective = spec['length'], spec['microbatch'], spec['targets_per_update']
    if length not in (256, 512, 1024) or batch < 1 or effective % (length*batch):
        raise ValueError('invalid training layout')
    if not 0 < spec['target_tokens'] <= 100_000_000 or spec['target_tokens'] % effective:
        raise ValueError('invalid bounded target budget')
    if spec['scheduler']['horizon_tokens'] != spec['target_tokens']:
        raise ValueError('scheduler horizon must be frozen to the target tranche')
    schedule = spec['scheduler']
    if (not all(math.isfinite(schedule[k]) for k in
                ('warmup_tokens', 'decay_start_tokens', 'horizon_tokens', 'peak_lr', 'end_fraction'))
            or not 0 < schedule['warmup_tokens'] <= schedule['decay_start_tokens'] < schedule['horizon_tokens']
            or not 0 < schedule['peak_lr'] <= 6e-5
            or not 0 <= schedule['end_fraction'] <= 1):
        raise ValueError('invalid frozen learning-rate schedule')
    for name, expected in spec.get('code_sha256', {}).items():
        file = (ROOT/name).resolve()
        if file.parent != ROOT or checkpoint.checksum(file) != expected:
            raise ValueError(f'frozen code changed: {name}')
    corpus = Corpus(spec['corpus'], spec['manifest_sha256'], spec['validation_blocks_sha256'], length, batch, device=device)
    if len(corpus.arrays['train']) <= spec['target_tokens']:
        raise ValueError('insufficient unique corpus tokens')
    diagnostic_path = Path(spec['diagnostics'])
    if checkpoint.checksum(diagnostic_path) != spec['diagnostics_sha256']:
        raise ValueError('diagnostics changed')
    diagnostics = json.loads(diagnostic_path.read_text())
    identity = dict(seed=spec['seed'], model=asdict(config), tokenizer=ASSETS,
                    initialization=dict(mode='own_pretraining', path=parent['path'], sha256=parent['sha256'],
                                        random_lineage_root=parent['acceptance_report_sha256']),
                    corpus=dict(directory=spec['corpus'], manifest=spec['manifest_sha256'],
                                validation=spec['validation_blocks_sha256']),
                    scheduler=spec['scheduler'], protocol=spec, device=device, torch_version=str(torch.__version__),
                    code={name: checkpoint.checksum(ROOT/name) for name in
                          ('base_train.py', 'base_run_control.py', 'gpt2.py', 'train.py', 'guards.py',
                           'checkpoint.py', 'tokenizer.py', 'pretrained_base.py', 'pretrain.py')})
    torch.set_num_threads(1)
    with Campaign(run_path, identity, token_limit=spec['target_tokens'], active_seconds=spec['active_seconds'],
                  calendar_seconds=spec['calendar_seconds'], lease_seconds=spec['lease_seconds'], resume=resume) as campaign:
        torch.manual_seed(spec['seed'])
        model = GPT2(config).to(device)
        opt = optimizer_for(model)
        history, best, bad_windows = [], None, 0
        step, trained = 0, 0
        tokenizer = load()
        if resume:
            saved = campaign.load()
            model.load_state_dict(saved['model'])
            opt.load_state_dict(saved['optimizer'])
            torch.set_rng_state(saved['cpu_rng'])
            if device == 'mps':
                torch.mps.set_rng_state(saved['mps_rng'])
            step, trained = saved['step'], saved['trained_tokens']
            history, best, bad_windows = saved['history'], saved['best'], saved['bad_windows']
            if trained != step*effective or saved['offset'] != trained:
                raise ValueError('resume data cursor differs from optimizer progress')
            del saved
        else:
            model.load_state_dict(load_base(Path(parent['path']), parent['sha256'], terminal=parent))
        last_save = time.monotonic()
        milestones = sorted({0, spec['target_tokens']} | {
            math.ceil(t/effective)*effective for t in [1_000_000, 5_000_000]+list(range(10_000_000, spec['target_tokens'], 10_000_000))})

        def save(protect=False):
            nonlocal last_save
            campaign.save(dict(step=step, model=model.state_dict(), optimizer=opt.state_dict(), offset=trained,
                               cpu_rng=torch.get_rng_state(), mps_rng=torch.mps.get_rng_state() if device == 'mps' else None,
                               history=history, best=best, bad_windows=bad_windows))
            if protect:
                checkpoint.protect(run_path)
            last_save = time.monotonic()

        def status(**extra):
            snapshot = campaign.snapshot()
            rate = trained / max(snapshot['active_seconds'], 1e-9)
            remaining = snapshot['remaining_tokens']
            values = dict(snapshot, stage='own-base foundation pretraining', timestamp=time.time(),
                          target_tokens=spec['target_tokens'], data_cursor=trained,
                          inherited_pretraining_targets=parent['target_tokens'],
                          end_to_end_targets_per_second=rate,
                          estimated_remaining_active_hours=remaining/rate/3600 if rate > 0 else None,
                          reason=campaign.ledger.get('reason', ''), **extra)
            atomic_status(run_path/'status.json', values)
            return values

        if not resume:
            save()
        try:
            while True:
                campaign.check()
                ending = trained >= spec['target_tokens'] or campaign.snapshot()['remaining_tokens'] < effective
                if (trained in milestones or ending) and not any(h['trained_tokens'] == trained for h in history):
                    losses = document_losses(model, corpus, campaign.check)
                    row = dict(step=step, trained_tokens=trained, document_losses=losses,
                               mean_ce=float(np.mean(losses)))
                    next_bad_windows = bad_windows
                    if best is not None:
                        row['versus_best'] = compare_losses(losses, best['document_losses'])
                        next_bad_windows = bad_windows+1 if row['versus_best']['materially_worse'] else 0
                    next_best = dict(row) if best is None or row['mean_ce'] < best['mean_ce'] else best
                    row['diagnostics'] = language_diagnostics(model, tokenizer, diagnostics, campaign.check,
                                                              completions=True)
                    # Commit the complete evaluation as one optimizer-boundary
                    # state. Interrupted diagnostics leave all prior metrics intact.
                    history, best, bad_windows = history+[row], next_best, next_bad_windows
                    atomic_status(run_path/'validation.json', history)
                    # Retain baseline, stability review and milestone artifacts under the declared disk budget.
                    save(protect=True)
                    status(validation_ce=row['mean_ce'], context_pair_accuracy=row['diagnostics']['pair_accuracy'])
                # A resumed milestone checkpoint may still require confirmation.
                # Resolve that decision before any optimizer work or completion.
                if bad_windows >= 2:
                    repeated = document_losses(model, corpus, campaign.check)
                    if compare_losses(repeated, best['document_losses'])['materially_worse']:
                        campaign.finish('diverged', 'two consecutive material validation regressions confirmed')
                        break
                if trained >= spec['target_tokens'] or campaign.snapshot()['remaining_tokens'] < effective:
                    save(protect=True)
                    campaign.finish('completed', 'bounded token tranche ended; base quality judged separately')
                    break
                if time.monotonic()-last_save >= 600:
                    save()
                # End predictable leases at a committed optimizer boundary,
                # leaving time to save rather than losing work mid-update.
                if campaign.snapshot()['remaining_lease_seconds'] < 20:
                    raise CampaignStop('paused-lease', 'lease checkpoint margin reached')
                campaign.reserve(effective)
                model.train()
                opt.zero_grad(set_to_none=True)
                lr = learning_rate(trained+effective, spec['scheduler'])
                for group in opt.param_groups:
                    group['lr'] = lr
                losses = torch.zeros((), device=device)
                for offset in range(trained, trained+effective, length*batch):
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
