"""Bounded synthetic MLX forward/backward sizing with no optimizer updates."""
# Creator: Navneet Prabhakar
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from slm.common import checkpoint
from slm.common.tokenizer import OFFSET
from slm.data.tokenized import sha
from slm.eval.portability import environment, memory_snapshot


SEED = 20261019


def workload(length, vocab_size, maximum=2048):
    if type(length) is not int or not 1 <= length <= maximum or vocab_size <= OFFSET:
        raise ValueError('Bounded content-only synthetic workload required')
    # The shorter workload is exactly a prefix of the longer workload.
    stream = np.random.default_rng(SEED).integers(OFFSET, vocab_size, (1, maximum+1), dtype=np.int32)
    mask = np.zeros((1, length), dtype=np.float32)
    mask[:, length//2:] = 1
    return stream[:, :length], stream[:, 1:length+1], mask


def parameter_bits(impl, params):
    arrays = impl.export(params)
    h = hashlib.sha256()
    for name in sorted(arrays):
        h.update(name.encode()); h.update(arrays[name].tobytes(order='C'))
    return h.hexdigest()


def run(model, expected_model_hash, output, length):
    model, output = Path(model), Path(output)
    if output.exists(): raise FileExistsError(output)
    if length not in (1024, 2048): raise ValueError('Predeclared 1024/2048 probe only')
    if sha(model/'manifest.json') != expected_model_hash:
        raise ValueError('Frozen model identity differs')
    config, weights = checkpoint.load(model)
    if config.max_seq_len < length: raise ValueError('Requested probe exceeds model context')
    import mlx.core as mx
    from slm.backends import mlx_backend as impl
    if mx.default_device() != mx.gpu: raise RuntimeError('Actual MLX GPU required, no CPU fallback')
    env = environment('mlx', 'default')
    params = impl.load(config, weights)
    del weights
    before = parameter_bits(impl, params)
    mx.synchronize()
    active_before_slots = mx.get_active_memory()
    slots = {}
    for i, (name, value) in enumerate(params.items()):
        # Unique finite constants prevent common-expression sharing of dummy slots.
        for j, slot in enumerate(('m', 'v')):
            slots[slot+':'+name] = mx.array(np.full(value.shape, (2*i+j+1)*1e-9, dtype=np.float32))
    mx.eval(slots); mx.synchronize()
    slot_bytes = 2*config.parameter_count*4
    reserved_delta = mx.get_active_memory()-active_before_slots
    if reserved_delta < slot_bytes: raise ValueError('Moment-shaped reservation not resident')
    x, y, mask = workload(length, config.vocab_size, config.max_seq_len)
    arrays = [mx.array(v) for v in (x, y, mask)]
    mx.eval(arrays)
    def gradient():
        value, grads = impl.value_and_grad(params, config, *arrays,
            embedding_implementation='dense-onehot-v1', loss_implementation='legacy-logsumexp-minus-target-v1')
        mx.synchronize()
        return value, grads
    def finite(value, grads):
        if (not np.isfinite(float(value)) or not bool(mx.all(mx.stack([mx.all(mx.isfinite(g)) for g in grads.values()])).item())):
            raise FloatingPointError('Nonfinite synthetic loss/gradient')
    warm_started = time.perf_counter()
    value, grads = gradient()
    warm_seconds = time.perf_counter()-warm_started
    finite(value, grads)
    del value, grads
    mx.synchronize(); mx.reset_peak_memory()
    timings = []; losses = []
    for _ in range(3):
        started = time.perf_counter()
        value, grads = gradient()
        timings.append(time.perf_counter()-started)
        finite(value, grads); losses.append(float(value))
        del value, grads
    mx.synchronize()
    memory = memory_snapshot('mlx', 'default')
    memory['allocator_peak_scope'] = 'Reset after warmup; timed forward/backward and untimed finite checks, with moment-shaped buffers resident.'
    after = parameter_bits(impl, params)
    if before != after or sha(model/'manifest.json') != expected_model_hash:
        raise ValueError('Probe changed source parameters or identity')
    result = dict(creator='Navneet Prabhakar', version=1, model_manifest_sha256=expected_model_hash,
        implementation_sha256=sha(__file__), backend_sha256=sha(impl.__file__), environment=env,
        parameters=config.parameter_count, config=config.to_dict(), sequence_length=length, batch_size=1,
        seed=SEED, embedding_implementation='dense-onehot-v1', loss_implementation='legacy-logsumexp-minus-target-v1',
        warmup_gradient_calls=1, timed_gradient_calls=3, warmup_seconds=warm_seconds,
        forward_backward_seconds=timings, timed_positions=3*length,
        timed_forward_backward_positions_per_second=3*length/sum(timings),
        total_gradient_probe_positions=4*length, total_supervised_probe_positions=4*int(mask.sum()),
        resident_moment_shaped_bytes=slot_bytes, observed_reservation_delta_bytes=reserved_delta,
        reservation_kind='Synthetic FP32 buffers; not source optimizer values and not used by an optimizer.',
        memory=memory, finite_losses=losses, parameters_bitwise_unchanged=True,
        optimizer_updates=0, new_training_positions=0,
        scope='Synthetic fixed-length forward/backward only. Timings exclude validation/export, optimizer/clipping and data/checkpoint work. RSS is process lifetime; allocator peak has the declared reset scope and overlaps unified-memory RSS. No sustained throughput, complete training-step feasibility, learned quality or actual CUDA claim.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as f: f.write(json.dumps(result, indent=2, sort_keys=True)+'\n')
    return result


def main():
    p = argparse.ArgumentParser()
    for name in ('model', 'model-manifest-sha256', 'output'): p.add_argument('--'+name, required=True)
    p.add_argument('--length', type=int, choices=(1024, 2048), required=True)
    a = p.parse_args()
    r = run(a.model, a.model_manifest_sha256, a.output, a.length)
    print(json.dumps({k: r[k] for k in ('sequence_length', 'forward_backward_seconds', 'memory', 'optimizer_updates')}, indent=2))


if __name__ == '__main__':
    main()
