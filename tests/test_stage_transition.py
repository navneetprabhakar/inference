"""Explicit fresh-optimizer SFT stage, without relaxing old resume bindings."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import json
from pathlib import Path
import shutil
import os
import subprocess
import sys
import numpy as np
import pytest
from slm.common import checkpoint
from slm.common.training import Trainer
from slm.data.tokenized import build_shards, sha
from slm.stage_transition import StageInputs, run, POLICY
from slm.train import run as foundation_run, verify_checkpoint
from test_train import spec as fixture_spec
from test_resume import compare


def setup(tmp_path):
    origin = fixture_spec(tmp_path, 'foundation')
    origin['limits']['updates'] = 1
    report = foundation_run(origin, tmp_path/'foundation')
    target = deepcopy(origin)
    prepared = build_shards(next(iter(origin['releases'].values())), origin['tokenizer'],
                            tmp_path/'sft', 'sft', context_length=64, shard_positions=80)
    target['data'] = dict(kind='tokens', path=str(tmp_path/'sft'), fingerprint=prepared['dataset_hash'])
    target['limits']['updates'] = 3
    target['recipe']['lr'] /= 10
    return target, origin, Path(report['latest_checkpoint']), tmp_path/'foundation/report.json'


def execute(tmp_path, setup_, name, backend='torch', **kwargs):
    target, origin, source, report = setup_
    return run(target, origin, source, report, tmp_path/name, optimizer_policy=POLICY,
               reason='Explicit objective change; new AdamW stage with retained prior exposure.',
               backend=backend, device='default' if backend == 'mlx' else 'cpu', **kwargs)


def inputs(setup_):
    return StageInputs(*setup_, POLICY,
                       'Explicit objective change; new AdamW stage with retained prior exposure.')


@pytest.mark.parametrize('backend', ['torch', 'mlx'])
def test_exact_import_fresh_state_and_same_stage_resume(tmp_path, backend):
    if backend == 'mlx':
        pytest.importorskip('mlx.core')
    s = setup(tmp_path)
    source_hash = sha(s[2]/'manifest.json')
    initial = execute(tmp_path, s, 'init', backend, initialize_only=True)
    assert initial['status'] == 'initialized_only'
    assert set(initial['final'].values()) == {0}
    assert initial['executed_this_invocation']['updates'] == 0
    assert initial['initialization']['source_final']['step'] == 1
    a, source_weights = checkpoint.load(s[2]/'state/model')
    b, imported = checkpoint.load(Path(initial['latest_checkpoint'])/'state/model')
    assert a == b
    for key in source_weights:
        np.testing.assert_array_equal(imported[key].view(np.uint32), source_weights[key].view(np.uint32))
    from safetensors.numpy import load_file
    assert not load_file(str(Path(initial['latest_checkpoint'])/'state/optimizer.safetensors'))
    full = execute(tmp_path, s, 'full', backend, resume=initial['latest_checkpoint'])
    first = execute(tmp_path, s, 'first', backend, resume=initial['latest_checkpoint'], max_new_updates=1)
    second = execute(tmp_path, s, 'second', backend, resume=first['latest_checkpoint'])
    assert second['initial']['step'] == 1
    assert full['final'] == second['final']
    inp = inputs(s)
    try:
        x = Trainer.resume(Path(full['latest_checkpoint'])/'state', inp.data, backend,
                           'default' if backend == 'mlx' else 'cpu', inp.data.tokenizer_hash)
        y = Trainer.resume(Path(second['latest_checkpoint'])/'state', inp.data, backend,
                           'default' if backend == 'mlx' else 'cpu', inp.data.tokenizer_hash)
        compare(x, y, True)
        verify_checkpoint(full['latest_checkpoint'], inp)
    finally:
        inp.close()
    assert second['cumulative_logical_processed_positions'] == initial['initialization']['source_final']['tokens']+second['final']['tokens']
    assert sha(s[2]/'manifest.json') == source_hash


@pytest.mark.parametrize('defect', ['policy', 'reason', 'config', 'tokenizer', 'objective',
                                  'origin_status', 'origin_report', 'origin_events', 'convention'])
def test_refuses_bad_transition_before_output(tmp_path, defect):
    s = list(setup(tmp_path))
    policy, reason = POLICY, 'Explicit SFT objective transition.'
    if defect == 'policy':
        policy = 'preserve-or-reset-implicitly'
    elif defect == 'reason':
        reason = ''
    elif defect == 'config':
        s[0]['config']['num_layers'] += 1
    elif defect == 'tokenizer':
        # Same vocabulary/different byte tokenizer identity must still fail.
        p = Path(s[0]['tokenizer'])/'manifest.json'
        m = json.loads(p.read_text());m['provenance']['extra'] = 'different'
        p.write_text(json.dumps(m))
    elif defect == 'objective':
        s[0] = deepcopy(s[1])
    elif defect in ('origin_status', 'origin_report'):
        r = json.loads(s[3].read_text())
        if defect == 'origin_status': r['status'] = 'invocation_update_limit'
        else: r['final']['tokens'] += 1
        s[3].write_text(json.dumps(r))
    elif defect == 'origin_events':
        s[3].with_name('events.jsonl').write_text('')
    elif defect == 'convention':
        s[0]['recipe']['embedding_implementation'] = 'native-gather-v1'
    with pytest.raises((ValueError, KeyError)):
        run(*s, tmp_path/'bad', optimizer_policy=policy, reason=reason)
    assert not (tmp_path/'bad').exists()


def test_old_resume_and_changed_new_plan_still_rejected(tmp_path):
    s = setup(tmp_path)
    with pytest.raises(ValueError, match='resume plan'):
        execute(tmp_path, s, 'old-resume', resume=s[2])
    initial = execute(tmp_path, s, 'init', initialize_only=True)
    changed = deepcopy(s)
    changed[0]['recipe']['lr'] *= 2
    with pytest.raises(ValueError, match='resume plan'):
        execute(tmp_path, changed, 'new-plan', resume=initial['latest_checkpoint'])
    assert not (tmp_path/'old-resume').exists() and not (tmp_path/'new-plan').exists()


def test_source_checkpoint_relocation_keeps_logical_binding(tmp_path):
    s = setup(tmp_path)
    first = execute(tmp_path, s, 'first', initialize_only=True)
    copied = tmp_path/'relocated'/s[2].name
    shutil.copytree(s[2], copied)
    relocated = (s[0], s[1], copied, s[3])
    second = execute(tmp_path, relocated, 'second', initialize_only=True)
    assert first['plan_hash'] == second['plan_hash']


def test_zero_stage_budget_stops_before_first_atomic_update(tmp_path):
    s = setup(tmp_path)
    s[0]['limits']['processed_positions'] = 1
    r = execute(tmp_path, s, 'bounded')
    assert r['status'] == 'position_ceiling_before_next_atomic_update'
    assert r['final']['step'] == 0
    assert r['executed_this_invocation']['processed_positions'] == 0


def test_cli_resolves_each_spec_against_its_own_directory(tmp_path):
    target, origin, source, report = setup(tmp_path)
    def save_relative(spec, folder):
        folder.mkdir()
        value = deepcopy(spec)
        value['tokenizer'] = os.path.relpath(value['tokenizer'], folder)
        value['data']['path'] = os.path.relpath(value['data']['path'], folder)
        value['releases'] = {k: os.path.relpath(v, folder) for k, v in value['releases'].items()}
        path = folder/'spec.json'
        path.write_text(json.dumps(value))
        return path
    target_file = save_relative(target, tmp_path/'target-config')
    origin_file = save_relative(origin, tmp_path/'origin-config')
    cwd = tmp_path/'elsewhere'
    cwd.mkdir()
    subprocess.run([sys.executable, '-m', 'slm.stage_transition', '--spec', str(target_file),
        '--origin-spec', str(origin_file), '--origin-checkpoint', str(source), '--origin-report', str(report),
        '--output', str(tmp_path/'cli-output'), '--optimizer-policy', POLICY,
        '--reason', 'Explicit objective transition.', '--initialize-only'], cwd=cwd, check=True, capture_output=True)
    result = json.loads((tmp_path/'cli-output/report.json').read_text())
    assert result['status'] == 'initialized_only' and result['final']['step'] == 0


def test_mlx_stage_resume_on_torch_preserves_learned_optimizer_and_counters(tmp_path):
    pytest.importorskip('mlx.core')
    s = setup(tmp_path)
    first = execute(tmp_path, s, 'mlx-stage', backend='mlx', max_new_updates=1)
    imported = execute(tmp_path, s, 'torch-stage', resume=first['latest_checkpoint'], initialize_only=True)
    assert imported['final'] == first['final'] and imported['final']['step'] == 1
    assert imported['executed_this_invocation']['updates'] == 0
    inp = inputs(s)
    try:
        a = Trainer.resume(Path(first['latest_checkpoint'])/'state', inp.data, 'mlx', 'default', inp.data.tokenizer_hash)
        b = Trainer.resume(Path(imported['latest_checkpoint'])/'state', inp.data, 'torch', 'cpu', inp.data.tokenizer_hash)
        compare(a, b, True)
        assert b.moments  # This backend switch must not apply the initial fresh policy again.
    finally:
        inp.close()
