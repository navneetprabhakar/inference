#!/usr/bin/env python3
"""Screen finite acquired prose locally; never publish a training release."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path

from slm.common.tokenizer import BPE
from slm.data.prose_screen import RULE, RequestGuard, screen, windows
from slm.data.quality_audit import LIMITS, predict, top_scores
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.eval.cases import candidate_suite
from slm.eval.tool_cases import tool_cases

ROOT = Path('data/fineweb-prose-screen-v1')
INPUTS = [Path('data/fineweb-parquet-rowgroup-audit-v1/rows.jsonl'),
          Path('data/fineweb-prose-distributed-audit-v1/rows.jsonl')]
HISTORY = [Path(p) for p in ('data/iteration-one-conversation-assessment-v1/turns.jsonl',
           'data/iteration-two-conversation-assessment-v1/turns.jsonl',
           'data/iteration-three-sft-experiment-v1/conversation/turns.jsonl',
           'data/iteration-four-fitting-control-v2/conversation/turns.jsonl')]


def read(path): return json.loads(path.read_text())
def lines(path): return [json.loads(line) for line in path.read_text().splitlines()]


def publish(path, value):
    with path.open('x') as out: out.write(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    if ROOT.exists(): raise FileExistsError(ROOT)
    descriptor = Path('data/language-detector-v4/detector.json')
    detector = read(descriptor)
    binary, model = (Path(detector[k]) for k in ('binary', 'model'))
    for path, field in ((binary, 'binary_sha256'), (model, 'model_sha256')):
        if sha(path) != detector[field]: raise ValueError('Pinned detector differs')
    artifacts = [Path('data/fineweb-parquet-rowgroup-audit-v1/result.json'),
                 Path('data/fineweb-prose-distributed-audit-v1/acquisition.json')]
    for path, receipt, key in zip(INPUTS, artifacts, ('row_file_sha256', 'row_file_sha256')):
        if sha(path) != read(receipt)[key]: raise ValueError('Acquisition rows differ')
    if sum(p.stat().st_size for p in INPUTS) > 16 * 1024**2: raise ValueError('Input byte limit exceeded')
    records = {}
    for path in INPUTS:
        for record in lines(path):
            group = record['source_group']
            if record['raw_record_sha256'] != digest(record['row']): raise ValueError('Raw row digest differs')
            if group in records and records[group]['row'] != record['row']: raise ValueError('Conflicting source identity')
            records[group] = record
    if len(records) != 1048: raise ValueError('Expected exact finite 1048-group intake')
    frozen_path = Path('data/smol-content-review-v2/staged/heldout-groups.json')
    if sha(frozen_path) != read(frozen_path.parent / 'manifest.json')['files'][frozen_path.name]:
        raise ValueError('Heldout artifact differs')
    frozen = read(frozen_path)
    journal_path = Path('data/fineweb-prose-distributed-audit-v1/direct-judgments.jsonl')
    review = Path('data/fineweb-prose-distributed-audit-v1/review-report.json')
    if sha(journal_path) != read(review)['judgment_file_sha256']: raise ValueError('Direct judgments differ')
    judgments = {r['source_group']: r['judgment'] for r in lines(journal_path)}
    requests = [m['content'] for c in candidate_suite()['cases'] for m in c['messages'] if m['role'] == 'user']
    requests.extend(m['content'] for c in tool_cases() for m in c['history'] if m['role'] == 'user')
    requests.extend(r['user'] for path in HISTORY for r in lines(path))
    guard = RequestGuard(requests)
    paths = [*INPUTS, *artifacts, *HISTORY, descriptor, binary, model, frozen_path, journal_path, review,
             Path(__file__), Path('src/slm/data/prose_screen.py'), Path('src/slm/data/quality_audit.py'),
             Path('src/slm/data/curation.py'), Path('src/slm/eval/cases.py'), Path('src/slm/eval/tool_cases.py')]
    bindings = {str(p): sha(p) for p in paths}
    plan = dict(creator='Navneet Prabhakar', kind='finite-prose-candidate-screen-v1', rule=RULE,
                input_bindings=bindings, distinct_groups=len(records), protected_requests=len(guard.requests),
                protected_request_fingerprint=guard.fingerprint, max_windows=10000,
                prior_judgments=judgments, training_approved=False,
                scope='Candidate selection only; no actual text rewrite, factual/privacy/content verification, deduplication, split reassignment or corpus admission.')
    ROOT.mkdir(); publish(ROOT / 'plan.json', plan)
    ordered = sorted(records)
    counts = []
    with (ROOT / 'language-input.txt').open('x') as out:
        for group in ordered:
            row = records[group]['row']
            if len(row['text']) > RULE['max_characters']: raise ValueError('Whole row exceeds finite screen scope')
            parts = windows(row['text']); counts.append(len(parts))
            if sum(counts) > plan['max_windows']: raise ValueError('Language window cap exceeded')
            for part in parts: out.write(part['text'].replace('\n', ' ').replace('\r', ' ') + '\n')
    predict(binary, model, ROOT / 'language-input.txt', ROOT / 'predictions.txt', LIMITS)
    predictions = lines_as_predictions = (ROOT / 'predictions.txt').read_text().splitlines()
    if len(predictions) != sum(counts): raise ValueError('Prediction count differs')
    scores = [top_scores(line) for line in predictions]
    results = []; cursor = 0
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    for group, count in zip(ordered, counts):
        raw = records[group]['row']
        if group != 'HuggingFaceFW/fineweb-edu:' + raw['id']: raise ValueError('Source-group identity differs')
        decision = screen(raw, scores[cursor:cursor + count], guard, judgments.get(group), frozen.get(group))
        cursor += count
        results.append(dict(source_group=group, **decision,
                            actual_student_bpe_content_tokens=len(bpe.encode(raw['text']))))
    for path, expected in bindings.items():
        if sha(path) != expected: raise ValueError('Screen input or implementation changed')
    with (ROOT / 'screened.jsonl').open('x') as out:
        for decision in results: out.write(json.dumps(decision, sort_keys=True) + '\n')
    report = dict(creator='Navneet Prabhakar', kind=plan['kind'], plan_sha256=sha(ROOT / 'plan.json'),
                  screen_file_sha256=sha(ROOT / 'screened.jsonl'), records=len(results),
                  candidate_groups=sum(r['candidate'] for r in results),
                  candidate_content_tokens=sum(r['actual_student_bpe_content_tokens'] for r in results if r['candidate']),
                  reason_counts=dict(Counter(reason for r in results for reason in r['reasons'])),
                  language_windows=sum(counts), protected_requests=len(guard.requests),
                  prior_nonapprovals_remaining_candidates=sum(r['candidate'] and r['prior_direct_judgment'] in ('defer', 'exclude') for r in results),
                  frozen_heldouts_remaining_candidates=sum(r['candidate'] and r['original_frozen_partition'] is not None for r in results),
                  candidate_crawls=dict(Counter(records[r['source_group']]['row']['dump'] for r in results if r['candidate'])),
                  training_approved=False, scope=plan['scope'])
    publish(ROOT / 'report.json', report)
    publish(Path('reports/milestone-sixty-nine-prose-screen.json'), report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
