"""Single-writer own-base trainer. No provisioning, budget expansion or data replay.

Campaign schema1 binds ordered admitted train/validation shard manifests and an
admission evidence receipt. A launcher must reserve a bounded cloud lease first;
--deadline-utc is a checkpoint/exit deadline, NOT a substitute for provider cleanup.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from datetime import datetime

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloud_training.nano_benchmark import BATCH, HORIZON, PINNED_REVISION, atomic_json, schedule, deterministic_attention
from cloud_training.nano_data import PackedRows, sha256_file

MILESTONES = (1_000_000_000, 3_000_000_000, 6_000_000_000, 10_000_000_000)


def evaluate_entries(entries, evaluate_one, should_stop):
    """Explicit completeness prevents a lease boundary from skipping dev shards."""
    results = []
    for entry in entries:
        if should_stop():
            break
        results.append(evaluate_one(entry))
    return {'complete': len(results) == len(entries), 'shards': results,
            'expected_shards': len(entries)}


def next_evaluation(current, targets, interval, result):
    return ((targets // interval + 1) * interval if result['complete']
            else min(current, targets))


def numerical_identity(torch, *, attention_deterministic):
    return {'cuda': torch.version.cuda, 'gpu': torch.cuda.get_device_name(),
            'sm': list(torch.cuda.get_device_capability()),
            'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
            'deterministic_attention': attention_deterministic,
            'float32_matmul_precision': torch.get_float32_matmul_precision(),
            'cublas_workspace_config': os.environ.get('CUBLAS_WORKSPACE_CONFIG'),
            'cudnn_deterministic': torch.backends.cudnn.deterministic,
            'cudnn_benchmark': torch.backends.cudnn.benchmark,
            'cudnn_allow_tf32': torch.backends.cudnn.allow_tf32}


def read_campaign(path):
    path = Path(path).resolve()
    m = json.loads(path.read_text())
    if m.get('schema') != 1 or m.get('training_admitted') is not True:
        raise ValueError('A reviewed admitted campaign is required')
    if (m.get('sequence_length'), m.get('vocab_size')) != (2048, 32768):
        raise ValueError('Campaign context/vocabulary differs from recipe')
    evidence = m.get('admission', {})
    receipt = path.parent / evidence.get('receipt', '')
    if not receipt.is_file() or sha256_file(receipt) != evidence.get('sha256'):
        raise ValueError('Missing or changed campaign admission receipt')
    evidence_doc = json.loads(receipt.read_text())
    if evidence_doc.get('training_admitted') is not True or evidence_doc.get('tokenizer_sha256') != m.get('tokenizer_sha256'):
        raise ValueError('Admission receipt did not admit this tokenizer')
    bound_shards = [e['manifest_sha256'] for key in ('train','validation') for e in m.get(key, [])]
    if evidence_doc.get('shard_manifest_sha256') != bound_shards:
        raise ValueError('Admission receipt does not bind the ordered shard manifests')
    seen = set()
    for split, key in [('train', 'train'), ('validation', 'validation')]:
        entries = m.get(key)
        if not isinstance(entries, list) or not entries:
            raise ValueError(f'Missing ordered {key} shards')
        for entry in entries:
            directory = (path.parent / entry['directory']).resolve()
            if sha256_file(directory / 'manifest.json') != entry['manifest_sha256']:
                raise ValueError('Changed shard manifest')
            reader = PackedRows(directory, expected_tokenizer_sha256=m['tokenizer_sha256'], expected_split=split)
            sm = reader.manifest
            if sm.get('training_admitted') is not True:
                raise ValueError('Shard has integrity only, not training admission')
            if (sm['sequence_length'], sm['vocab_size']) != (2048, 32768):
                raise ValueError('Shard dimensions differ from campaign')
            if sm['sha256'] in seen:
                raise ValueError('Duplicate shard or train/validation overlap')
            seen.add(sm['sha256'])
            entry['_directory'] = str(directory)
            entry['_rows'] = sm['rows']
    m['_sha256'] = sha256_file(path)
    return m


class CampaignRows:
    """Finite, exact ordered stream; assembles batches across shard boundaries."""
    def __init__(self, campaign):
        self.campaign = campaign
        self.entries = campaign['train']
        self.total_rows = sum(e['_rows'] for e in self.entries)
        self.shard = 0
        self.global_row = 0
        self.reader = self._open(0)

    def _open(self, i):
        if i == len(self.entries):
            return None
        e = self.entries[i]
        if sha256_file(Path(e['_directory']) / 'manifest.json') != e['manifest_sha256']:
            raise ValueError('Shard manifest changed after preflight')
        return PackedRows(e['_directory'], expected_tokenizer_sha256=self.campaign['tokenizer_sha256'],
                          expected_split='train')

    @property
    def remaining(self):
        return self.total_rows - self.global_row

    def state_dict(self):
        return {'schema': 1, 'campaign_sha256': self.campaign['_sha256'], 'shard': self.shard,
                'global_row': self.global_row, 'reader': self.reader.state_dict() if self.reader else None}

    def load_state_dict(self, state):
        if state.get('schema') != 1 or state.get('campaign_sha256') != self.campaign['_sha256']:
            raise ValueError('Cursor belongs to another campaign')
        shard = state.get('shard')
        if type(shard) is not int or not 0 <= shard <= len(self.entries):
            raise ValueError('Invalid shard cursor')
        reader = self._open(shard)
        if reader:
            reader.load_state_dict(state['reader'])
        elif state['reader'] is not None:
            raise ValueError('Unexpected reader after EOF')
        expected = sum(e['_rows'] for e in self.entries[:shard]) + (reader.next_row if reader else 0)
        if state.get('global_row') != expected:
            raise ValueError('Inconsistent global cursor')
        self.shard, self.reader, self.global_row = shard, reader, expected

    def read(self, rows):
        if type(rows) is not int or rows < 1:
            raise ValueError('Positive batch rows required')
        if rows > self.remaining:
            raise StopIteration('Finite campaign exhausted; replay prohibited')
        xs, ys = [], []
        while rows:
            available = self.reader.manifest['rows'] - self.reader.next_row
            take = min(rows, available)
            if take:
                x, y = self.reader.read(take)
                xs.extend(x); ys.extend(y)
                self.global_row += take; rows -= take
            if self.reader.next_row == self.reader.manifest['rows']:
                self.shard += 1; self.reader = self._open(self.shard)
        return xs, ys


def lease_stop_step(start_step, max_updates=None):
    if type(start_step) is not int or not 0 <= start_step <= HORIZON:
        raise ValueError('Invalid starting update')
    if max_updates is not None and (type(max_updates) is not int or max_updates < 1):
        raise ValueError('Positive bounded-pilot update count required')
    return HORIZON if max_updates is None else min(HORIZON, start_step + max_updates)


def crossed_milestones(before, after):
    return [t for t in MILESTONES if before < t <= after]


def validate_lease_seconds(seconds, reserve_seconds):
    if not 0 < reserve_seconds < seconds <= 21600:
        raise ValueError('Lease deadline must leave checkpoint reserve and be <=6 hours away')


def deadline_timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Deadline must include timezone')
    return parsed.timestamp()



class CloudJournal:
    """Authoritative remote journal with generation-checked replacement.

    Missing journals on resume and interrupted upload/prune intents fail closed.
    No inference from local disk state, bucket listings or automatic reset.
    """
    def __init__(self, path, *, campaign_prefix, identity, resume_step=None, timeout=90):
        from cloud_training.nano_retention import _prefix, _read
        self.path = Path(path)
        self.prefix = _prefix(campaign_prefix)
        self.uri = self.prefix + '/retention-journal.json'
        self.identity = identity
        self.timeout = timeout
        self.deadline = time.monotonic() + timeout
        self.generation = '0'
        if resume_step is None:
            if self.path.exists():
                raise ValueError('Fresh campaign cannot replace an existing local journal')
            atomic_json(self.path, {'schema': 1, 'campaign_prefix': self.prefix,
                                   'identity': identity, 'lease_phase': 'ready', 'entries': []})
            self.persist()  # generation=0 refuses an existing remote campaign
        else:
            generation, raw = self.remote_snapshot()
            value = json.loads(raw)
            if value.get('identity') != identity or value.get('lease_phase') != 'ready':
                raise ValueError('Remote journal identity mismatch or interrupted operation; reconcile explicitly')
            atomic_json(self.path, value)
            journal = _read(self.path, self.prefix)
            if any(e['state'] == 'deleting' for e in journal['entries']):
                raise ValueError('Interrupted remote deletion requires reconciliation')
            matches = [e for e in journal['entries'] if e['state'] == 'committed'
                       and e['receipt']['step'] == resume_step and e['receipt']['identity'] == identity]
            if not matches:
                raise ValueError('Resume checkpoint is absent from authoritative committed journal')
            self.generation = generation
        self.deadline = None

    def command(self, arguments):
        remaining = self.timeout if self.deadline is None else min(self.timeout, self.deadline-time.monotonic())
        if remaining <= 0:
            raise TimeoutError('Retention journal operation deadline expired')
        return subprocess.run(['gcloud', 'storage', *arguments, '--quiet'], check=True,
                              capture_output=True, text=True, timeout=remaining).stdout

    def remote_snapshot(self):
        first = json.loads(self.command(['objects','describe',self.uri,'--format=json']))
        generation = str(first.get('generation',''))
        if not generation.isdigit():
            raise ValueError('Remote journal generation missing')
        raw = self.command(['cat',self.uri])
        after = json.loads(self.command(['objects','describe',self.uri,'--format=json']))
        if str(after.get('generation','')) != generation:
            raise ValueError('Concurrent remote journal modification')
        return generation, raw

    def persist(self):
        raw = self.path.read_text()
        self.command(['cp',str(self.path),self.uri,'--if-generation-match='+self.generation])
        generation, downloaded = self.remote_snapshot()
        if downloaded != raw:
            raise ValueError('Remote journal readback differs; do not prune')
        self.generation = generation

    def set_phase(self, phase, **details):
        value = json.loads(self.path.read_text())
        value['lease_phase'] = phase
        value['operation'] = details
        atomic_json(self.path,value)
        self.persist()

    def prune(self, *, timeout=180):
        from cloud_training.nano_retention import apply_retention
        # Persist intent before any destructive operation. A killed VM therefore
        # cannot resume from a stale ready journal and repeat a partial deletion.
        preview = apply_retention(self.path,campaign_prefix=self.prefix,execute=False)
        if not preview['candidates']:
            return preview
        self.set_phase('retention_in_progress',candidates=preview['candidates'])
        report = apply_retention(self.path,campaign_prefix=self.prefix,execute=True,timeout=timeout)
        self.set_phase('ready')
        return report


def run(args, campaign):
    if args.deterministic:
        os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    import torch
    from cloud_training.nano_checkpoint import save_bundle, load_bundle, capture_rng, restore_rng_state
    from cloud_training.nano_eval import evaluate_packed
    from cloud_training.l4_recovery_check import upload_bundle
    repo = Path(args.repo).resolve()
    revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != PINNED_REVISION or subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain'], text=True).strip():
        raise ValueError('Pinned clean upstream checkout required')
    if not torch.__version__.startswith('2.9.') or not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise ValueError('Pinned torch2.9 CUDA BF16 runtime required')
    sys.path.insert(0, str(repo))
    import nanochat.flash_attention as attention
    if args.kernel_path:
        from kernels import get_local_kernel
        attention._fa3 = get_local_kernel(Path(args.kernel_path), 'flash_attn3').flash_attn_interface
        attention.HAS_FA3 = True; attention.USE_FA3 = attention._resolve_use_fa3()
    if args.deterministic:
        torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
    attention_deterministic = bool(args.deterministic_attention or (args.deterministic and attention.USE_FA3))
    if attention_deterministic:
        deterministic_attention(attention)
    from nanochat.gpt import GPT, GPTConfig
    from nanochat.common import COMPUTE_DTYPE
    if COMPUTE_DTYPE != torch.bfloat16:
        raise ValueError('BF16 activation dtype required')
    torch.set_num_threads(args.cpu_threads)
    torch.manual_seed(args.seed); torch.cuda.manual_seed_all(args.seed)
    width = args.depth * 64
    cfg = GPTConfig(sequence_len=2048, vocab_size=32768, n_layer=args.depth, n_embd=width,
                    n_head=width//128, n_kv_head=width//128, window_pattern='SSSL')
    with torch.device('meta'):
        model = GPT(cfg)
        reference = GPT(GPTConfig(sequence_len=2048, vocab_size=32768, n_layer=12,
                                  n_embd=768, n_head=6, n_kv_head=6, window_pattern='SSSL'))
        ref_counts = reference.num_scaling_params()
    del reference
    model.to_empty(device='cuda'); model.init_weights(); model.train()
    counts = model.num_scaling_params()
    if counts['total'] != {12: 286261730, 16: 536871738}[args.depth]:
        raise ValueError('Unexpected parameter count')
    decay = .28 * (ref_counts['transformer_matrices'] + ref_counts['lm_head']) / (counts['transformer_matrices'] + counts['lm_head'])
    optimizer = model.setup_optimizer(unembedding_lr=.008, embedding_lr=.3, scalar_lr=.5,
                                      matrix_lr=.02, weight_decay=decay)
    from cloud_training.nano_probes import configuration as probe_configuration, load_tokenizer, run_probes
    probe_tokenizer = load_tokenizer(args.tokenizer_dir, campaign['tokenizer_sha256']) if args.tokenizer_dir else None
    reader = CampaignRows(campaign)
    source_files = ['nano_train.py', 'nano_benchmark.py', 'nano_checkpoint.py', 'nano_data.py', 'nano_eval.py', 'nano_retention.py', 'l4_recovery_check.py', 'nano_probes.py']
    identity = {'phase': 'base', 'initialization': 'own_random', 'revision': revision, 'adapter_hashes': {f: sha256_file(Path(__file__).parent / f) for f in source_files},
                'config': vars(cfg), 'tokenizer_sha256': campaign['tokenizer_sha256'], 'campaign_sha256': campaign['_sha256'], 'torch': torch.__version__,
                'numerical_mode': numerical_identity(torch, attention_deterministic=attention_deterministic),
                'probes': probe_configuration(probe_tokenizer is not None),
                'batch_tokens': BATCH, 'microbatch': args.microbatch, 'horizon_updates': HORIZON,
                'seed': args.seed, 'eval_every_tokens': args.eval_every_tokens, 'eval_tokens_per_shard': args.eval_tokens_per_shard, 'attention': 'fa3' if attention.USE_FA3 else 'sdpa', 'kernel_sha256': args.kernel_sha}
    step = 0
    next_eval = args.eval_every_tokens
    milestone_steps = []
    if args.resume:
        restored = load_bundle(args.resume, model=model, optimizer=optimizer, expected_identity=identity)
        if (restored.get('verification', {}).get('exact_state_verified') is not True
            or restored['verification'].get('rng') is not True):
            raise ValueError('Production resume requires exact restored state and RNG verification')
        step = restored['metadata']['step']
        reader.load_state_dict(restored['data_state']['reader'])
        if restored['data_state']['next_batch'] != step or reader.global_row != step * (BATCH // 2048):
            raise ValueError('Model step and exact data cursor disagree')
        next_eval = restored['metadata']['loop']['next_eval']
        milestone_steps = restored['metadata']['loop']['milestone_steps']
    compiled = torch.compile(model, dynamic=False)
    out = Path(args.output).resolve(); out.mkdir(parents=True, exist_ok=True)
    journal = CloudJournal(out/'retention-journal.json', campaign_prefix=args.backup_prefix,
                           identity=identity, resume_step=step if args.resume else None)
    lease_start_step = step
    lease_end_step = lease_stop_step(step,args.max_updates)
    stop_requested = []
    def stop(signum, frame):
        stop_requested.append(signum)
    for sig in (signal.SIGTERM, signal.SIGINT): signal.signal(sig, stop)
    cutoff = deadline_timestamp(args.deadline_utc) - args.checkpoint_reserve_seconds
    if cutoff <= time.time():
        raise ValueError('Lease lacks checkpoint reserve')
    def should_stop():
        return bool(stop_requested) or time.time() >= cutoff
    last_save = time.monotonic()
    last_checkpoint_step = step if args.resume else None
    status = {'status': 'running', 'identity': identity, 'parameters': counts['total'], 'step': step,
              'targets': step * BATCH, 'run_mode': 'admitted_bounded_pilot' if args.max_updates else 'admitted_campaign',
              'lease_start_step': lease_start_step, 'lease_end_step': lease_end_step, 'planned_horizon_updates': HORIZON,
              'journal_uri': journal.uri, 'budget_enforcement': 'External reserved lease/provider stop required'}
    def checkpoint(reason):
        nonlocal last_save, last_checkpoint_step
        if last_checkpoint_step == step:
            return
        journal.deadline = time.monotonic() + min(args.checkpoint_reserve_seconds, deadline_timestamp(args.deadline_utc)-time.time())
        path = out / f'step-{step:08d}'
        save_bundle(path, model=model, optimizer=optimizer,
                    metadata={'step': step, 'identity': identity, 'reason': reason,
                              'loop': {'next_eval': next_eval, 'milestone_steps': milestone_steps}},
                    data_state={'exact': True, 'next_batch': step, 'reader': reader.state_dict()})
        journal.set_phase('checkpoint_upload_in_progress', step=step)
        receipt = upload_bundle(path, remote_prefix=args.backup_prefix,
                                timeout=min(args.checkpoint_reserve_seconds,journal.deadline-time.monotonic()))
        from cloud_training.nano_retention import record_upload
        pins = ['milestone'] if step in milestone_steps else ['final'] if step == HORIZON else []
        record_upload(journal.path, receipt, campaign_prefix=args.backup_prefix, pins=pins)
        journal.set_phase('ready')
        # Prune only when ample lease time remains; the upload is already durable.
        if deadline_timestamp(args.deadline_utc)-time.time() > args.checkpoint_reserve_seconds and journal.deadline-time.monotonic()>60:
            status['retention'] = journal.prune(timeout=min(180,args.checkpoint_reserve_seconds,max(1,journal.deadline-time.monotonic()-30)))
        else:
            status['retention'] = {'status':'deferred_until_next_lease'}
        status['last_checkpoint'] = {'path': str(path), 'upload': receipt, 'step': step}
        atomic_json(out / 'progress.json', status)
        journal.deadline = None
        last_save = time.monotonic(); last_checkpoint_step = step
        # Only remove this trainer's verified local periodic checkpoints, retain milestones/latest2.
        from cloud_training.nano_checkpoint import validate_bundle
        import shutil
        paths = sorted(out.glob('step-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'))
        for old in paths[:-2]:
            old_step = int(old.name.split('-')[1])
            if old_step not in milestone_steps:
                validate_bundle(old); shutil.rmtree(old)
    def evaluate():
        def one(entry):
            tokens = min(args.eval_tokens_per_shard, entry['_rows']*2048)
            return evaluate_packed(model, entry['_directory'],
                tokenizer_sha256=campaign['tokenizer_sha256'], token_budget=tokens,
                batch_rows=args.microbatch, device=next(model.parameters()).device, actual_revision=revision,
                expected_manifest_sha256=entry['manifest_sha256'])
        return evaluate_entries(campaign['validation'], one, should_stop)
    # Retry a partially completed scheduled evaluation before another update.
    if args.resume and step * BATCH >= next_eval and not should_stop():
        status['validation'] = evaluate()
        next_eval = next_evaluation(next_eval, step * BATCH, args.eval_every_tokens, status['validation'])
    if args.max_updates and not should_stop():
        status['pilot_validation_start'] = evaluate()
    # Initial exact random-state recovery before any retained update.
    if not args.resume:
        checkpoint('initial_random_state')
    accumulation = BATCH // (args.microbatch * 2048)
    stop_reason = 'horizon_complete' if lease_end_step == HORIZON else 'pilot_update_limit'
    while step < lease_end_step:
        if should_stop():
            stop_reason = 'signal_or_lease_deadline'; break
        if reader.remaining < BATCH // 2048:
            stop_reason = 'finite_data_exhausted'; break
        before_cursor, before_rng = reader.state_dict(), capture_rng()
        torch.cuda.synchronize(); tick = time.monotonic()
        losses = []
        aborted = False
        for _ in range(accumulation):
            if should_stop():
                aborted = True; break
            x, y = reader.read(args.microbatch)
            x = torch.tensor(x, dtype=torch.int64, device='cuda')
            y = torch.tensor(y, dtype=torch.int64, device='cuda')
            loss = compiled(x, y)
            losses.append(loss.detach())
            (loss / accumulation).backward()
        if aborted:
            model.zero_grad(set_to_none=True)
            reader.load_state_dict(before_cursor); restore_rng_state(before_rng)
            stop_reason = 'signal_or_lease_deadline_mid_accumulation'; break
        average = torch.stack(losses).mean().item()
        if not math.isfinite(average):
            model.zero_grad(set_to_none=True)
            reader.load_state_dict(before_cursor); restore_rng_state(before_rng)
            stop_reason = 'nonfinite_loss'; break
        try:
            torch.nn.utils.get_total_norm([p.grad for p in model.parameters() if p.grad is not None], error_if_nonfinite=True)
        except RuntimeError:
            model.zero_grad(set_to_none=True)
            reader.load_state_dict(before_cursor); restore_rng_state(before_rng)
            stop_reason = 'nonfinite_gradient'; break
        lrm, momentum, wd = schedule(step)
        for group in optimizer.param_groups:
            group['lr'] = group['initial_lr'] * lrm
            if group['kind'] == 'muon': group['momentum'] = momentum; group['weight_decay'] = decay * wd
        optimizer.step(); model.zero_grad(set_to_none=True)
        torch.cuda.synchronize()
        old_targets = step * BATCH; step += 1
        milestones = crossed_milestones(old_targets, step * BATCH)
        if milestones: milestone_steps.append(step)
        status.update(step=step, targets=step*BATCH, train_loss=average,
                      update_seconds=time.monotonic()-tick, peak_allocated_bytes=torch.cuda.max_memory_allocated())
        status['tokens_per_second_last_update'] = BATCH/status['update_seconds']
        if step*BATCH >= next_eval or milestones or (args.max_updates and step == lease_end_step):
            status['validation'] = evaluate()
            next_eval = next_evaluation(next_eval, step*BATCH, args.eval_every_tokens, status['validation'])
        if milestones and probe_tokenizer is not None:
            probe_result = run_probes(model, probe_tokenizer, should_stop=should_stop)
            probe_result.update(step=step, targets=step*BATCH, milestones=milestones)
            atomic_json(out / f'base-probes-step-{step:08d}.json', probe_result)
            status['base_probes'] = probe_result
        with (out / 'updates.jsonl').open('a') as log:
            log.write(json.dumps(status, allow_nan=False)+'\n'); log.flush()
        atomic_json(out / 'progress.json', status)
        if milestones or time.monotonic()-last_save >= args.checkpoint_seconds:
            checkpoint('milestone' if milestones else 'periodic')
    checkpoint(stop_reason)
    status.update(status='complete' if step == HORIZON else 'bounded_pilot_complete' if stop_reason=='pilot_update_limit' else 'stopped', reason=stop_reason,
                  step=step, targets=step*BATCH, finite_remaining_rows=reader.remaining)
    atomic_json(out / 'result.json', status)
    return 0 if stop_reason in ('horizon_complete','pilot_update_limit','signal_or_lease_deadline','signal_or_lease_deadline_mid_accumulation') else 2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign', required=True)
    p.add_argument('--validate-only', action='store_true')
    p.add_argument('--repo'); p.add_argument('--output'); p.add_argument('--backup-prefix')
    p.add_argument('--deadline-utc'); p.add_argument('--resume')
    p.add_argument('--max-updates', type=int, help='Bound this admitted pilot/lease without resetting the global schedule')
    p.add_argument('--depth', type=int, choices=(12,16), default=16)
    p.add_argument('--microbatch', type=int, default=4)
    p.add_argument('--cpu-threads', type=int, default=4)
    p.add_argument('--kernel-path'); p.add_argument('--kernel-sha')
    p.add_argument('--deterministic', action='store_true', help='Strict PyTorch algorithms and deterministic FA3 backward')
    p.add_argument('--deterministic-attention', action='store_true', help='Deterministic staged FA3 backward')
    p.add_argument('--tokenizer-dir', help='Enable fixed milestone-only base probes with the final own tokenizer')
    p.add_argument('--seed', type=int, default=103)
    p.add_argument('--checkpoint-seconds', type=int, default=900)
    p.add_argument('--checkpoint-reserve-seconds', type=int, default=300)
    p.add_argument('--eval-every-tokens', type=int, default=250_000_000)
    p.add_argument('--eval-tokens-per-shard', type=int, default=1_048_576)
    a = p.parse_args()
    campaign = read_campaign(a.campaign)
    if a.validate_only:
        print(json.dumps({'campaign_sha256': campaign['_sha256'], 'training_admitted': True,
                          'train_targets':sum(e['_rows'] for e in campaign['train'])*2048},indent=2)); return 0
    if not all((a.repo,a.output,a.backup_prefix,a.deadline_utc)):
        p.error('Training requires repo,output,backup-prefix,deadline-utc')
    if a.max_updates is not None and a.max_updates < 1:
        p.error('--max-updates must be positive')
    if a.microbatch<1 or BATCH%(a.microbatch*2048) or a.cpu_threads<1:
        p.error('Invalid microbatch/CPU threads')
    if min(a.checkpoint_seconds,a.checkpoint_reserve_seconds,a.eval_every_tokens,a.eval_tokens_per_shard)<1 or a.eval_tokens_per_shard%2048:
        p.error('Positive intervals and whole-row eval budget required')
    seconds=deadline_timestamp(a.deadline_utc)-time.time()
    try:
        validate_lease_seconds(seconds, a.checkpoint_reserve_seconds)
    except ValueError as exc:
        p.error(str(exc))
    if bool(a.kernel_path)!=bool(a.kernel_sha):
        p.error('Pinned kernel path and SHA must be supplied together')
    os.environ.setdefault('HF_HUB_OFFLINE','1')
    os.environ.setdefault('WANDB_MODE','disabled')
    os.environ.setdefault('PYTORCH_ALLOC_CONF','expandable_segments:True')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    with (out/'.writer.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return run(a,campaign)


if __name__=='__main__':
    raise SystemExit(main())
