#!/usr/bin/env python3
"""Freeze two SFT execution plans before actual weight-import/resource probes."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import json
from pathlib import Path
from slm.data.mixture import build_mixture, MixtureBatches
from slm.data.tokenized import sha
from slm.research_sft_stage import ResearchStageInputs, POLICY


def main():
    root = Path('data/iteration-three-sft-stage-v2')
    if root.exists(): raise FileExistsError(root)
    root.mkdir()
    source = Path('data/iteration-two-experiment-v1/runs/selected-continuation')
    origin = json.loads((source/'run.json').read_text())['spec']
    report = json.loads((source/'report.json').read_text())
    (root/'origin-spec.json').write_text(json.dumps(origin, indent=2, sort_keys=True)+'\n')
    data = Path('data/iteration-three-sft-research-v1')
    tokenizer = Path(origin['tokenizer'])
    prepared = json.loads((data/'preparation.json').read_text())
    policy = Path('configs/iteration-three-sft-research-admission-v1.json')
    tokens = data/'tokens'
    mixture = build_mixture([dict(id='conversation', path=tokens, dataset_hash=sha(tokens/'manifest.json'),
        weight=1, max_passes=2, max_positions=716288)], tokenizer, root/'schedule', objective='sft',
        budget=716288, minimum=716288, group_cap=4096, seed='iteration-three-sft-20261019-v1', max_batches=1900)
    reason = 'Explicit foundation-to-conversation SFT objective change with fresh AdamW; retain source weights, prior counters and all separate physical exposure.'
    trials = {}
    for trial, rate in [('lr-00001', 1e-5), ('lr-00005', 5e-5)]:
        spec = deepcopy(origin)
        spec.update(version=2, policy_file_sha256=sha(policy))
        spec['data'] = dict(kind='mixture', path=str((root/'schedule').resolve()), fingerprint=mixture['dataset_hash'],
                            bindings=dict(conversation=str(tokens.resolve())))
        spec['releases'] = {sha(data/'release/manifest.json'):str((data/'release').resolve())}
        spec['limits'] = dict(updates=475, processed_positions=800130)
        spec['recipe'].update(lr=rate, accumulation_steps=4, warmup_tokens=8192)
        spec['checkpoint'] = dict(every_updates=64, keep=2)
        path = root/(trial+'.json')
        path.write_text(json.dumps(spec, indent=2, sort_keys=True)+'\n')
        inp = ResearchStageInputs(spec, origin, report['latest_checkpoint'], source/'report.json', POLICY, reason)
        try:
            trials[trial] = dict(plan_hash=inp.identity, spec_file_sha256=sha(path),
                                actual_maximum_length=inp.data.max_length, synthetic_preflight_positions=inp.data.max_length*4)
        finally: inp.close()
    with MixtureBatches(root/'schedule', {'conversation':tokens}, tokenizer, mixture['dataset_hash']) as schedule:
        prefix = schedule.counts(256)[0]
        assert schedule.counts(1900) == (800130, 716288)
    result = dict(creator='Navneet Prabhakar', version=1, trials=trials,
        origin_spec_sha256=sha(root/'origin-spec.json'), source_checkpoint=report['latest_checkpoint'],
        source_report=str((source/'report.json').resolve()), transition_reason=reason, mixture=mixture,
        schedule_manifest_sha256=sha(root/'schedule/manifest.json'), data_preparation_sha256=sha(data/'preparation.json'),
        prospective_screen_updates=64, prospective_screen_batches=256,
        prospective_discarded_screen_positions=prefix, prospective_main_positions=800130,
        prospective_combined_positions=800130+prefix, planned_total_preflight_positions=sum(v['synthetic_preflight_positions'] for v in trials.values()),
        source_sha256={str(p):sha(p) for p in map(Path, ['src/slm/research_sft_stage.py','src/slm/sft_research_preflight.py',
            'scripts/probe-research-sft-stage.py','scripts/prepare-research-sft-stage.py'])},
        main_training_started=False, launch_contract_ready=False,
        scope='Execution plans/data order frozen before actual probes. Finite optimizer selection, assessment/scoring contract and launch admission remain separate; no actual SFT learning.')
    assert result['prospective_combined_positions'] <= 1048576 and result['planned_total_preflight_positions'] <= 16384
    (root/'preparation.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    Path('reports/milestone-sixty-two-sft-stage-plans-v2.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
