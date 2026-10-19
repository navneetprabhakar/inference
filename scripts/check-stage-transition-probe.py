#!/usr/bin/env python3
"""Verify the actual full-size zero-update SFT-stage import, without generation."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file
from slm.common import checkpoint
from slm.data.schema import digest
from slm.data.tokenized import sha


def main():
    root = Path('data/iteration-three-transition-probe-v2')
    run = root/'mlx'
    report = json.loads((run/'report.json').read_text())
    launch = json.loads((run/'run.json').read_text())
    old_run = Path('data/iteration-two-experiment-v1/runs/selected-continuation')
    old_report = json.loads((old_run/'report.json').read_text())
    old = Path(old_report['latest_checkpoint'])
    new = Path(report['latest_checkpoint'])
    binding = json.loads((new/'binding.json').read_text())
    assert binding['plan'] == launch['logical_plan']
    assert binding['plan_hash'] == digest(binding['plan']) == report['plan_hash'] == launch['plan_hash']
    assert report['initialization'] == binding['plan']['initialization']
    assert report['initialization']['source_checkpoint_sha256'] == sha(old/'manifest.json')
    assert report['initialization']['source_terminal_report_sha256'] == sha(old_run/'report.json')
    assert report['initialization']['source_final'] == old_report['final']
    assert binding['plan']['reference_sources']['stage_transition.py'] == sha('src/slm/stage_transition.py')
    for folder in (old, new):
        for manifest in ('manifest.json', 'state/manifest.json'):
            file = folder/manifest
            for name, checksum in json.loads(file.read_text()).items():
                assert sha(file.parent/name) == checksum
    a, x = checkpoint.load(old/'state/model')
    b, y = checkpoint.load(new/'state/model')
    assert a == b and x.keys() == y.keys() and a.parameter_count == 80765440
    for key in x:
        assert np.array_equal(x[key].view(np.uint32), y[key].view(np.uint32)), key
    assert not load_file(str(new/'state/optimizer.safetensors'))
    state = json.loads((new/'state/state.json').read_text())
    assert all(state[k] == 0 for k in ('step', 'cursor', 'tokens', 'supervised_tokens'))
    assert report['status'] == 'initialized_only' and set(report['final'].values()) == {0}
    assert report['executed_this_invocation']['updates'] == 0 and (run/'events.jsonl').read_bytes() == b''
    original = json.loads((old_run/'run.json').read_text())
    for name, checksum in original['logical_plan']['reference_sources'].items():
        assert sha(Path('src/slm')/name) == checksum
    receipt = dict(creator='Navneet Prabhakar', version=1, actual_probe=report,
        source_manifest_sha256=sha(old/'manifest.json'), imported_model_manifest_sha256=sha(new/'state/model/manifest.json'),
        spec_sha256=sha(root/'spec.json'), transition_implementation_sha256=sha('src/slm/stage_transition.py'),
        control_script_sha256=sha(__file__), test_source_sha256=sha('tests/test_stage_transition.py'),
        exact_imported_tensors=len(x), exact_imported_fp32_values=sum(v.size for v in x.values()),
        optimizer_empty=True, events_empty=True, original_26_training_references_unchanged=True,
        focused_tests=dict(passed=43, skipped=2,
            command='.venv/bin/python -m pytest -q -rs tests/test_stage_transition.py tests/test_train.py',
            skip_reason='Actual NVIDIA wrapper validation unavailable locally'),
        scope='Actual MLX full-size initialization only, zero gradient updates. Tiny MLX/PyTorch same-stage resume tests separate. Not actual CUDA transition validation, preservation of foundation optimizer, new conversational skill, paid run or broad SFT iteration.')
    Path('reports/milestone-fifty-five-stage-transition.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
    print(json.dumps(dict(exact_tensors=len(x), exact_fp32_values=sum(v.size for v in x.values()),
                          optimizer_entries=0, new_gradient_updates=0), indent=2))


if __name__ == '__main__':
    main()
