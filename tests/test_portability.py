import json
import numpy as np
import pytest
from slm.eval.portability import create, verify, validate_bundle, compare, environment


def test_mlx_export_serializes_transposed_arrays_and_scalars(tmp_path):
    mx = pytest.importorskip('mlx.core')
    from slm.backends.mlx_backend import export
    from safetensors.numpy import save_file, load_file
    values = export({'matrix': mx.arange(12, dtype=mx.float32).reshape(3, 4).T,
                     'scalar': mx.array(2., dtype=mx.float32)})
    assert values['matrix'].flags.c_contiguous
    assert values['scalar'].shape == ()
    save_file(values, str(tmp_path/'probe.safetensors'))
    restored = load_file(str(tmp_path/'probe.safetensors'))
    for name in values:
        np.testing.assert_array_equal(values[name], restored[name])


def test_two_leg_bundle(tmp_path):
    pytest.importorskip('mlx.core')
    bundle, outbound, returned = (tmp_path/n for n in ('bundle','outbound','returned'))
    create(bundle, 'mlx')
    first = verify(bundle, outbound, 'torch')
    second = verify(bundle, returned, 'mlx', resume=outbound/'checkpoint')
    assert first['passed'] and second['passed']
    assert first['start_step'] == 2 and first['final_step'] == 4
    assert second['start_step'] == 4 and second['final_step'] == 6
    assert first['destination']['device'] == 'cpu'
    assert first['bundle_hash'] == second['bundle_hash']
    assert 'gradient:embedding' in first['checks']['4']
    assert 'moment_v:embedding' in second['checks']['6']
    assert 'cached_logits' in first['checks']['2']


def test_corrupt_bundle_and_reject_false_match(tmp_path):
    root=tmp_path/'bundle'; create(root,'torch')
    with (root/'batches.npz').open('ab') as f: f.write(b'corrupted')
    with pytest.raises(ValueError,match='checksum'): validate_bundle(root)
    with pytest.raises(AssertionError): compare({'logits':np.ones(2)}, {'logits':np.zeros(2)})
    with pytest.raises(ValueError): compare({'logits':np.array([np.nan])}, {'logits':np.ones(1)})


def test_failed_check_records_failure(tmp_path, monkeypatch):
    import slm.eval.portability as module
    root=tmp_path/'bundle'; create(root,'torch')
    def fail(*args): raise AssertionError('deliberate mismatch')
    monkeypatch.setattr(module,'compare',fail)
    with pytest.raises(AssertionError): verify(root,tmp_path/'failed','torch')
    report=json.loads((tmp_path/'failed'/'verification.json').read_text())
    assert report['passed'] is False
    assert not (tmp_path/'failed'/'checkpoint').exists()


def test_cuda_never_falls_back():
    import torch
    if torch.cuda.is_available(): pytest.skip('CUDA is available on this host')
    with pytest.raises(RuntimeError,match='no CPU fallback'): environment('torch','cuda')


def test_cuda_100_updates_and_bidirectional_resume(tmp_path):
    import os
    from pathlib import Path
    import torch
    from slm.common.config import Config, initialize
    from slm.common.training import Batches, Trainer
    from slm.eval.portability import capture
    if not torch.cuda.is_available():
        pytest.skip('NVIDIA CUDA device unavailable')
    environment('torch', 'cuda')
    rng = np.random.default_rng(123)
    items = []
    for i in range(100):
        x = rng.integers(0, 64, (2, 4+i%5))
        y = rng.integers(0, 64, x.shape)
        mask = rng.integers(0, 2, x.shape).astype(np.float32)
        mask[:, 0] = 1
        items.append((x, y, mask))
    config = Config()
    batches = Batches(items, config.vocab_size)
    cpu = Trainer(config, initialize(config), batches, 'torch', 'cpu')
    gpu = Trainer(config, initialize(config), batches, 'torch', 'cuda')
    migrated = None
    checks = {}
    for step in range(1, 101):
        cpu.update(); gpu.update()
        if migrated is not None:
            migrated.update()
        if step in (1, 25, 50, 75, 100):
            reference = capture(cpu)
            checks[str(step)] = compare(capture(gpu), reference)
            if migrated is not None:
                checks[f'migrated-{step}'] = compare(capture(migrated), reference)
        if step == 50:
            cpu.save(tmp_path/'cpu-50')
            migrated = Trainer.resume(tmp_path/'cpu-50', batches, 'torch', 'cuda')
        if step == 75:
            migrated.save(tmp_path/'cuda-75')
            migrated = Trainer.resume(tmp_path/'cuda-75', batches, 'torch', 'cpu')
    assert migrated.step == cpu.step == gpu.step == 100
    assert migrated.cursor == cpu.cursor == gpu.cursor == 100
    assert migrated.tokens == cpu.tokens == gpu.tokens
    if destination := os.environ.get('SLM_CUDA_STRESS_REPORT'):
        Path(destination).write_text(json.dumps({'passed': True, 'updates': 100,
            'destination': environment('torch', 'cuda'), 'checks': checks}, indent=2)+'\n')
