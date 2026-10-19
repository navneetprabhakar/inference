#!/usr/bin/env python3
"""Reopen explicit decisions and compare actual whole-dialogue SFT batches."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import numpy as np
from slm.data.review_stream import open_checked
from slm.data.tokenized import ShardBatches, sha
from slm.common.tokenizer import BPE
from slm.data.schema import digest


def main():
    root = Path('data/iteration-three-sft-review-v2')
    tokenizer = Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    packet = json.loads((root/'decisions.json').read_text())
    preparation = json.loads((root/'preparation.json').read_text())
    report_path = Path('reports/milestone-fifty-four-sft-review.json')
    report = json.loads(report_path.read_text())
    # Frozen admission-map digest from the retained first draft, not its prose note.
    assert digest({eid: e['decision']['approved'] for eid, e in packet['examples'].items()}) == 'c255b05431c02b8130d0ddb3d4e6b5294d673af4c27525f4755d29887f984255'
    assert report['decision_sha256'] == sha(root/'decisions.json')
    assert report['script_sha256'] == sha('scripts/review-iteration-three-sft.py')
    assert preparation['script_sha256'] == sha('scripts/prepare-iteration-three-sft-review.py')
    raw = Path('data/dolly-complete-v1')
    assert sha(raw/'rows.jsonl') == json.loads((raw/'acquisition.json').read_text())['published_sha256']
    expected = {eid: e['record'] for eid, e in packet['examples'].items() if e['decision']['approved'] is True}
    with open_checked(root/'release') as index:
        actual = {eid: json.loads(text) for eid, text in index.db.execute('SELECT eid,data FROM approved')}
        assert set(actual) == set(expected)
        for eid, row in actual.items():
            assert row['messages'] == expected[eid]['messages'] and row['split'] == expected[eid]['split']
            assert row['validation_results']['split_group'] == expected[eid]['validation_results']['split_group']
        train = list(index.values())
    bpe = BPE.load(tokenizer)
    with ShardBatches(root/'tokens', tokenizer) as data:
        assert len(data) == len(train) == 12
        for i, row in enumerate(train):
            expected_batch = bpe.serialize(row['messages'])
            assert all(np.array_equal(a[0], v) for a, v in zip(data[i], expected_batch))
        assert data.counts(len(data)) == (1417, 851)
    report.update(preparation=preparation, token_preparation=json.loads((root/'tokens/report.json').read_text()),
        token_manifest_sha256=sha(root/'tokens/manifest.json'), controls_script_sha256=sha(__file__),
        actual_controls=dict(approved_ids_equal=True, original_messages_and_splits_preserved=True,
            all_12_train_batches_match_whole_dialogue_assistant_masks=True,
            raw_dolly_pinned_hash_matches=True, first_review_note_corrected_no_decision_changes=True),
        primary_reference_checks={
            '25': ['https://www.merriam-webster.com/grammar/the-many-plurals-of-octopus-octopi-octopuses-octopodes'],
            '29': ['https://www.presidentiallibrary.go.ke/presidents/he-daniel-toroitich-arap-moi'],
            '36': ['https://movies.disney.com/the-lion-king', 'https://movies.disney.com/frozen', 'https://movies.disney.com/finding-nemo']},
        limitations='Purposive short-text review, not population quality-rate sampling or broad SFT data. No neural updates, new teacher/API calls, cloud actions or paid training. Existing separate explicit release not merged. Source-relative factual extraction does not certify upstream facts.')
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print('Actual admitted IDs/text/splits/groups and all twelve SFT batches/masks match; 1417 positions / 851 assistant targets.')


if __name__ == '__main__':
    main()
