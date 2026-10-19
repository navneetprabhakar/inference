#!/usr/bin/env python3
"""Reopen actual zero-update import and both disposable full-step receipts."""
# Creator: Navneet Prabhakar
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file
from slm.common import checkpoint
from slm.data.schema import digest
from slm.data.tokenized import sha


def main():
    root = Path('data/iteration-three-sft-stage-v2')
    protocol = json.loads((root/'preparation.json').read_text())
    for name, value in protocol['source_sha256'].items():
        assert sha(name) == value
    source_report = json.loads(Path(protocol['source_report']).read_text())
    source = Path(source_report['latest_checkpoint'])
    assert str(source) == protocol['source_checkpoint']
    source_model_hash = sha(source/'state/model/manifest.json')
    trials = {}
    normalized_specs = []
    for trial, binding in protocol['trials'].items():
        spec = json.loads((root/(trial+'.json')).read_text())
        normalized = json.loads(json.dumps(spec))
        rate = normalized['recipe'].pop('lr')
        assert rate == (1e-5 if trial == 'lr-00001' else 5e-5)
        normalized_specs.append(normalized)
        assert sha(root/(trial+'.json')) == binding['spec_file_sha256']
        receipt = json.loads((root/('preflight-'+trial+'.json')).read_text())
        assert receipt['plan_hash'] == binding['plan_hash']
        assert receipt['kind'] == 'sft-full-step-resource-preflight-v1'
        assert receipt['passed'] is True and receipt['source_unchanged'] is True
        assert receipt['main_student_updates'] == 0 and receipt['disposable_optimizer_updates'] == 1
        assert receipt['synthetic_gradient_positions'] == binding['synthetic_preflight_positions'] == 6332
        assert receipt['maximum_sequence_length'] == 1583 and receipt['backend'] == 'mlx' and receipt['device'] == 'default'
        assert receipt['source_model_sha256'] == source_model_hash
        assert receipt['config'] == spec['config'] and receipt['recipe'] == spec['recipe']
        assert receipt['policy_file_sha256'] == spec['policy_file_sha256']
        assert receipt['implementation_sha256'] == sha('src/slm/sft_research_preflight.py')
        assert np.isfinite(receipt['cold_complete_step_seconds']) and receipt['cold_complete_step_seconds'] > 0
        assert receipt['update']['step'] == 1 and receipt['update']['tokens'] == 6332
        trials[trial] = receipt
    assert normalized_specs[0] == normalized_specs[1]
    assert protocol['prospective_combined_positions'] == 915325 <= 1048576
    reserved = [json.loads(line) for line in (root/'preflight-reservations.jsonl').read_text().splitlines()]
    assert len(reserved) == 2 and {r['trial'] for r in reserved} == set(trials)
    assert sum(r['positions'] for r in reserved) == protocol['planned_total_preflight_positions'] == 12664
    for r in reserved:
        assert r['plan_hash'] == protocol['trials'][r['trial']]['plan_hash']
        assert r['positions'] == trials[r['trial']]['synthetic_gradient_positions']
    initial_run = root/'lr-00001-initialization'
    report = json.loads((initial_run/'report.json').read_text())
    launch = json.loads((initial_run/'run.json').read_text())
    assert report['plan_hash'] == protocol['trials']['lr-00001']['plan_hash'] == digest(launch['logical_plan'])
    assert report['status'] == 'initialized_only' and set(report['final'].values()) == {0}
    assert report['executed_this_invocation']['updates'] == 0 and (initial_run/'events.jsonl').read_bytes() == b''
    new = Path(report['latest_checkpoint'])
    for folder in (source, new):
        for filename in ('manifest.json','state/manifest.json'):
            path = folder/filename
            for name, value in json.loads(path.read_text()).items(): assert sha(path.parent/name) == value
    assert not load_file(str(new/'state/optimizer.safetensors'))
    a, x = checkpoint.load(source/'state/model')
    b, y = checkpoint.load(new/'state/model')
    assert a == b and a.parameter_count == 80765440 and set(x) == set(y)
    assert all(np.array_equal(v.view(np.uint32), y[k].view(np.uint32)) for k,v in x.items())
    exact = dict(tensors=len(x), fp32_values=sum(v.size for v in x.values()))
    for name, value in launch['logical_plan']['reference_sources'].items():
        assert sha(Path('src/slm')/name) == value
    original = json.loads(Path('data/iteration-two-experiment-v1/runs/selected-continuation/run.json').read_text())
    assert len(original['logical_plan']['reference_sources']) == 26
    assert all(sha(Path('src/slm')/name) == value for name,value in original['logical_plan']['reference_sources'].items())
    result = dict(creator='Navneet Prabhakar', protocol=protocol, protocol_sha256=sha(root/'preparation.json'),
        exact_initialization=exact, actual_preflights=trials,
        initialization_report_sha256=sha(initial_run/'report.json'),
        synthetic_gradient_positions=12664, disposable_optimizer_updates=2, main_student_updates=0,
        source_model_sha256=source_model_hash, original_26_runtime_references_unchanged=True,
        launch_contract_ready=False, controls_script_sha256=sha(__file__),
        test_source_sha256=sha('tests/test_research_sft_stage.py'),
        scope='Actual full-size MLX zero-update import and two cold complete-step synthetic clones. No real SFT training, sustained benchmark, new conversation score or CUDA result. Frozen optimizer selection/evaluation/launch contract remains next.')
    file = Path('reports/milestone-sixty-two-actual-stage-probes.json')
    rendered = json.dumps(result, indent=2, sort_keys=True)+'\n'
    if file.exists(): assert file.read_text() == rendered
    else: file.write_text(rendered)
    print(json.dumps(dict(exact_import=exact, preflight_positions=12664,
        timings={k:v['cold_complete_step_seconds'] for k,v in trials.items()},
        memory={k:v['memory'] for k,v in trials.items()}), indent=2))


if __name__ == '__main__':
    main()
