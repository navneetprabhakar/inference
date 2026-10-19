#!/usr/bin/env python3
"""Freeze a fresh crawl-balanced train-only full-document review packet."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path

from slm.data.build import verify
from slm.data.schema import digest
from slm.data.tokenized import sha

ROOT = Path('data/prose-train-review-v1')
STAGED = Path('data/fineweb-prose-candidate-staging-v1/staged')
SEED = 'prose-train-content-review-20261019-v1'


def read(path): return json.loads(path.read_text())
def lines(path): return [json.loads(line) for line in path.read_text().splitlines()]


def publish(path, value):
    with path.open('x') as out: out.write(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    if ROOT.exists(): raise FileExistsError(ROOT)
    verify(STAGED)
    inputs = [Path('data/fineweb-parquet-rowgroup-audit-v1/rows.jsonl'),
              Path('data/fineweb-prose-distributed-audit-v1/rows.jsonl')]
    raw = {r['source_group']: r for path in inputs for r in lines(path)}
    journal = Path('data/fineweb-prose-distributed-audit-v1/direct-judgments.jsonl')
    previous = {r['source_group'] for r in lines(journal)}
    train = [r for path in sorted(STAGED.glob('train-*.jsonl')) for r in lines(path)]
    available = [r for r in train if r['parent_group_id'] not in previous]
    crawls = sorted({raw[r['parent_group_id']]['row']['dump'] for r in available})
    if len(crawls) != 4: raise ValueError('Exactly four current crawl strata required')
    chosen = []; populations = {}
    for crawl in crawls:
        rows = [r for r in available if raw[r['parent_group_id']]['row']['dump'] == crawl]
        if len(rows) < 8: raise ValueError('Eight fresh train candidates per crawl required')
        populations[crawl] = len(rows)
        chosen.extend(sorted(rows, key=lambda r: (digest([SEED, r['parent_group_id']]), r['parent_group_id']))[:8])
    plan = dict(creator='Navneet Prabhakar', kind='crawl-balanced-train-prose-review-v1',
                staged_manifest_sha256=sha(STAGED / 'manifest.json'), seed=SEED, rows_per_crawl=8,
                prior_journal_sha256=sha(journal), raw_input_bindings={str(p): sha(p) for p in inputs},
                script_sha256=sha(__file__), fresh_train_population_by_crawl=populations,
                selection='Eight deterministic hash-priority previously unread train candidates per crawl; unequal inclusion rates, not a corpus-wide acceptance-rate estimate.',
                training_approved=False)
    ROOT.mkdir(); publish(ROOT / 'plan.json', plan)
    with (ROOT / 'review.jsonl').open('x') as out:
        for i, row in enumerate(chosen):
            original = raw[row['parent_group_id']]
            if row['messages'] != [dict(role='text', content=original['row']['text'])]:
                raise ValueError('Unchanged complete original text required')
            record = dict(index=i, source_group=row['parent_group_id'],
                          staged_example_id=row['example_id'], split_group=row['validation_results']['split_group'],
                          raw_record_sha256=original['raw_record_sha256'], row=original['row'])
            out.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + '\n')
    report = dict(creator='Navneet Prabhakar', kind=plan['kind'], plan_sha256=sha(ROOT / 'plan.json'),
                  review_file_sha256=sha(ROOT / 'review.jsonl'), rows=len(chosen),
                  characters=sum(len(raw[r['parent_group_id']]['row']['text']) for r in chosen),
                  crawl_counts=dict(Counter(raw[r['parent_group_id']]['row']['dump'] for r in chosen)),
                  training_approved=False, scope='Frozen review packet; direct full-text judgments pending. No content admission, model score, gradient or source acquisition.')
    publish(ROOT / 'packet.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
