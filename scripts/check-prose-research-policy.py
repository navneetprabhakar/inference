#!/usr/bin/env python3
"""Reopen the actual balanced review and finite private-research decision."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path

from slm.common.tokenizer import BPE
from slm.data.build import verify
from slm.data.schema import digest
from slm.data.tokenized import sha


def read(path): return json.loads(path.read_text())
def lines(path): return [json.loads(line) for line in path.read_text().splitlines()]


def require(condition, reason):
    if not condition: raise ValueError(reason)


def check(policy):
    require(policy['version'] == 1 and policy['kind'] == 'fineweb-finite-prose-research-v1' and
            policy['status'] == 'accepted_for_bounded_private_research', 'Policy identity differs')
    root = Path('data/prose-train-review-v1')
    stage = Path('data/fineweb-prose-candidate-staging-v1/staged')
    plan, packet, report = (read(root / name) for name in ('plan.json', 'packet.json', 'review-report.json'))
    verify(stage)
    require(sha(stage / 'manifest.json') == plan['staged_manifest_sha256'] == policy['staged_manifest_sha256'], 'Staged origin differs')
    require(sha(root / 'plan.json') == packet['plan_sha256'], 'Review plan differs')
    require(sha('scripts/prepare-prose-train-review.py') == plan['script_sha256'], 'Packet implementation differs')
    for path, expected in plan['raw_input_bindings'].items(): require(sha(path) == expected, 'Raw acquisition differs')
    old_path = Path('data/fineweb-prose-distributed-audit-v1/direct-judgments.jsonl')
    require(sha(old_path) == plan['prior_journal_sha256'] == policy['prior_journal_sha256'], 'Prior nonapprovals differ')
    raw = {r['source_group']: r for path in plan['raw_input_bindings'] for r in lines(Path(path))}
    all_rows = [r for split in ('train', 'validation', 'test') for path in stage.glob(split + '-*.jsonl') for r in lines(path)]
    previous = {r['source_group'] for r in lines(old_path)}
    available = [r for r in all_rows if r['split'] == 'train' and r['parent_group_id'] not in previous]
    selected = []
    for crawl, count in sorted(plan['fresh_train_population_by_crawl'].items()):
        current = [r for r in available if raw[r['parent_group_id']]['row']['dump'] == crawl]
        require(len(current) == count, 'Review stratum differs')
        selected.extend(sorted(current, key=lambda r: (digest([plan['seed'], r['parent_group_id']]), r['parent_group_id']))[:8])
    reviewed = lines(root / 'review.jsonl'); journal = lines(root / 'direct-judgments.jsonl')
    require(len(reviewed) == len(journal) == len(selected) == 32, 'Complete 32-row packet/journal required')
    require(sha(root / 'review.jsonl') == packet['review_file_sha256'] == report['review_file_sha256'], 'Review bytes differ')
    require(sha(root / 'direct-judgments.jsonl') == report['journal_sha256'] == policy['review_journal_sha256'], 'Journal differs')
    for i, (row, decision, staged) in enumerate(zip(reviewed, journal, selected)):
        require(row['index'] == decision['index'] == i and row['source_group'] == decision['source_group'] == staged['parent_group_id'], 'Review order/selection differs')
        require(row['row'] == raw[row['source_group']]['row'] and digest(row['row']) == row['raw_record_sha256'] == decision['raw_record_sha256'], 'Reviewed original text differs')
        require(decision['full_text_read'] is True and decision['review_file_sha256'] == sha(root / 'review.jsonl'), 'Reading declaration missing')
        require(decision['judgment'] in ('consider', 'exclude', 'defer') and bool(decision['reason']), 'Incomplete decision')
        require(all(decision[k] is False for k in ('human_attestation', 'training_approved', 'factual_accuracy_verified', 'underlying_document_rights_verified')), 'Unsupported individual clearance')
    require(dict(Counter(d['judgment'] for d in journal)) == report['outcomes'], 'Outcome counts differ')
    evidence = root / 'references/receipt.json'
    require(sha(evidence) == report['primary_reference_receipt_sha256'] == journal[12]['specific_primary_reference_receipt_sha256'], 'Specific factual reference differs')
    require(read(evidence)['doi'] == '10.1351/goldbook.A00279', 'Primary terminology reference differs')
    decisions = {r['source_group']: r['judgment'] for r in lines(old_path) + journal}
    retained = sorted([r for r in all_rows if r['source'] == policy['source']['source_id'] and decisions.get(r['parent_group_id']) not in ('exclude', 'defer')], key=lambda r: r['example_id'])
    expected = [dict(example_id=r['example_id'], source_group=r['parent_group_id'], split=r['split'], split_group=r['validation_results']['split_group'], canonical_record_sha256=digest(r)) for r in retained]
    require(expected == read(root / 'retained-membership.json'), 'Exact research membership differs')
    require(sha(root / 'retained-membership.json') == policy['retained_membership_sha256'] == report['retained_membership_sha256'], 'Research membership hash differs')
    require(dict(Counter(r['split'] for r in retained)) == policy['expected_rows'] == report['retained_counts'], 'Split counts differ')
    train = [r for r in retained if r['split'] == 'train']
    considered = sum(decisions.get(r['parent_group_id']) == 'consider' for r in train)
    require(considered == policy['directly_considered_train'] == 19 and len(train) - considered == policy['unread_train'] == 758, 'Read/unread distinction differs')
    require(policy['source'] == read(stage / 'sources.json')['HuggingFaceFW/fineweb-edu'], 'Source evidence differs')
    require(sha('data/main-learning-budget-research-v1/commoncrawl-terms.html') == policy['commoncrawl_terms_sha256'], 'Underlying-source terms differ')
    require(sha(root / 'review-report.json') == policy['review_report_sha256'] and read(Path('reports/milestone-seventy-prose-review.json')) == report, 'Published report differs')
    require(policy['schema_version'] == 6 and policy['training_ready'] is False and policy['human_attestation'] is False, 'Readiness/attestation changed')
    require(policy['training_devices'] == ['mlx:default', 'torch:cpu'] and policy['selection']['automatic_source_expansion'] is False, 'Device/source scope changed')
    require(policy['limits'] == dict(physical_data_positions=2000000, optimizer_updates=4096, max_physical_passes_per_group=2, max_parameters=100000000, max_context=2048), 'Finite research ceilings differ')
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    require(sum(len(bpe.encode(r['messages'][0]['content'])) for r in train) == report['retained_train_content_tokens'], 'Actual content-token count differs')
    return dict(creator='Navneet Prabhakar', kind='actual-prose-research-policy-check-v1', passed=True,
                policy_canonical_digest=digest(policy),
                checker_sha256=sha(__file__), review_rows=32, outcomes=report['outcomes'], retained_rows=policy['expected_rows'],
                directly_considered_train=considered, unread_train=len(train) - considered, training_ready=False,
                scope='Actual deterministic sample/journal/source/count/membership and policy bounds checked; subjective judgments and legal/factual conclusions are not independently certified. No checked training reader or launch authorization implied.')


if __name__ == '__main__':
    policy = read(Path('configs/prose-foundation-research-admission-v1.json'))
    result = check(policy)
    Path('reports/milestone-seventy-policy-check.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2))
