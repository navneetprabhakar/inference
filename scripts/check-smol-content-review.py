#!/usr/bin/env python3
"""Bind direct full-text judgments to the pinned, non-admitted review sample."""
# Creator: Navneet Prabhakar
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import unicodedata

from slm.common.tokenizer import BPE
from slm.data.build import verify
from slm.data.review import training_examples
from slm.data.schema import digest
from slm.data.tokenized import sha

ROOT = Path('data/smol-content-review-v2')
ANCESTOR = Path('data/iteration-two-foundation-candidates-v1/staged')
AUDIT = Path('data/smol-smoltalk-audit-v1')
SOURCE = 'HuggingFaceTB/smol-smoltalk'


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check_judgments(samples, decisions, sample_hash):
    if len(samples) != 64 or len(decisions) != 64:
        raise ValueError('Exactly 64 complete direct decisions required')
    for i, (sample, decision) in enumerate(zip(samples, decisions)):
        record = sample['record']
        expected = dict(index=i, example_id=record['example_id'],
                        record_sha256=digest(record), sample_sha256=sample_hash,
                        full_text_read=True, review_mode='delegated_expert',
                        human_attestation=False, training_approved=False)
        if any(type(decision.get(k)) is not type(v) or decision[k] != v
               for k, v in expected.items()):
            raise ValueError('Decision identity/read/scope binding differs')
        if decision.get('judgment') not in ('consider', 'exclude', 'defer'):
            raise ValueError('Unknown direct judgment')
        if not isinstance(decision.get('reason'), str) or len(decision['reason'].strip()) < 40:
            raise ValueError('Specific direct reason required')


def main():
    preparation = json.loads((ROOT/'preparation.json').read_text())
    for path, key in ((ROOT/'staged/manifest.json', 'staged_manifest_sha256'),
                      (ROOT/'sample.jsonl', 'sample_sha256'),
                      (AUDIT/'sample/rows.jsonl', 'sample_input_sha256'),
                      (ANCESTOR/'manifest.json', 'frozen_ancestor_manifest_sha256'),
                      (Path('data/iteration-two-foundation-research-v1/manifest.json'), 'parent_manifest_sha256'),
                      (Path('scripts/prepare-smol-content-review.py'), 'script_sha256')):
        if sha(path) != preparation[key]:
            raise ValueError('Preparation identity differs: '+str(path))
    for root in (ROOT/'staged', ANCESTOR):
        verify(root)
    staged = {}
    for split in ('train', 'validation', 'test'):
        for path in sorted((ROOT/'staged').glob(split+'-*.jsonl')):
            for record in read_rows(path):
                if record['example_id'] in staged:
                    raise ValueError('Duplicate staged example')
                staged[record['example_id']] = record
    protected = 0
    rank = dict(train=0, validation=1, test=2)
    for split in ('validation', 'test'):
        for path in sorted(ANCESTOR.glob(split+'-*.jsonl')):
            for old in read_rows(path):
                new = staged[old['example_id']]
                if new['messages'] != old['messages'] or rank[new['split']] < rank[old['split']]:
                    raise ValueError('Protected heldout lost, changed or demoted')
                protected += 1
    if protected != preparation['frozen_rows_preserved'] or protected != 5692:
        raise ValueError('Protected heldout population differs')
    raw = read_rows(AUDIT/'sample/rows.jsonl')
    source_rows = [r for r in staged.values() if r['source'] == SOURCE]
    if len(raw) != 200 or len(source_rows) != 200 or len(staged) != 5892:
        raise ValueError('Bounded source population differs')
    seen_indices = set()
    normalized_dialogues = 0
    for record in source_rows:
        origin = record['validation_results']['synthetic_origin']
        index = origin['prefix_index']
        if index in seen_indices or not 0 <= index < 200:
            raise ValueError('Source prefix identity differs')
        seen_indices.add(index)
        original = raw[index]
        expected_messages = [dict(role=m['role'], content=unicodedata.normalize('NFC', m['content']).replace('\r\n', '\n').strip())
                             for m in original['messages']]
        normalized_dialogues += record['messages'] != original['messages']
        if (origin['raw_row'] != digest(original) or origin['raw_messages'] != digest(original['messages'])
                or record['messages'] != expected_messages or origin['constituent'] != original['source']
                or origin['acquisition_sha256'] != sha(AUDIT/'sample/acquisition.json')
                or origin['training_eligible'] is not False or origin['quality_verified'] is not False):
            raise ValueError('Original source text/constituent/non-admission differs')
    samples = read_rows(ROOT/'sample.jsonl')
    decisions = read_rows(ROOT/'direct-judgments.jsonl')
    sample_hash = sha(ROOT/'sample.jsonl')
    check_judgments(samples, decisions, sample_hash)
    groups = set()
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    totals = defaultdict(Counter)
    by_tag = defaultdict(Counter)
    for i, (sample, decision) in enumerate(zip(samples, decisions)):
        record = sample['record']
        group = record['validation_results']['split_group']
        if (sample['index'] != i or sample['record_sha256'] != digest(record)
                or staged[record['example_id']] != record or record['source'] != SOURCE
                or record['split'] != 'train' or group in groups
                or sample['training_approved'] is not False or sample['full_text_read'] is not False
                or sample['quality_judgment'] is not None):
            raise ValueError('Frozen unread-packet identity or distinct train grouping differs')
        groups.add(group)
        x, _, mask = bpe.serialize(record['messages'])
        if len(x) > 2048:
            raise ValueError('Whole dialogue exceeds candidate context')
        status = decision['judgment']
        tag = record['validation_results']['synthetic_origin']['constituent']
        by_tag[tag][status] += 1
        totals[status].update(rows=1, hypothetical_prediction_positions=len(x),
                              hypothetical_assistant_targets=sum(mask))
    # Binding controls cannot establish semantic quality or whether a reader actually read text.
    controls = 0
    for field, replacement in (('full_text_read', False), ('record_sha256', '0'*64),
                               ('sample_sha256', '0'*64), ('training_approved', True),
                               ('human_attestation', True), ('index', True), ('reason', '')):
        changed = deepcopy(decisions)
        changed[0][field] = replacement
        try:
            check_judgments(samples, changed, sample_hash)
        except ValueError:
            controls += 1
        else:
            raise ValueError('Mutated decision accepted: '+field)
    for changed in (decisions[:-1], list(reversed(decisions))):
        try:
            check_judgments(samples, changed, sample_hash)
        except ValueError:
            controls += 1
        else:
            raise ValueError('Incomplete or reordered decisions accepted')
    try:
        next(training_examples(ROOT/'staged'))
    except ValueError as exc:
        if 'sample-only data is refused' not in str(exc):
            raise
    else:
        raise ValueError('Sample-only training unexpectedly accepted')
    run = json.loads(Path('data/iteration-two-experiment-v1/runs/selected-continuation/run.json').read_text())
    references = run['logical_plan']['reference_sources']
    if len(references) != 26 or any(sha(Path('src/slm')/p) != value for p, value in references.items()):
        raise ValueError('Original runtime sources changed')
    report = dict(creator='Navneet Prabhakar', version=1,
        preparation=preparation, preparation_sha256=sha(ROOT/'preparation.json'),
        sample_sha256=sample_hash, direct_judgments_sha256=sha(ROOT/'direct-judgments.jsonl'),
        control_script_sha256=sha(__file__), decisions=decisions,
        full_dialogues_read=64, distinct_train_groups=64, outcomes=dict(Counter(d['judgment'] for d in decisions)),
        outcomes_by_constituent=dict(by_tag), hypothetical_reviewed_token_counts=dict(totals),
        controls=dict(protected_heldout_rows=protected, raw_source_hashes_and_constituents_preserved=True,
                      staged_text_matches_nfc_newline_boundary_normalization=True,
                      normalized_source_dialogues=normalized_dialogues,
                      sample_membership_and_decision_binding=True, rejected_mutations=controls,
                      sample_only_training_refused=True, original_26_runtime_sources_unchanged=True),
        training_approved=False, human_attestation=False, new_model_updates=0,
        limitations='Direct delegated judgments on a purposive 64-dialogue sample from a 200-row train prefix. Not a random population estimate, specialist fact certification, rights clearance, corpus admission, training exposure or a new model assessment. Consider is only a quality consideration with stated limitations; exclude is an observed defect; defer is verification/scope uncertainty. Original raw bytes are retained; staging applies existing NFC/newline/boundary-whitespace normalization, without semantic rewrites. Technical checks bind statements, not semantic correctness or proof of reading.')
    output = Path('reports/milestone-fifty-eight-smol-content-review.json')
    rendered = json.dumps(report, indent=2, sort_keys=True)+'\n'
    if output.exists() and output.read_text() != rendered:
        raise ValueError('Existing receipt differs; preserve it and declare a new version')
    if not output.exists():
        output.write_text(rendered)
    print(json.dumps(dict(outcomes=report['outcomes'], by_constituent=report['outcomes_by_constituent'],
                          hypothetical_counts=report['hypothetical_reviewed_token_counts'], controls=report['controls']), indent=2))


if __name__ == '__main__':
    main()
