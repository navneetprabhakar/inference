#!/usr/bin/env python3
"""Reopen actual rated candidates, their raw paths and non-admission boundary."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.data.build import verify
from slm.data.curation import normalize
from slm.data.review import training_examples
from slm.data.schema import digest
from slm.data.tokenized import sha


def main():
    root = Path('data/oasst-rated-sft-candidates-v1')
    manifest = verify(root)
    result = json.loads((root/'report.json').read_text())
    assert manifest['release'] == 'sample_only' and result['training_eligible'] is False
    assert result['implementation_sha256'] == sha('src/slm/data/oasst_sft_screen.py')
    parent = Path('data/iteration-two-foundation-research-v1')
    assert result['parent_manifest_sha256'] == sha(parent/'manifest.json')
    tokenizer = Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    assert result['tokenizer_manifest_sha256'] == sha(tokenizer/'manifest.json')
    prior_path = Path('data/iteration-three-sft-review-v2/decisions.json')
    assert result['prior_review_sha256'] == sha(prior_path)
    prior = json.loads(prior_path.read_text())
    blocked = {e['record']['validation_results']['split_group'] for e in prior['examples'].values()
               if e['decision']['approved'] is not True}
    candidates = [json.loads(line) for line in (root/'candidates.jsonl').read_text().splitlines()]
    parent_records = {}
    for split in ('train', 'validation', 'test'):
        for path in parent.glob(split+'-*.jsonl'):
            for line in path.open():
                row = json.loads(line)
                if row['source'] == 'OpenAssistant/oasst2':
                    assert row['split'] == split and row['example_id'] not in parent_records
                    parent_records[row['example_id']] = row
    screens = {row['example_id']: row for row in map(json.loads, (root/'screening.jsonl').read_text().splitlines())}
    assert len(screens) == result['examined_paths']
    assert set(screens) == set(parent_records)
    for eid, screen in screens.items():
        parent_row = parent_records[eid]
        assert screen['record_sha256'] == digest(parent_row)
        assert screen['split'] == parent_row['split']
        assert screen['split_group'] == parent_row['validation_results']['split_group']
    source = Path('data/iteration-two-oasst2-snapshot-v1')
    assert result['raw_sha256'] == sha(source/'trees.jsonl')
    assert result['acquisition_sha256'] == sha(source/'acquisition.json')
    needed = {key for row in candidates for key in row['lineage']}
    nodes = {}
    for line in (source/'trees.jsonl').open():
        stack = [json.loads(line)['prompt']]
        while stack:
            node = stack.pop()
            if node['message_id'] in needed:
                assert node['message_id'] not in nodes
                nodes[node['message_id']] = node
            stack.extend(node['replies'])
    assert set(nodes) == needed
    groups = set()
    totals, turns = Counter(), Counter()
    bpe = BPE.load(tokenizer)
    for row in candidates:
        assert row == parent_records[row['example_id']]
        gid = row['validation_results']['split_group']
        assert row['source'] == 'OpenAssistant/oasst2' and gid not in groups and gid not in blocked
        groups.add(gid)
        assert len(row['lineage']) == len(row['messages'])
        for i, (key, message) in enumerate(zip(row['lineage'], row['messages'])):
            node = nodes[key]
            assert normalize(node['text']) == message['content']
            assert node['parent_id'] == (row['lineage'][i-1] if i else None)
            assert node['role'] == ('assistant' if message['role'] == 'assistant' else 'prompter')
            assert node['lang'] == 'en' and node['synthetic'] is False and node['deleted'] is False
            assert node['review_result'] is True and node['model_name'] is None
            flags = ['spam', 'lang_mismatch', 'pii', 'not_appropriate', 'hate_speech', 'sexual_content']
            if message['role'] == 'assistant':
                assert type(node['rank']) is int and node['rank'] == 0
                flags.append('fails_task')
                for name in ('quality', 'helpfulness'):
                    label = node['labels'][name]
                    assert type(label['count']) is int and label['count'] >= 2
                    assert type(label['value']) in (int, float) and .75 <= label['value'] <= 1
            for name in flags:
                label = node['labels'][name]
                assert type(label['count']) is int and label['count'] >= 1
                assert type(label['value']) in (int, float) and label['value'] == 0
        x, _, mask = bpe.serialize(row['messages'])
        assert len(x) <= 2048 and sum(mask) >= 16
        screen = screens[row['example_id']]
        assert screen['record_sha256'] == digest(row) and screen['split_group'] == gid
        assert screen['split'] == row['split'] and screen['reasons'] == []
        assert screen['training_eligible'] is False
        assert screen['hypothetical_prediction_positions'] == len(x)
        assert screen['hypothetical_assistant_targets'] == sum(mask)
        split = row['split']
        totals.update({split+'_rows': 1, split+'_positions': len(x), split+'_assistant_targets': sum(mask)})
        turns[split+'|'+str(len(row['messages'])//2)] += 1
    assert dict(totals) == result['candidate_counts'] and dict(turns) == result['turns']
    pending = [json.loads(line) for line in (root/'sample.jsonl').read_text().splitlines()]
    expected = [row for row in candidates if row['split'] == 'train'][:64]
    assert [s['record'] for s in pending] == expected
    assert len(pending) == result['pending_train_review_rows']
    for i, sample in enumerate(pending):
        assert sample['index'] == i and sample['record_sha256'] == digest(sample['record'])
        assert sample['full_text_read'] is False and sample['judgment'] is None and sample['training_approved'] is False
    try:
        next(training_examples(root))
    except ValueError as exc:
        assert 'sample-only data is refused' in str(exc)
    else:
        raise AssertionError('Unadmitted candidate stage accepted for training')
    run = json.loads(Path('data/iteration-two-experiment-v1/runs/selected-continuation/run.json').read_text())
    references = run['logical_plan']['reference_sources']
    assert len(references) == 26 and all(sha(Path('src/slm')/p) == checksum for p, checksum in references.items())
    report = dict(creator='Navneet Prabhakar', measured=result, manifest_sha256=sha(root/'manifest.json'),
        candidate_file_sha256=sha(root/'candidates.jsonl'), sample_sha256=sha(root/'sample.jsonl'),
        controls_script_sha256=sha(__file__), test_source_sha256=sha('tests/test_oasst_sft_screen.py'),
        controls=dict(all_candidate_raw_paths_ratings_counts_and_masks_reopened=True,
                      one_path_per_existing_group=True, prior_nonapproval_groups_absent=True,
                      all_parent_records_and_original_splits_match_exactly=True, sample_only_training_refused=True,
                      original_26_runtime_sources_unchanged=True),
        full_text_reviews=0, training_approved=False, new_model_updates=0,
        scope='Actual candidate measurement and independent raw-rating/path checks. Publisher labels and mechanical validity are not direct quality review, semantic decontamination or corpus/SFT admission. No new download, teacher/API/cloud call, paid work or student generation.')
    target = Path('reports/milestone-fifty-nine-oasst-rated-sft-v2.json')
    payload = json.dumps(report, indent=2, sort_keys=True)+'\n'
    if target.exists():
        assert target.read_text() == payload, 'Existing receipt differs; retain and version explicitly'
    else:
        target.write_text(payload)
    print(json.dumps(dict(counts=dict(totals), turns=dict(turns), pending_review_rows=len(pending),
                          checked_candidate_rows=len(candidates)), indent=2))


if __name__ == '__main__':
    main()
