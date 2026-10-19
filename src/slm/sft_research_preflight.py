"""Finite complete optimizer-step resource preflight on a disposable synthetic clone."""
# Creator: Navneet Prabhakar
from dataclasses import asdict
from pathlib import Path
import time
import numpy as np
from slm.common import checkpoint
from slm.common.training import Batches, Trainer
from slm.common.tokenizer import STRUCTURAL
from slm.data.tokenized import sha
from slm.eval.portability import environment, memory_snapshot
from slm.train import synchronize, write


def preflight(inputs, output, backend='mlx', device='default'):
    output = Path(output)
    if output.exists(): raise FileExistsError(output)
    if backend+':'+device not in inputs.allowed_devices:
        raise ValueError('Explicit locally authorized backend/device required')
    length = inputs.data.max_length
    accumulation = inputs.recipe.accumulation_steps
    positions = length*accumulation
    if positions > inputs.research_limits['synthetic_preflight_gradient_positions']:
        raise ValueError('Synthetic full-step workload exceeds policy')
    inputs.check()
    source_before = sha(inputs.source_model/'manifest.json')
    cfg, weights = checkpoint.load(inputs.source_model)
    env = environment(backend, device)
    if backend == 'mlx':
        import mlx.core as mx
        if mx.default_device() != mx.gpu:
            raise ValueError('Actual MLX GPU required; no fallback')
    rng = np.random.default_rng(20261019)
    raw = rng.integers(max(STRUCTURAL.values())+1, cfg.vocab_size, size=(1, length+1), dtype=np.int64)
    mask = np.zeros((1, length), dtype=np.float32)
    mask[:, length//2:] = 1
    data = Batches([(raw[:, :-1], raw[:, 1:], mask)]*accumulation, cfg.vocab_size)
    trainer = Trainer(cfg, weights, data, backend, device, inputs.recipe, inputs.data.tokenizer_hash)
    synchronize(backend, device)
    if backend == 'mlx': mx.reset_peak_memory()
    tick = time.perf_counter()
    update = trainer.update()
    synchronize(backend, device)
    seconds = time.perf_counter()-tick
    learned = trainer.impl.export(trainer.params)
    if not all(np.isfinite(v).all() for v in learned.values()):
        raise ValueError('Nonfinite preflight weights')
    if trainer.step != 1 or trainer.tokens != positions or not trainer.moments:
        raise ValueError('Expected one complete fresh-optimizer step')
    moments = trainer.impl.export({f'{k}:{i}': value for k, pair in trainer.moments.items() for i,value in enumerate(pair)})
    if set(trainer.moments) != set(weights) or not all(np.isfinite(v).all() for v in moments.values()):
        raise ValueError('Nonfinite or incomplete preflight optimizer moments')
    source_unchanged = sha(inputs.source_model/'manifest.json') == source_before
    # Reopen the source payload transitively; source is never a training output here.
    _, original = checkpoint.load(inputs.source_model)
    if not source_unchanged or any(not np.array_equal(original[k].view(np.uint32), v.view(np.uint32)) for k,v in weights.items()):
        raise ValueError('Main source model changed')
    inputs.check()
    report = dict(kind='sft-full-step-resource-preflight-v1', passed=True, plan_hash=inputs.identity,
        source_model_sha256=source_before, source_unchanged=True, config=cfg.to_dict(), recipe=asdict(inputs.recipe),
        policy_file_sha256=inputs.policy_hash, backend=backend, device=device, environment=env,
        maximum_sequence_length=length, synthetic_gradient_positions=positions,
        synthetic_supervised_positions=int(mask.sum())*accumulation,
        disposable_optimizer_updates=1, main_student_updates=0, cold_complete_step_seconds=seconds,
        update=update, memory=memory_snapshot(backend, device), implementation_sha256=sha(__file__),
        scope='One cold full-step synthetic clone; includes gradient/export/clipping/AdamW. Not sustained throughput, real SFT exposure, quality or an upper bound on memory. Main checkpoint unchanged; clone discarded.')
    output.parent.mkdir(parents=True, exist_ok=True)
    write(output, report)
    return report
