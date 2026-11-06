"""Freeze three future-parent optimizer templates without starting training."""
import json
from pathlib import Path
import platform
import time

from gpt2 import Config
from optimizer_ablation_train import RUNTIME, validate_spec
from optimizer_ablation_supervise import digest, validate_spec as validate_experiment, verify_frozen

ROOT = Path(__file__).resolve().parent
REPORT = ROOT/'reports/optimizer-ablation-v1'


def create(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    protocol_path = REPORT/'protocol.json'
    protocol = json.loads(protocol_path.read_text())
    if protocol['status'] != 'approved_for_runtime_freeze':
        raise ValueError('protocol has not been reviewed')
    outputs = [REPORT/f'{name}.template.json' for name in
               ('preserve-095', 'reset-095', 'reset-scaled')]
    outputs += [REPORT/'experiment.json', REPORT/'freeze-receipt.json']
    if any(path.exists() for path in outputs):
        raise ValueError('freeze output already exists; never rewrite an active specification')
    foundation_path = ROOT/'reports/base-foundation-100m/budget.json'
    foundation = json.loads(foundation_path.read_text())
    assert digest(foundation_path) == protocol['parent']['spec_sha256']
    for name, expected in foundation['code_sha256'].items():
        assert digest(ROOT/name) == expected, name
    files = set(RUNTIME) | {'base_supervise.py', 'optimizer_ablation_supervise.py',
                            'optimizer_ablation_report.py', 'freeze_optimizer_ablation.py',
                            'verify_optimizer_ablation_train.py', 'verify_optimizer_ablation_supervise.py',
                            'verify_optimizer_ablation_report.py'}
    pins = {name: digest(ROOT/name) for name in sorted(files)}
    common = protocol['common']
    template = {key: common[key] for key in ('source_offset', 'target_tokens', 'length',
                 'microbatch', 'targets_per_update', 'seed', 'bf16', 'manifest_sha256',
                 'validation_blocks_sha256', 'diagnostics_sha256')}
    template.update(corpus=str(ROOT/common['corpus']), diagnostics=str(ROOT/common['diagnostics']),
                    scheduler={key: protocol['scheduler'][key] for key in
                               ('mode', 'start_lr', 'peak_lr', 'warmup_tokens', 'horizon_tokens')},
                    active_seconds=protocol['budgets']['per_arm_active_seconds'],
                    lease_seconds=protocol['budgets']['lease_seconds'],
                    calendar_seconds=protocol['budgets']['experiment_calendar_seconds'],
                    protocol_path=str(protocol_path), protocol_sha256=digest(protocol_path), code_sha256=pins,
                    authorization='User approved corrected three-arm plan and hands-off local continuation on 2026-11-06; own random lineage only, no paid compute.')
    manifest = json.loads((Path(template['corpus'])/'manifest.json').read_text())
    assert common['source_offset']+common['target_tokens'] < manifest['shards']['fineweb-train']['tokens']
    arms = []
    for arm in protocol['arms']:
        name = arm['name']
        value = dict(template, branch=name)
        validate_spec(value, Config(), 'mps')
        path = REPORT/f'{name}.template.json'
        create(path, value)
        arms.append(dict(name=name, run=str(ROOT/'runs'/f'optimizer-ablation-v1-{name}'),
                         template=str(path), template_sha256=digest(path)))
    experiment = dict(schema=1, parent=dict(run=str(ROOT/protocol['parent']['run']),
                     spec=str(foundation_path), spec_sha256=digest(foundation_path),
                     required_trained_tokens=protocol['parent']['required_trained_tokens']),
                     arms=arms, active_seconds=protocol['budgets']['aggregate_active_seconds'],
                     target_tokens=protocol['budgets']['aggregate_attempted_targets_ceiling'],
                     calendar_seconds=protocol['budgets']['experiment_calendar_seconds'],
                     code_sha256={str(ROOT/name): sha for name, sha in pins.items()},
                     protocol_path=str(protocol_path), protocol_sha256=digest(protocol_path))
    validate_experiment(experiment)
    verify_frozen(experiment)
    create(REPORT/'experiment.json', experiment)
    create(REPORT/'freeze-receipt.json', dict(state='frozen_waiting_for_parent', recorded_at=time.time(),
           python=platform.python_version(), files={str(path.relative_to(ROOT)): digest(path)
              for path in outputs[:-1]+[protocol_path, REPORT/'PROTOCOL.md']}, runtime=pins,
           verification='Trainer tiny CPU parity/recovery, 27 supervisor CPU subprocess cases, and report decision tests passed; independent trainer/report review found no blocking correctness issue.',
           parent_binding='No endpoint weights selected yet. Supervisor binds the exact verified completed foundation endpoint into immutable branch specifications.',
           usable_model=False))
    print('Frozen optimizer experiment:', REPORT/'experiment.json')


if __name__ == '__main__':
    main()
