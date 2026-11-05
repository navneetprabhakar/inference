"""Real-data microbatch throughput probe. All diagnostic updates are discarded."""
import argparse
import fcntl
import gc
import hashlib
import json
import math
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np
from mlx.utils import tree_map
from benchmark_mlx import Model
from inference_guard import violation
from sft_common import ROOT, configure_memory, masked_loss, memory_stats
from token_weighted_gradients import add_weighted, mean_gradient
from train_local import health


def main(args):
    goal = ROOT/'runs/eight-hour-improvement-v1'
    out = ROOT/args.output
    if out.exists():
        raise RuntimeError('Preserve completed probe; do not rerun into the same output')
    deadline = json.loads((goal/'authorization.json').read_text())['deadline_unix']
    cp, data = ROOT/args.checkpoint, ROOT/args.data
    source_sha = hashlib.sha256((cp/'model.safetensors').read_bytes()).hexdigest()
    manifest = json.loads((data/'manifest.json').read_text())
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((data/name).read_bytes()).hexdigest() == digest
    arr = dict(np.load(data/'episodes.npz'))
    order = json.loads((data/'order.json').read_text())['order']
    baseline = {**health(), **memory_stats()}

    def guard():
        if time.time() >= deadline or (goal/'STOP').exists():
            raise RuntimeError('deadline_or_STOP')
        reason = violation({**health(), **memory_stats()}, baseline)
        if reason:
            raise RuntimeError(reason)

    def arm(batch_size):
        master = Model(768, 12, 16384)
        master.load_weights(str(cp/'model.safetensors'))
        compute = Model(768, 12, 16384)
        compute.update(tree_map(lambda x: x.astype(mx.bfloat16), master.parameters()))
        opt = optim.AdamW(1e-5, betas=[.9, .95], weight_decay=.1, bias_correction=True)
        mx.eval(master.parameters(), compute.parameters(), opt.state)
        grad = nn.value_and_grad(compute, masked_loss)
        batches = []
        for start in range(0, len(order), 64):
            block = sorted(order[start:start+64], key=lambda i: int(arr['length'][i]))
            batches.extend(block[j:j+batch_size] for j in range(0, len(block), batch_size)
                           if len(block[j:j+batch_size]) == batch_size)
        cursor = 0

        def step():
            nonlocal cursor
            count = inputs = padded = 0
            accumulated = None
            while count < 512:
                guard()
                ix = batches[cursor]; cursor += 1
                width = max(int(arr['length'][i]) for i in ix)
                mask = mx.array(arr['mask'][ix, :width-1])
                n = int(arr['mask'][ix, :width-1].sum())
                loss, gradients = grad(compute, mx.array(arr['ids'][ix, :width]), mask)
                mx.eval(loss, gradients)
                if not math.isfinite(float(loss)):
                    raise RuntimeError('nonfinite_loss')
                accumulated = add_weighted(accumulated, gradients, n)
                mx.eval(accumulated)
                count += n; inputs += sum(int(arr['length'][i])-1 for i in ix)
                padded += len(ix)*(width-1)
            guard()
            gradients, norm = optim.clip_grad_norm(mean_gradient(accumulated, count), 1.0)
            mx.eval(norm)
            if not math.isfinite(float(norm)):
                raise RuntimeError('nonfinite_gradient')
            opt.update(master, gradients)
            mx.eval(master.parameters(), opt.state)
            compute.update(tree_map(lambda x: x.astype(mx.bfloat16), master.parameters()))
            mx.eval(compute.parameters())
            return inputs, padded

        step()  # One real update for initialization; excluded from timed throughput.
        start = time.monotonic(); inputs = padded = updates = 0
        while time.monotonic()-start < args.seconds:
            n, slots = step(); inputs += n; padded += slots; updates += 1
        elapsed = time.monotonic()-start
        return {'microbatch': batch_size, 'seconds': elapsed, 'optimizer_updates': updates,
                'nonpadding_input_tokens': inputs, 'tokens_per_second': inputs/elapsed,
                'padding_fraction': 1-inputs/padded, 'health': {**health(), **memory_stats()}}

    result = {'kind': 'discarded_training_throughput_probe_NOT_quality_evaluation',
              'checkpoint': str(cp), 'checkpoint_sha256': source_sha,
              'data_manifest_sha256': hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest(),
              'seconds_per_arm': args.seconds, 'arms': [], 'weights_saved': False,
              'limitation': 'Short probe, not sustained thermal throughput; same deterministic source order but different grouping and timed token prefixes.'}
    with (goal/'.training.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        configure_memory(); guard()
        try:
            for size in [2, 4, 8]:
                gc.collect(); mx.clear_cache()
                if hasattr(mx, 'reset_peak_memory'):
                    mx.reset_peak_memory()
                guard()
                item = arm(size); result['arms'].append(item)
                print(json.dumps(item), flush=True)
        except Exception as exc:
            result['stopped_reason'] = repr(exc)
        result['source_weights_unchanged'] = hashlib.sha256((cp/'model.safetensors').read_bytes()).hexdigest() == source_sha
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--checkpoint', required=True)
    p.add_argument('--data', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--seconds', type=int, default=20)
    args = p.parse_args()
    assert 5 <= args.seconds <= 30
    main(args)
