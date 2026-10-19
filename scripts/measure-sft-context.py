#!/usr/bin/env python3
"""Freeze and run four isolated zero-update context-sizing probes in ABBA order."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
from slm.data.tokenized import sha


ROOT = Path('data/sft-context-sizing-v1')
MODEL = Path('data/iteration-two-experiment-v1/runs/selected-continuation/checkpoints/000000009984-44136fa355b3/state/model')


def main():
    if ROOT.exists(): raise FileExistsError(ROOT)
    source = json.loads(Path('reports/milestone-fifty-five-stage-transition.json').read_text())
    expected = source['actual_probe']['initialization']['source_model_sha256']
    if sha(MODEL/'manifest.json') != expected: raise ValueError('Completed foundation model differs')
    protocol = dict(creator='Navneet Prabhakar', version=1, order=[1024, 2048, 2048, 1024],
        fresh_process_each_trial=True, warmup_gradient_calls_per_trial=1, timed_gradient_calls_per_trial=3,
        model_manifest_sha256=expected, source_receipt_sha256=sha('reports/milestone-fifty-five-stage-transition.json'),
        implementation_sha256=sha('src/slm/eval/sft_context_probe.py'), script_sha256=sha(__file__),
        seed=20261019, optimizer_updates=0, scope='Synthetic forward/backward sizing, resident dummy moment-shaped buffers; not a full optimizer step or language training.')
    ROOT.mkdir()
    (ROOT/'protocol.json').write_text(json.dumps(protocol, indent=2, sort_keys=True)+'\n')
    reports = []
    for i, length in enumerate(protocol['order'], 1):
        output = ROOT/f'trial-{i:02d}-{length}.json'
        command = [sys.executable, '-m', 'slm.eval.sft_context_probe', '--model', str(MODEL),
                   '--model-manifest-sha256', expected, '--output', str(output), '--length', str(length)]
        with output.with_suffix('.log').open('x') as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if process.returncode:
            (ROOT/'failure.json').write_text(json.dumps(dict(trial=i, length=length,
                returncode=process.returncode, scope='No optimizer updates; partial probe logs retained.'), indent=2)+'\n')
            raise RuntimeError('Probe failed; original attempt retained, no automatic replay')
        r = json.loads(output.read_text())
        if (r['model_manifest_sha256'] != expected or r['implementation_sha256'] != protocol['implementation_sha256']
                or r['parameters'] != 80765440 or r['optimizer_updates'] != 0
                or not r['parameters_bitwise_unchanged'] or len(r['forward_backward_seconds']) != 3
                or any(not np.isfinite(v) or v <= 0 for v in r['forward_backward_seconds'])):
            raise ValueError('Actual probe identity/count/timing differs')
        reports.append(r)
        print(json.dumps(dict(trial=i, length=length, seconds=r['forward_backward_seconds'],
                              allocator_peak_bytes=r['memory']['allocator_peak_bytes'])), flush=True)
    if sha(MODEL/'manifest.json') != expected: raise ValueError('Source model identity changed')
    summary = {}
    for length in (1024, 2048):
        rows = [r for r in reports if r['sequence_length'] == length]
        times = [v for r in rows for v in r['forward_backward_seconds']]
        summary[str(length)] = dict(fresh_process_trials=len(rows), timed_calls=len(times),
            seconds=times, median_seconds=float(np.median(times)), min_seconds=min(times), max_seconds=max(times),
            forward_backward_positions_per_second=len(times)*length/sum(times),
            maximum_allocator_peak_bytes=max(r['memory']['allocator_peak_bytes'] for r in rows),
            maximum_process_peak_rss_bytes=max(r['memory']['process_peak_rss_bytes'] for r in rows),
            resident_moment_shaped_bytes=rows[0]['resident_moment_shaped_bytes'])
    result = dict(creator='Navneet Prabhakar', version=1, protocol=protocol,
        protocol_sha256=sha(ROOT/'protocol.json'), trials=reports, summary=summary,
        total_synthetic_gradient_positions=sum(r['total_gradient_probe_positions'] for r in reports),
        total_synthetic_supervised_gradient_positions=sum(r['total_supervised_probe_positions'] for r in reports),
        optimizer_updates=0, language_capability_proved=False,
        scope='Two fresh processes per context, six timed calls each. ABBA ordering reduces order confounding but is not sustained/thermal causal evidence. Finite checks/export/optimizer/data/checkpoint overhead excluded from timing. Allocator/RSS overlap. Memory includes dummy moment buffers but omits optimizer-update scratch. No full-step memory acceptance, real SFT throughput or actual CUDA result.')
    Path('reports/milestone-fifty-seven-context-sizing.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    (ROOT/'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
