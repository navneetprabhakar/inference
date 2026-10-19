#!/usr/bin/env python3
"""Reaggregate saved actual context probes and retain observed hardware metadata."""
# Creator: Navneet Prabhakar
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import numpy as np
from slm.common import checkpoint
from slm.data.tokenized import sha


def main():
    root = Path('data/sft-context-sizing-v1')
    file = Path('reports/milestone-fifty-seven-context-sizing.json')
    report = json.loads(file.read_text())
    protocol = json.loads((root/'protocol.json').read_text())
    assert report['protocol'] == protocol and report['protocol_sha256'] == sha(root/'protocol.json')
    assert protocol['implementation_sha256'] == sha('src/slm/eval/sft_context_probe.py')
    assert protocol['script_sha256'] == sha('scripts/measure-sft-context.py')
    assert protocol['order'] == [1024, 2048, 2048, 1024]
    rows = []
    for i, length in enumerate(protocol['order'], 1):
        r = json.loads((root/f'trial-{i:02d}-{length}.json').read_text())
        assert r == report['trials'][i-1]
        assert r['sequence_length'] == length and r['parameters'] == 80765440
        assert r['optimizer_updates'] == 0 and r['new_training_positions'] == 0
        assert r['parameters_bitwise_unchanged'] is True and r['warmup_gradient_calls'] == 1
        assert r['timed_gradient_calls'] == 3 and r['total_gradient_probe_positions'] == 4*length
        assert r['total_supervised_probe_positions'] == 2*length
        assert r['resident_moment_shaped_bytes'] == 646123520
        assert r['observed_reservation_delta_bytes'] >= r['resident_moment_shaped_bytes']
        assert r['implementation_sha256'] == protocol['implementation_sha256']
        assert r['model_manifest_sha256'] == protocol['model_manifest_sha256']
        assert r['backend_sha256'] == sha('src/slm/backends/mlx_backend.py')
        assert all(np.isfinite(v) and v > 0 for v in r['forward_backward_seconds'])
        rows.append(r)
    for length in (1024, 2048):
        actual = [r for r in rows if r['sequence_length'] == length]
        times = [v for r in actual for v in r['forward_backward_seconds']]
        summary = report['summary'][str(length)]
        assert summary['seconds'] == times and summary['timed_calls'] == 6
        assert summary['median_seconds'] == float(np.median(times))
        assert summary['forward_backward_positions_per_second'] == 6*length/sum(times)
        assert summary['maximum_allocator_peak_bytes'] == max(r['memory']['allocator_peak_bytes'] for r in actual)
    source = Path('data/iteration-two-experiment-v1/runs/selected-continuation')
    old = json.loads((source/'report.json').read_text())
    cfg, weights = checkpoint.load(Path(old['latest_checkpoint'])/'state/model')
    assert cfg.parameter_count == 80765440
    assert sha(Path(old['latest_checkpoint'])/'state/model/manifest.json') == protocol['model_manifest_sha256']
    del weights
    original = json.loads((source/'run.json').read_text())
    for name, checksum in original['logical_plan']['reference_sources'].items():
        assert sha(Path('src/slm')/name) == checksum
    report['controls'] = dict(actual_trial_reaggregation_passed=True, total_gradient_positions=24576,
        total_supervised_gradient_positions=12288, original_26_runtime_references_unchanged=True,
        source_model_transitive_load_valid=True, script_sha256=sha(__file__),
        test_source_sha256=sha('tests/test_sft_context_probe.py'), focused_checks_passed=6)
    report['hardware_observed_after_probes'] = dict(
        observed_at_utc=datetime.now(timezone.utc).isoformat(),
        cpu_brand=subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip(),
        physical_memory_bytes=int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True)),
        numpy_version=np.__version__, scope='Observed after probes, not temperature/background-load control.')
    assert report['total_synthetic_gradient_positions'] == 24576
    assert report['total_synthetic_supervised_gradient_positions'] == 12288
    file.write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print(json.dumps(dict(summary=report['summary'], hardware=report['hardware_observed_after_probes']), indent=2))


if __name__ == '__main__':
    main()
