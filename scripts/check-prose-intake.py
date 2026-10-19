#!/usr/bin/env python3
"""Reconstruct actual screening and audit sample-only grouping lineage."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path

from slm.common.tokenizer import BPE
from slm.data.build import verify
from slm.data.prose_screen import RULE, RequestGuard, screen
from slm.data.quality_audit import top_scores
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.eval.cases import candidate_suite
from slm.eval.tool_cases import tool_cases


def read(path): return json.loads(path.read_text())
def lines(path): return [json.loads(line) for line in path.read_text().splitlines()]


def require(value, reason):
    if not value: raise ValueError(reason)


def main():
    root = Path('data/fineweb-prose-screen-v1'); plan = read(root / 'plan.json')
    require(plan['rule'] == RULE, 'Screen rules differ')
    for path, expected in plan['input_bindings'].items(): require(sha(path) == expected, 'Pinned screen input differs')
    records = {}
    for path in ('data/fineweb-parquet-rowgroup-audit-v1/rows.jsonl', 'data/fineweb-prose-distributed-audit-v1/rows.jsonl'):
        for record in lines(Path(path)):
            require(digest(record['row']) == record['raw_record_sha256'], 'Raw row differs')
            records[record['source_group']] = record['row']
    requests = [m['content'] for c in candidate_suite()['cases'] for m in c['messages'] if m['role'] == 'user']
    requests.extend(m['content'] for c in tool_cases() for m in c['history'] if m['role'] == 'user')
    history = [Path(p) for p in plan['input_bindings'] if p.endswith('/turns.jsonl')]
    requests.extend(r['user'] for path in history for r in lines(path))
    guard = RequestGuard(requests)
    require(guard.fingerprint == plan['protected_request_fingerprint'], 'Protected request set differs')
    scores = [top_scores(s) for s in (root / 'predictions.txt').read_text().splitlines()]
    from slm.data.prose_screen import windows
    frozen = read(Path('data/smol-content-review-v2/staged/heldout-groups.json'))
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    expected = []; cursor = 0
    for group, raw in sorted(records.items()):
        count = len(windows(raw['text']))
        decision = screen(raw, scores[cursor:cursor + count], guard, plan['prior_judgments'].get(group), frozen.get(group))
        cursor += count
        expected.append(dict(source_group=group, **decision, actual_student_bpe_content_tokens=len(bpe.encode(raw['text']))))
    require(cursor == len(scores) and expected == lines(root / 'screened.jsonl'), 'Actual screening differs')
    screen_report = read(root / 'report.json')
    require(sha(root / 'screened.jsonl') == screen_report['screen_file_sha256'], 'Published screen hash differs')
    require(screen_report == read(Path('reports/milestone-sixty-nine-prose-screen.json')), 'Published screen report differs')
    require(screen_report['candidate_groups'] == sum(r['candidate'] for r in expected), 'Reported candidate count differs')
    require(screen_report['reason_counts'] == dict(Counter(reason for r in expected for reason in r['reasons'])), 'Reported reasons differ')
    stage_root = Path('data/fineweb-prose-candidate-staging-v1'); staged = stage_root / 'staged'
    stage_plan = read(stage_root / 'plan.json'); stage_report = read(stage_root / 'report.json')
    require(sha(stage_root / 'plan.json') == stage_report['plan_sha256'], 'Staging plan differs')
    require(sha(root / 'report.json') == stage_plan['screen_report_sha256'], 'Stage uses another screen')
    require(sha('scripts/stage-prose-candidates.py') == stage_plan['script_sha256'], 'Stage source differs')
    require(sha(staged / 'manifest.json') == stage_report['staged_manifest_sha256'], 'Staged manifest differs')
    verify(staged)
    selected = {r['source_group']: r for r in expected if r['candidate']}
    candidates = lines(stage_root / 'candidate-prose.jsonl')
    require({r['parent_group_id'] for r in candidates} == set(selected), 'Candidate membership differs')
    for row in candidates:
        group = row['parent_group_id']
        require(row['messages'] == [dict(role='text', content=records[group]['text'])], 'Candidate text differs')
        require(row['validation_results']['prose_candidate_screen']['raw_record_sha256'] == digest(records[group]), 'Candidate lineage differs')
    output = {}
    for split in ('train', 'validation', 'test'):
        for path in staged.glob(split + '-*.jsonl'):
            for row in lines(path): output[row['example_id']] = row
    ancestor = {}
    for split in ('validation', 'test'):
        for path in Path('data/smol-content-review-v2/staged').glob(split + '-*.jsonl'):
            for row in lines(path): ancestor[row['example_id']] = row
    require(set(ancestor) <= set(output), 'Ancestral heldout row missing')
    for eid, prior in ancestor.items():
        require(output[eid]['messages'] == prior['messages'], 'Ancestral heldout text changed')
        require(output[eid]['split'] != 'train', 'Ancestral heldout entered train')
    promotions = sum(output[eid]['split'] != row['split'] for eid, row in ancestor.items())
    require(promotions == 0, 'Actual ancestral partition changed; stop before admission')
    changes = sum(output[r['example_id']]['messages'] != r['messages'] for r in candidates if r['example_id'] in output)
    splits = Counter(output[r['example_id']]['split'] for r in candidates if r['example_id'] in output)
    tokens = Counter()
    for row in candidates:
        if row['example_id'] in output:
            tokens[output[row['example_id']]['split']] += len(bpe.encode(row['messages'][0]['content']))
    automatic_misses = sum(r['prior_direct_judgment'] in ('defer', 'exclude') and
                           not [reason for reason in r['reasons'] if not reason.startswith('prior_direct_')]
                           for r in expected)
    result = dict(creator='Navneet Prabhakar', kind='actual-prose-intake-check-v1', passed=True,
                  checker_sha256=sha(__file__), screen_plan_sha256=sha(root / 'plan.json'),
                  staged_manifest_sha256=sha(staged / 'manifest.json'), screened_groups=len(expected),
                  retained_candidate_groups=sum(splits.values()), candidate_split_counts=dict(splits),
                  candidate_content_tokens_by_split=dict(tokens),
                  prior_nonapprovals_passing_automatic_signals_alone=automatic_misses,
                  cleaner_changed_candidate_texts=changes, missing_candidate_ids=len(candidates) - sum(splits.values()),
                  ancestral_heldout_rows_preserved=len(ancestor), ancestral_partition_changes=promotions,
                  training_approved=False,
                  scope='All actual screen decisions reconstructed from retained language predictions; unchanged detector hashes verified without rerunning CLI. Candidate raw lineage and existing staged manifest checked, every ancestral heldout text/partition preserved. No independent subjective content/rights/factual approval.')
    Path('reports/milestone-sixty-nine-intake-check.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
