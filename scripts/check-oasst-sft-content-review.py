#!/usr/bin/env python3
"""Bind direct readings and measure a proposed bounded SFT selection, without training."""
# Creator: Navneet Prabhakar
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from slm.common.tokenizer import BPE
from slm.data.build import verify
from slm.data.review import training_examples
from slm.data.schema import digest
from slm.data.tokenized import sha

CANDIDATES = Path('data/oasst-rated-sft-candidates-v1')
REVIEW = Path('data/oasst-rated-sft-review-v1')


def check_decisions(samples, decisions, sample_hash):
    if len(samples) != 64 or len(decisions) != 64:
        raise ValueError('Exactly 64 direct whole-dialogue decisions required')
    for i, (sample, decision) in enumerate(zip(samples, decisions)):
        row = sample['record']
        binding = dict(index=i, example_id=row['example_id'], record_sha256=digest(row),
                       sample_sha256=sample_hash, full_text_read=True, review_mode='delegated_expert',
                       human_attestation=False, training_approved=False)
        if any(type(decision.get(k)) is not type(v) or decision[k] != v for k, v in binding.items()):
            raise ValueError('Direct review identity/read/authority binding differs')
        if decision.get('judgment') not in ('consider', 'exclude', 'defer'):
            raise ValueError('Unknown direct outcome')
        if not isinstance(decision.get('reason'), str) or len(decision['reason'].strip()) < 40:
            raise ValueError('Specific direct reason required')


def main():
    verify(CANDIDATES)
    measured = json.loads(Path('reports/milestone-fifty-nine-oasst-rated-sft-v2.json').read_text())
    if sha(CANDIDATES/'manifest.json') != measured['manifest_sha256']:
        raise ValueError('Frozen candidate artifact differs')
    samples = [json.loads(line) for line in (CANDIDATES/'sample.jsonl').read_text().splitlines()]
    decisions = [json.loads(line) for line in (REVIEW/'direct-judgments.jsonl').read_text().splitlines()]
    sample_hash = sha(CANDIDATES/'sample.jsonl')
    if sample_hash != measured['sample_sha256']:
        raise ValueError('Frozen sample differs')
    check_decisions(samples, decisions, sample_hash)
    amendment = json.loads((REVIEW/'amendments.json').read_text())
    if (amendment['version'] != 1 or amendment['prior_journal_sha256'] != sha(REVIEW/'direct-judgments.jsonl')
            or amendment['review_mode'] != 'delegated_expert' or amendment['human_attestation'] is not False
            or amendment['training_approved'] is not False or len(amendment['amendments']) != 1):
        raise ValueError('Review amendment authority/history differs')
    effective = deepcopy(decisions)
    correction = amendment['amendments'][0]
    old = effective[correction['index']]
    if (correction['index'] != 63 or correction['example_id'] != old['example_id']
            or correction['record_sha256'] != old['record_sha256']
            or correction['original_judgment'] != old['judgment'] or old['judgment'] != 'defer'
            or correction['judgment'] != 'exclude' or len(correction['reason']) < 40):
        raise ValueError('Specific primary-verified amendment differs')
    old.update(judgment=correction['judgment'], reason=correction['reason'],
               primary_references=correction['primary_references'])
    references = json.loads((REVIEW/'reference-verification.json').read_text())
    if {r['index'] for r in references['references']} != {23, 63}:
        raise ValueError('Expected primary verification coverage differs')
    for reference in references['references']:
        path = Path(reference['path'])
        if path.is_absolute() or '..' in path.parts or sha(REVIEW/path) != reference['sha256']:
            raise ValueError('Primary source snapshot differs')
    code = (REVIEW/'references/coreutils-v9.7-remove.c').read_text()
    if not all(fragment in code for fragment in ('dot_or_dotdot', 'refusing to remove', 'in effect -- default')):
        raise ValueError('Expected GNU safeguards absent')
    maven = (REVIEW/'references/maven-install-observed.html').read_text()
    if 'Java Development Kit' not in maven or 'JAVA_HOME' not in maven:
        raise ValueError('Expected official prerequisite evidence absent')
    candidates = [json.loads(line) for line in (CANDIDATES/'candidates.jsonl').read_text().splitlines()]
    population = {row['example_id']: row for row in candidates}
    if len(population) != 1176:
        raise ValueError('Measured population differs')
    blocked = set()
    groups = set()
    for sample, decision in zip(samples, effective):
        row = sample['record']
        gid = row['validation_results']['split_group']
        if row != population[row['example_id']] or row['split'] != 'train' or gid in groups:
            raise ValueError('Sample train membership/distinct groups differ')
        groups.add(gid)
        if decision['judgment'] != 'consider':
            blocked.add(gid)
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    outcome_counts = {name: Counter() for name in ('consider', 'exclude', 'defer')}
    for sample, decision in zip(samples, effective):
        x, _, mask = bpe.serialize(sample['record']['messages'])
        outcome_counts[decision['judgment']].update(rows=1, prediction_positions=len(x), assistant_targets=sum(mask))
    selection_counts = Counter()
    retained = []
    for row in candidates:
        if row['validation_results']['split_group'] in blocked:
            continue
        x, _, mask = bpe.serialize(row['messages'])
        split = row['split']
        selection_counts.update({split+'_rows': 1, split+'_positions': len(x), split+'_assistant_targets': sum(mask)})
        retained.append(dict(example_id=row['example_id'], record_sha256=digest(row), split=split,
                             split_group=row['validation_results']['split_group']))
    negative_controls = 0
    for field, value in (('full_text_read', False), ('human_attestation', True), ('training_approved', True),
                         ('record_sha256', '0'*64), ('sample_sha256', '0'*64), ('index', True), ('reason', '')):
        mutated = deepcopy(decisions)
        mutated[0][field] = value
        try:
            check_decisions(samples, mutated, sample_hash)
        except ValueError:
            negative_controls += 1
        else:
            raise ValueError('Mutated decision accepted')
    for mutated in (decisions[:-1], list(reversed(decisions))):
        try:
            check_decisions(samples, mutated, sample_hash)
        except ValueError:
            negative_controls += 1
        else:
            raise ValueError('Incomplete/reordered decisions accepted')
    try:
        next(training_examples(CANDIDATES))
    except ValueError as exc:
        if 'sample-only data is refused' not in str(exc):
            raise
    else:
        raise ValueError('Unadmitted candidates accepted for training')
    run = json.loads(Path('data/iteration-two-experiment-v1/runs/selected-continuation/run.json').read_text())
    refs = run['logical_plan']['reference_sources']
    if len(refs) != 26 or any(sha(Path('src/slm')/name) != value for name, value in refs.items()):
        raise ValueError('Original runtime sources differ')
    report = dict(creator='Navneet Prabhakar', version=1,
        candidate_manifest_sha256=sha(CANDIDATES/'manifest.json'), sample_sha256=sample_hash,
        journal_sha256=sha(REVIEW/'direct-judgments.jsonl'), amendments_sha256=sha(REVIEW/'amendments.json'),
        references_sha256=sha(REVIEW/'reference-verification.json'), references=references,
        initial_outcomes=dict(Counter(d['judgment'] for d in decisions)),
        effective_outcomes=dict(Counter(d['judgment'] for d in effective)), effective_decisions=effective,
        counts_by_outcome=outcome_counts, full_dialogues_read=64, distinct_train_groups=64,
        hypothetical_selection=dict(status='proposed_not_admitted', excluded_known_groups=len(blocked),
            counts=dict(selection_counts), original_unread_train_rows_retained=925,
            individually_considered_train_rows_retained=25, retained_membership_sha256=digest(retained)),
        controls=dict(exact_sample_and_candidate_bindings=True, source_checks_bound=True,
            rejected_decision_controls=negative_controls, sample_only_training_refused=True,
            original_candidate_manifest_payloads_unchanged=True, original_26_runtime_sources_unchanged=True),
        control_script_sha256=sha(__file__), training_approved=False, human_attestation=False, new_model_updates=0,
        limitations='Direct delegated review of a seeded selected pool, not population quality estimation or complete specialist fact-checking. Consider means bounded research consideration with stated limitations, not factual gold. Exclude records an observed defect; defer records uncertainty/scope. Proposed removal of 39 known nonapproval groups leaves 925 unread train rows and grants no SFT admission. Technical bindings do not prove semantics or actual reading. No new teacher/model API call, cloud action or paid activity.')
    target = Path('reports/milestone-sixty-oasst-sft-content-review.json')
    rendered = json.dumps(report, indent=2, sort_keys=True)+'\n'
    if target.exists():
        if target.read_text() != rendered:
            raise ValueError('Existing receipt differs; retain and explicitly version')
    else:
        target.write_text(rendered)
    print(json.dumps(dict(outcomes=report['effective_outcomes'], token_counts=outcome_counts,
                          proposed=report['hypothetical_selection'], controls=report['controls']), indent=2))


if __name__ == '__main__':
    main()
