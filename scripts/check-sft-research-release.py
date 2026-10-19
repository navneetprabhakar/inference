#!/usr/bin/env python3
"""Reopen every actual admitted row and SFT batch, plus the historical exact import."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import numpy as np
from slm.common import checkpoint
from slm.common.tokenizer import BPE
from slm.data.review_stream import open_checked
from slm.data.schema import digest
from slm.data.sft_research import open_research
from slm.data.tokenized import ShardBatches, sha


def main():
    root = Path('data/iteration-three-sft-research-v1')
    receipt = json.loads((root/'preparation.json').read_text())
    release = root/'release'
    tokenizer = Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    policy = Path('configs/iteration-three-sft-research-admission-v1.json')
    ph = sha(policy)
    assert receipt['policy_file_sha256'] == ph
    assert receipt['release_manifest_sha256'] == sha(release/'manifest.json')
    assert receipt['token_manifest_sha256'] == sha(root/'tokens/manifest.json')
    assert receipt['reader_sha256'] == sha('src/slm/data/sft_research.py')
    assert receipt['token_builder_sha256'] == sha('src/slm/data/sft_research_tokens.py')
    assert receipt['script_sha256'] == sha('scripts/prepare-sft-research-release.py')
    originals = {r['example_id']: r for r in map(json.loads, (release/'candidate-candidates.jsonl').read_text().splitlines())}
    decisions = json.loads((release/'review-report.json').read_text())['effective_decisions']
    blocked_ids = {d['example_id'] for d in decisions if d['judgment'] != 'consider'}
    read_ids = {d['example_id'] for d in decisions if d['judgment'] == 'consider'}
    blocked_groups = {originals[eid]['validation_results']['split_group'] for eid in blocked_ids}
    expected = {eid: row for eid, row in originals.items() if row['validation_results']['split_group'] not in blocked_groups}
    bpe = BPE.load(tokenizer)
    with open_research(release, ph) as admitted:
        actual = {eid: json.loads(data) for eid, data in admitted.db.execute('SELECT eid,data FROM approved')}
        assert set(actual) == set(expected) and len(actual) == 1137
        for eid, row in actual.items():
            before = expected[eid]
            copy = json.loads(json.dumps(row))
            proof = copy['validation_results'].pop('sft_research_admission')
            assert copy == before
            assert proof['original_record_sha256'] == digest(before) and proof['policy_file_sha256'] == ph
            assert proof['individual_quality_verified'] is False and proof['human_attestation'] is False
            assert proof['individually_read'] == (eid in read_ids)
            assert row['validation_results']['split_group'] not in blocked_groups
        train = list(admitted.values())
        assert len(train) == 950 and len(read_ids) == 25 and len(blocked_groups) == 39
        assert sum(row['split'] == 'validation' for row in actual.values()) == 109
        assert sum(row['split'] == 'test' for row in actual.values()) == 78
        with ShardBatches(root/'tokens', tokenizer) as batches:
            assert len(batches) == 950 and batches.counts(950) == (400065, 358144)
            for i, row in enumerate(train):
                x, y, mask = bpe.serialize(row['messages'], objective='assistant')
                for got, wanted in zip(batches[i], (x, y, mask)):
                    assert np.array_equal(got, [wanted]), (i, row['example_id'])
            max_length = batches.max_length
    try:
        with open_checked(release):
            raise AssertionError('Historical reader unexpectedly admitted new schema')
    except ValueError:
        pass
    source_run = Path('data/iteration-two-experiment-v1/runs/selected-continuation')
    old_launch = json.loads((source_run/'run.json').read_text())
    for name, value in old_launch['logical_plan']['reference_sources'].items():
        assert sha(Path('src/slm')/name) == value
    assert len(old_launch['logical_plan']['reference_sources']) == 26
    old_report = json.loads((source_run/'report.json').read_text())
    old = Path(old_report['latest_checkpoint'])
    prior_probe = Path('data/iteration-three-transition-probe-v2/mlx')
    probe_report = json.loads((prior_probe/'report.json').read_text())
    probe_launch = json.loads((prior_probe/'run.json').read_text())
    assert probe_launch['logical_plan']['reference_sources']['stage_transition.py'] == sha('src/slm/stage_transition.py')
    new = Path(probe_report['latest_checkpoint'])
    for folder in (old, new):
        for filename in ('manifest.json', 'state/manifest.json'):
            path = folder/filename
            for name, checksum in json.loads(path.read_text()).items():
                assert sha(path.parent/name) == checksum
    a, weights = checkpoint.load(old/'state/model')
    b, imported = checkpoint.load(new/'state/model')
    assert a == b and a.parameter_count == 80765440 and set(weights) == set(imported)
    assert all(np.array_equal(value.view(np.uint32), imported[key].view(np.uint32)) for key, value in weights.items())
    proof = dict(exact_tensors=len(weights), exact_fp32_values=sum(v.size for v in weights.values()),
                 source_model_sha256=sha(old/'state/model/manifest.json'),
                 historical_import_model_sha256=sha(new/'state/model/manifest.json'))
    del weights, imported
    report = dict(creator='Navneet Prabhakar', preparation=receipt,
        control_script_sha256=sha(__file__), test_source_sha256=sha('tests/test_sft_research.py'),
        actual_controls=dict(all_1137_rows_match_original_text_splits_groups_and_metadata=True,
            known_39_nonapproval_groups_absent=True, all_950_sft_batches_match_shared_serializer=True,
            counts=dict(prediction_positions=400065, assistant_targets=358144),
            maximum_actual_prediction_length=max_length, read_train=25, unread_train=925,
            original_26_runtime_sources_unchanged=True, historical_reader_refuses_new_schema=True,
            historical_exact_import_reopened=proof),
        new_student_updates=0, capability_accepted=False,
        scope='Actual research release/token integrity and historical checkpoint recheck. Not all-row semantic/privacy/content verification, new training, complete-step preflight or CUDA evidence.')
    file = Path('reports/milestone-sixty-one-sft-research-controls.json')
    payload = json.dumps(report, indent=2, sort_keys=True)+'\n'
    if file.exists():
        assert file.read_text() == payload, 'Retain prior receipt and explicitly version changes'
    else:
        file.write_text(payload)
    print(json.dumps(report['actual_controls'], indent=2))


if __name__ == '__main__':
    main()
