"""Bounded compute qualification; benchmark updates are NOT retained language training.

The parent process enforces a wall deadline. This never provisions a VM or uploads data.
Use with an independently bounded cloud lease; process timeout is not a billing stop.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

PINNED_REVISION = '92d63d4e8bb4df75c3b71618f31ddde2378b2bcd'
BATCH = 524288
HORIZON = 19074


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def schedule(step, horizon=HORIZON):
    warmdown = round(.65 * horizon)
    lr = ((step + 1) / 40 if step < 40 else 1.0 if step <= horizon - warmdown
          else (horizon - step) / warmdown * .95 + .05)
    momentum = (.85 + .12 * step / 400 if step < 400 else
                .97 * (1 - (step - (horizon - warmdown)) / warmdown) +
                .90 * ((step - (horizon - warmdown)) / warmdown)
                if step >= horizon - warmdown else .97)
    return lr, momentum, .5 * (1 + math.cos(math.pi * step / horizon))


def microbatches(text):
    values = [int(v) for v in text.split(',')]
    if not values or any(v < 1 or BATCH % (v * 2048) for v in values):
        raise ValueError('Microbatches must be positive divisors of 256')
    return sorted(set(values), reverse=True)


def can_measure_update(reader, *, rows_per_update=256, reserve_updates=2):
    """Never consume the finite tail reserved for restart checks."""
    return reader is None or reader.next_row + (1 + reserve_updates) * rows_per_update <= reader.manifest['rows']


def digest_state(model, optimizer):
    """Exact state comparison without retaining a second model in device memory."""
    import torch
    h = hashlib.sha256()
    def add(value):
        if torch.is_tensor(value):
            t = value.detach().cpu().contiguous()
            h.update(str((str(t.dtype), tuple(t.shape))).encode())
            h.update(t.reshape(-1).view(torch.uint8).numpy().tobytes())
        elif isinstance(value, dict):
            for k in sorted(value, key=str):
                h.update(repr(k).encode()); add(value[k])
        elif isinstance(value, (tuple, list)):
            for v in value: add(v)
        else:
            h.update(repr(value).encode())
    add(model.state_dict()); add(optimizer.state_dict())
    return h.hexdigest()


def run(args):
    started = time.monotonic()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(args.repo).resolve()
    revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != PINNED_REVISION:
        raise RuntimeError(f'Unreviewed upstream revision: {revision}')
    if subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain'], text=True).strip():
        raise RuntimeError('Upstream checkout must be clean; benchmark adapter lives outside it')
    sys.path.insert(0, str(repo))
    sys.path.insert(1, str(Path(__file__).resolve().parents[1]))
    os.environ.setdefault('PYTORCH_ALLOC_CONF', 'expandable_segments:True')
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    os.environ.setdefault('WANDB_MODE', 'disabled')
    import gc
    import torch
    if not torch.__version__.startswith('2.9.'):
        raise RuntimeError(f'Pinned worker requires torch 2.9.x, got {torch.__version__}')
    import nanochat.flash_attention as attention
    if args.kernel_path:
        from kernels import get_local_kernel
        attention._fa3 = get_local_kernel(Path(args.kernel_path), 'flash_attn3').flash_attn_interface
        attention.HAS_FA3 = True
        attention.USE_FA3 = attention._resolve_use_fa3()
    from nanochat.gpt import GPT, GPTConfig
    from nanochat.common import COMPUTE_DTYPE
    USE_FA3 = attention.USE_FA3
    from cloud_training.nano_checkpoint import save_bundle, load_bundle
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError('Qualification requires CUDA BF16')
    if COMPUTE_DTYPE != torch.bfloat16:
        raise RuntimeError(f'Expected BF16 activation dtype, got {COMPUTE_DTYPE}')
    torch.set_num_threads(args.cpu_threads)
    width = args.depth * 64
    config = GPTConfig(sequence_len=2048, vocab_size=32768, n_layer=args.depth,
                       n_head=width // 128, n_kv_head=width // 128, n_embd=width, window_pattern='SSSL')
    reader = None
    if args.packed_data:
        from cloud_training.nano_data import PackedRows
        reader = PackedRows(args.packed_data, expected_tokenizer_sha256=args.tokenizer_sha,
                            expected_split='train')
        if reader.manifest['sequence_length'] != 2048 or reader.manifest['vocab_size'] != 32768:
            raise ValueError('Packed data must match the 2048/32768 configuration')
        if reader.manifest['rows'] < (args.warmup_updates + args.minimum_measured_updates + 2) * 256:
            raise ValueError('Insufficient finite rows for warmup, measurement and restart reserve')
    identity = {'revision': revision, 'config': vars(config), 'synthetic': reader is None}
    if reader is not None:
        identity['data_manifest_sha256'] = reader.manifest_sha256
        identity['tokenizer_sha256'] = args.tokenizer_sha
    report = {'status': 'fitting', 'purpose': ('synthetic_compute_only_not_learning' if reader is None else 'real_data_compute_not_quality'),
              'retained_training_targets': 0,
              'identity': identity, 'torch': torch.__version__, 'cuda': torch.version.cuda,
              'gpu': torch.cuda.get_device_name(), 'attention_backend': 'fa3' if USE_FA3 else 'sdpa',
              'effective_batch_tokens': BATCH, 'fit_trials': [], 'updates': []}
    if reader is not None:
        report['packed_data_manifest'] = reader.manifest
    atomic_json(out / 'progress.json', report)
    # Match base_train.py d12 reference decay scaling; dimensions and vocabulary identical.
    with torch.device('meta'):
        ref = GPT(GPTConfig(sequence_len=2048, vocab_size=32768, n_layer=12,
                            n_head=6, n_kv_head=6, n_embd=768, window_pattern='SSSL'))
        ref_counts = ref.num_scaling_params()
    del ref
    def make_model():
        torch.manual_seed(args.seed)
        torch.cuda.manual_seed_all(args.seed)
        with torch.device('meta'):
            m = GPT(config)
        m.to_empty(device='cuda'); m.init_weights(); m.train()
        return m
    def make_optimizer(m):
        counts = m.num_scaling_params()
        decay = .28 * (ref_counts['transformer_matrices'] + ref_counts['lm_head']) / (
            counts['transformer_matrices'] + counts['lm_head'])
        opt = m.setup_optimizer(unembedding_lr=.008, embedding_lr=.3,
                                scalar_lr=.5, matrix_lr=.02, weight_decay=decay)
        return opt, decay
    generator = torch.Generator(device='cpu').manual_seed(args.seed + 1)
    def synthetic_inputs(mb):
        ids = torch.randint(32768, (mb, 2049), generator=generator, dtype=torch.int64)
        return ids[:, :-1].contiguous().to('cuda'), ids[:, 1:].contiguous().to('cuda')
    model = optimizer = None
    for mb in microbatches(args.microbatches):
        try:
            model = make_model(); optimizer, decay = make_optimizer(model)
            torch.cuda.reset_peak_memory_stats()
            x, y = synthetic_inputs(mb)
            loss = model(x, y); loss.backward(); optimizer.step(); model.zero_grad(set_to_none=True)
            torch.cuda.synchronize()
            peak = torch.cuda.max_memory_allocated()
            report['fit_trials'].append({'microbatch': mb, 'status': 'fit', 'peak_bytes': peak})
            del x, y, loss
            break
        except torch.cuda.OutOfMemoryError:
            report['fit_trials'].append({'microbatch': mb, 'status': 'oom'})
            # Drop all live exception/trial tensors before attempting a smaller shape.
            model = optimizer = None
            x = y = loss = None
            gc.collect(); torch.cuda.empty_cache()
            atomic_json(out / 'progress.json', report)
    else:
        raise RuntimeError('No microbatch fits')
    # Discard fit-probe weights; qualification always starts from fresh random initialization.
    model = optimizer = None
    gc.collect(); torch.cuda.empty_cache()
    model = make_model(); optimizer, decay = make_optimizer(model)
    generator.manual_seed(args.seed + 1)
    report['parameter_counts'] = model.num_scaling_params()
    if report['parameter_counts']['total'] != {12: 286261730, 16: 536871738}[args.depth]:
        raise RuntimeError('Unexpected parameter count')
    report['microbatch'] = mb
    report['gradient_accumulation'] = BATCH // (mb * 2048)
    report['initial_groups'] = [{k: v for k, v in group.items() if k != 'params'}
                                 for group in optimizer.param_groups]
    def inputs(mb):
        if reader is None:
            return synthetic_inputs(mb)
        x, y = reader.read(mb)
        return torch.tensor(x, dtype=torch.int64, device='cuda'), torch.tensor(y, dtype=torch.int64, device='cuda')
    compiled = torch.compile(model, dynamic=False) if not args.eager else model
    def update(step):
        torch.cuda.synchronize(); tick = time.monotonic()
        losses = []
        for _ in range(report['gradient_accumulation']):
            x, y = inputs(mb)
            loss = compiled(x, y)
            losses.append(loss.detach())
            (loss / report['gradient_accumulation']).backward()
        lrm, momentum, wd = schedule(step)
        for group in optimizer.param_groups:
            group['lr'] = group['initial_lr'] * lrm
            if group['kind'] == 'muon':
                group['momentum'] = momentum; group['weight_decay'] = decay * wd
        optimizer.step(); model.zero_grad(set_to_none=True)
        avg = torch.stack(losses).mean().item()
        torch.cuda.synchronize()
        if not math.isfinite(avg):
            raise RuntimeError('Nonfinite loss')
        return {'step': step, 'seconds': time.monotonic() - tick, 'loss': avg}
    report['status'] = 'warming_up'
    atomic_json(out / 'progress.json', report)
    warm = [update(i) for i in range(args.warmup_updates)]
    report['warmup_updates'] = warm
    report['setup_and_compile_seconds'] = time.monotonic() - started
    torch.cuda.reset_peak_memory_stats()
    report['status'] = 'measuring'
    step = args.warmup_updates
    measured_start = time.monotonic()
    while time.monotonic() - measured_start < args.seconds and can_measure_update(reader):
        record = update(step)
        report['updates'].append(record); step += 1
        report['measured_seconds'] = time.monotonic() - measured_start
        report['measured_tokens'] = len(report['updates']) * BATCH
        report['tokens_per_second'] = report['measured_tokens'] / report['measured_seconds']
        report['peak_allocated_bytes'] = torch.cuda.max_memory_allocated()
        report['peak_reserved_bytes'] = torch.cuda.max_memory_reserved()
        atomic_json(out / 'progress.json', report)
        print(json.dumps({'event': 'update', **record, 'tokens_per_second': report['tokens_per_second']}), flush=True)
    report['measurement_stop_reason'] = ('finite_data_restart_reserve' if not can_measure_update(reader) else 'requested_duration')
    report['requested_measured_seconds'] = args.seconds
    report['minimum_measured_updates'] = args.minimum_measured_updates
    if len(report['updates']) < args.minimum_measured_updates:
        raise RuntimeError('Too few completed measured updates for qualification')
    report['status'] = 'checking_local_restart'
    atomic_json(out / 'progress.json', report)
    checkpoint = out / 'restart-before'
    checkpoint_tick = time.monotonic()
    data_state = {'exact': True, 'next_batch': step, 'generator_state': generator.get_state()}
    if reader is not None:
        data_state['packed_reader'] = reader.state_dict()
    save_bundle(checkpoint, model=model, optimizer=optimizer,
                metadata={'step': step, 'identity': identity}, data_state=data_state)
    report['checkpoint_write_seconds'] = time.monotonic() - checkpoint_tick
    restore_checkpoint = checkpoint
    if args.backup_prefix:
        from cloud_training.l4_recovery_check import roundtrip_bundle
        restore_checkpoint = out / 'restart-from-gcs'
        report['gcs_roundtrip'] = roundtrip_bundle(checkpoint, remote_prefix=args.backup_prefix,
                                                   destination=restore_checkpoint, timeout=600)
        atomic_json(out / 'progress.json', report)
    uninterrupted = update(step)
    expected = digest_state(model, optimizer)
    # Loading must replace the optimizer state without a second full GPU checkpoint copy.
    checkpoint_tick = time.monotonic()
    restored = load_bundle(restore_checkpoint, model=model, optimizer=optimizer,
                           expected_identity=identity)
    generator.set_state(restored['data_state']['generator_state'])
    if reader is not None:
        reader.load_state_dict(restored['data_state']['packed_reader'])
    if restored['data_state']['next_batch'] != step:
        raise RuntimeError('Incorrect next-update cursor restored')
    report['checkpoint_restore_seconds'] = time.monotonic() - checkpoint_tick
    replay = update(step)
    actual = digest_state(model, optimizer)
    report['restart'] = {'bitwise_model_and_optimizer_match': actual == expected,
                         'uninterrupted_loss': uninterrupted['loss'], 'restored_loss': replay['loss'],
                         'scope': ('GCS roundtrip' if args.backup_prefix else 'local-only') +
                                  (' finite packed-data' if reader is not None else ' synthetic') + ' exact next-update'}
    report['wall_seconds'] = time.monotonic() - started
    report['status'] = 'passed_compute_qualification' if actual == expected else 'restart_mismatch'
    report['limitations'] = [('Synthetic uniformly random IDs.' if reader is None else 'Finite real-data sample; benchmark weights discarded, no automatic corpus admission.'),
                            'No model-quality claim. Throughput excludes evaluation, GCS transfer and interruption overhead.',
                            'Upstream attention fallback is recorded; SSSL architecture is never silently changed.']
    atomic_json(out / 'result.json', report)
    atomic_json(out / 'progress.json', report)
    return 0 if actual == expected else 2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', required=True); p.add_argument('--output', required=True)
    p.add_argument('--depth', type=int, choices=(12, 16), default=16)
    p.add_argument('--packed-data', help='Finite PackedRows directory; no automatic replay')
    p.add_argument('--tokenizer-sha', help='Expected tokenizer SHA256 for packed data')
    p.add_argument('--minimum-measured-updates', type=int, default=3)
    p.add_argument('--backup-prefix', help='Optional GCS prefix for fresh-download restart proof')
    p.add_argument('--kernel-path', help='Pinned offline Flash Attention kernel directory')
    p.add_argument('--seconds', type=int, default=1800)
    p.add_argument('--wall-seconds', type=int, default=5400)
    p.add_argument('--microbatches', default='8,4,2,1')
    p.add_argument('--warmup-updates', type=int, default=3)
    p.add_argument('--cpu-threads', type=int, default=4)
    p.add_argument('--seed', type=int, default=103)
    p.add_argument('--eager', action='store_true')
    p.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    a = p.parse_args()
    microbatches(a.microbatches)
    if bool(a.packed_data) != bool(a.tokenizer_sha):
        p.error('--packed-data and --tokenizer-sha are required together')
    if a.minimum_measured_updates < 1:
        p.error('--minimum-measured-updates must be positive')
    if a.seconds < 1 or a.wall_seconds <= a.seconds or a.warmup_updates < 1 or a.cpu_threads < 1:
        p.error('Require positive duration/warmup/threads and wall deadline greater than measured duration')
    if a.child:
        try:
            return run(a)
        except Exception as exc:
            atomic_json(Path(a.output) / 'failure.json', {'status': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)})
            raise
    out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], '--child'], timeout=a.wall_seconds)
        return proc.returncode
    except subprocess.TimeoutExpired:
        atomic_json(out / 'failure.json', {'status': 'wall_deadline', 'wall_seconds': a.wall_seconds,
                                          'note': 'Process stopped; cloud lease/cleanup must stop billing separately.'})
        return 124


if __name__ == '__main__':
    raise SystemExit(main())
