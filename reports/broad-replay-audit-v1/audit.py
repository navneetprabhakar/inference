"""Read-only full TRAIN replay audit; never admits data or reads protected prompts."""
import hashlib
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tokenizer import load


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    started = time.monotonic()
    source = ROOT / 'data/base-foundation-100m'
    output = Path(__file__).with_name('result.json')
    if output.exists():
        raise ValueError('Preserve existing audit result')
    manifest = json.loads((source / 'manifest.json').read_text())
    assert sha(source / 'documents.jsonl') == manifest['documents_sha256']
    assert sha(source / 'custody.json') == manifest['custody_receipt_sha256']
    assert sha(source / 'candidates.sqlite') == manifest['candidate_database_sha256']
    excluded = set()
    custody = []
    for name in ('custody.json', 'conversation-custody.json'):
        p = source / name
        receipt = json.loads(p.read_text())
        assert receipt['state'] == 'cleared'
        assert receipt['candidate_database_sha256'] == manifest['candidate_database_sha256']
        excluded.update(receipt['excluded_doc_ids'])
        custody.append({'path': str(p), 'sha256': sha(p)})
    docs = [json.loads(line) for line in (source / 'documents.jsonl').open()]
    groups = {s: {d['group'] for d in docs if d['split'] == s}
              for s in ('train', 'validation')}
    assert not groups['train'] & groups['validation']
    fingerprints = {s: {d['normalized_sha256'] for d in docs if d['split'] == s}
                    for s in groups}
    assert not fingerprints['train'] & fingerprints['validation']
    train = [d for d in docs if d['split'] == 'train']
    assert not {d['document_id'] for d in train} & excluded
    p = source / 'fineweb-train.u16'
    expected = manifest['shards']['fineweb-train']
    assert p.stat().st_size == expected['tokens'] * 2 and sha(p) == expected['sha256']
    tokens = np.memmap(p, dtype='<u2', mode='r')
    database = sqlite3.connect(f'file:{source / "candidates.sqlite"}?mode=ro', uri=True)
    tokenizer = load()
    offset = 0
    counts = Counter()
    for d in train:
        assert d['offset'] == offset and d['tokens'] > 1
        chunk = tokens[offset:offset + d['tokens']]
        assert len(chunk) == d['tokens'] and chunk[-1] == 50256
        assert np.all(chunk[:-1] < 50256)
        row = database.execute('select doc_id, split, raw_sha256, text from documents where priority=?',
                               (d['order_sha256'],)).fetchone()
        assert row and row[:3] == (d['document_id'], 'train', d['raw_sha256'])
        assert hashlib.sha256(row[3].encode()).hexdigest() == d['raw_sha256']
        assert tokenizer.decode(chunk[:-1].tolist()) == row[3]
        offset += d['tokens']
        counts[d['group']] += d['tokens']
    assert offset == len(tokens) == expected['tokens'] and len(train) == expected['docs']
    database.close()
    result = dict(state='PASS_existing_train_replay_integrity_not_admission',
                  manifest_sha256=sha(source / 'manifest.json'), custody=custody,
                  documents=len(train), tokens=offset, full_source_decodes=len(train),
                  domains=len(counts), maximum_domain_tokens=max(counts.values()),
                  seconds=time.monotonic()-started, training_admitted=False,
                  limitations=['Existing TRAIN is replay, not new unique text.',
                               'Historical custody is revalidated; newer development overlap remains to be checked.',
                               'No semantic quality or assistant capability certification.',
                               'Validation contents were not decoded or promoted into TRAIN.'])
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
