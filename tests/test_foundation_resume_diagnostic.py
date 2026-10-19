"""Actual checkpoint-comparison mechanics on tiny synthetic managed runs."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import runpy
import pytest
from safetensors.numpy import load_file, save_file
from slm.common.config import Config
from slm.train import Inputs, run
from slm.data.tokenized import sha
from test_train import spec as fixture_spec


def dump(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True)+'\n')


@pytest.fixture
def experiment(tmp_path):
    spec = fixture_spec(tmp_path, 'foundation')
    spec['config'] = Config(vocab_size=spec['config']['vocab_size'], hidden_size=8,
                            intermediate_size=16, num_layers=1, num_heads=2,
                            num_kv_heads=1, max_seq_len=64).to_dict()
    spec['recipe']['accumulation_steps'] = 1
    inputs = Inputs(spec)
    try:
        n = len(inputs.data)
    finally:
        inputs.close()
    assert n >= 2
    spec['limits']['updates'] = n+1
    dump(tmp_path/'spec.json', spec)
    a = run(spec, tmp_path/'original')
    origin = next(p for p in (tmp_path/'original/checkpoints').iterdir()
                  if json.loads((p/'state/state.json').read_text())['step'] == n-1)
    b = run(spec, tmp_path/'replay', resume=origin, max_new_updates=1)
    assert a['status'] == b['status'] == 'data_exhausted_before_target'
    contract = json.loads(Path('configs/foundation-smoke-resume-check-v1.json').read_text())
    contract.update(scope='synthetic_comparison_mechanics_only', plan_hash=a['plan_hash'],
                    backend='torch', device='cpu', original_run=str(tmp_path/'original'),
                    resume_run=str(tmp_path/'replay'), resume_checkpoint_step=n-1,
                    expected_final_step=n, expected_final_processed_positions=a['final']['tokens'])
    dump(tmp_path/'contract.json', contract)
    compare = runpy.run_path('scripts/verify-foundation-resume.py')['compare']
    return tmp_path, a, b, compare


def test_exact_checkpoint_resume_comparison_and_separate_replay_accounting(experiment):
    root, a, b, compare = experiment
    result = compare(root/'spec.json', root/'contract.json')
    assert result['exact_passed'] and not result['cross_backend_quality_proved']
    assert result['additional_physical_replay']['updates'] == 1
    assert result['combined_physical_positions'] > result['final_model_logical_positions']
    assert result['final_model_logical_positions'] == a['final']['tokens']


def test_resealed_tensor_mismatch_is_reported_as_failure(experiment):
    root, _, b, compare = experiment
    cp = Path(b['latest_checkpoint'])
    path = cp/'state/model/model.safetensors'
    weights = load_file(str(path))
    weights['embedding'][0, 0] += .01
    save_file(weights, str(path))
    # Resealing proves the comparator checks values, beyond manifest integrity.
    for manifest in (cp/'state/model/manifest.json', cp/'state/manifest.json', cp/'manifest.json'):
        hashes = json.loads(manifest.read_text())
        dump(manifest, {name: sha(manifest.parent/name) for name in hashes})
    report = json.loads((root/'replay/report.json').read_text())
    report['latest_manifest_sha256'] = sha(cp/'manifest.json')
    dump(root/'replay/report.json', report)
    result = compare(root/'spec.json', root/'contract.json')
    assert not result['exact_passed']
    assert result['tensor_mismatches'] == ['model/model.safetensors:embedding']


@pytest.mark.parametrize('defect', ['counter', 'origin', 'event'])
def test_terminal_report_event_and_origin_binding_cannot_be_substituted(experiment, defect):
    root, _, _, compare = experiment
    if defect == 'event':
        with (root/'replay/events.jsonl').open('a') as f:
            f.write('\n')
    elif defect == 'origin':
        p = root/'replay/run.json'
        r = json.loads(p.read_text()); r['resume_manifest_sha256'] = '0'*64; dump(p, r)
    else:
        p = root/'replay/report.json'
        r = json.loads(p.read_text()); r['final']['supervised_tokens'] -= 1; dump(p, r)
    with pytest.raises(ValueError):
        compare(root/'spec.json', root/'contract.json')
