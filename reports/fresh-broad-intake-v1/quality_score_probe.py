"""Bounded, read-only candidate probe; no packing or training admission."""
import hashlib
import heapq
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import sqlite3
import sys
import time
from collections import Counter

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data/fresh-broad-candidates-v1'
RAW = ROOT / 'data/fresh-broad-intake-v1'
OUT = ROOT / 'data/fresh-broad-quality-probe-v1'
REPORT = Path(__file__).parent
SEED = 'fresh-broad-score4-quality-v1:'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def main():
    start = time.monotonic()
    os.nice(10)
    def check():
        assert time.monotonic() - start < 1800
        assert shutil.disk_usage(ROOT).free > 20 * 1024**3
        assert not any(p.exists() for p in [ROOT/'runs/STOP', DATA/'STOP', OUT/'STOP'])
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert rss * (1 if sys.platform == 'darwin' else 1024) < 3 * 1024**3
    def deadline(*_):
        raise TimeoutError('quality probe deadline')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(1800)
    assert not OUT.exists()
    check()
    manifest = json.loads((DATA/'candidate-manifest.json').read_text())
    assert sha(DATA/'candidates.sqlite') == manifest['candidate_database_sha256']
    custody = json.loads((DATA/'custody.json').read_text())
    assert custody['candidate_database_sha256'] == manifest['candidate_database_sha256']
    review = json.loads((REPORT/'quality-review.json').read_text())
    excluded = set(custody['excluded_domain_families']) | set(review['excluded_domains'])
    previous_ids = {r['doc_id'] for r in review['decisions']}
    OUT.mkdir()
    plan = dict(state='frozen_before_probe', minimum_int_score=4,
                sample_selection='8 lowest SHA256(seed+doc_id) per publisher-token bucket (<256,256-511,512-1023,>=1024); train only, prior sample IDs excluded',
                seed=SEED, training_admitted=False,
                limitation='Higher publisher education score is a hypothesis, not a factuality or prose-quality guarantee.')
    (OUT/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    db = sqlite3.connect(f'file:{DATA / "candidates.sqlite"}?mode=ro', uri=True)
    db.execute('pragma cache_size=-65536')
    db.execute('pragma temp_store=FILE')
    counts = Counter()
    heaps = [[] for _ in range(4)]
    scanned = matched = 0
    for entry in json.loads((RAW/'receipt.json').read_text())['files']:
        check()
        path = RAW/entry['file']
        assert path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256']
        scores = []
        for batch in pq.ParquetFile(path).iter_batches(batch_size=4096, columns=['id', 'int_score'], use_threads=False):
            check()
            scores.extend((str(r['id']), int(r['int_score'])) for r in batch.to_pylist())
        scanned += len(scores)
        cursor = db.execute('select rowid,row_index,doc_id,domain,split,publisher_tokens from documents where source_file=?', (entry['file'],))
        for n, (rowid, offset, doc_id, domain, split, tokens) in enumerate(cursor):
            if n % 4096 == 0:
                check()
            assert scores[offset][0] == doc_id
            score = scores[offset][1]
            matched += 1
            if domain in excluded:
                continue
            counts[f'{split}_score{score}_docs'] += 1
            counts[f'{split}_score{score}_publisher_tokens'] += tokens
            if score < 4 or split != 'train' or doc_id in previous_ids:
                continue
            bucket = 0 if tokens < 256 else 1 if tokens < 512 else 2 if tokens < 1024 else 3
            priority = int(hashlib.sha256((SEED+doc_id).encode()).hexdigest(), 16)
            item = (-priority, rowid, score)
            if len(heaps[bucket]) < 8:
                heapq.heappush(heaps[bucket], item)
            elif item > heaps[bucket][0]:
                heapq.heapreplace(heaps[bucket], item)
        del scores
    assert scanned == 2944000 and matched == 2384706
    samples = []
    for bucket, heap in enumerate(heaps):
        assert len(heap) == 8
        for _, rowid, score in sorted(heap, reverse=True):
            doc_id, domain, url, tokens, raw_sha, text = db.execute('select doc_id,domain,canonical_url,publisher_tokens,raw_sha256,text from documents where rowid=?', (rowid,)).fetchone()
            assert hashlib.sha256(text.encode()).hexdigest() == raw_sha
            samples.append(dict(sample_index=len(samples), bucket=bucket, doc_id=doc_id, domain=domain,
                                url=url, publisher_tokens=tokens, int_score=score, raw_sha256=raw_sha, text=text))
    db.close()
    sample_path = OUT/'sample.jsonl'
    sample_path.write_text(''.join(json.dumps(r)+'\n' for r in samples))
    result = dict(state='score_probe_complete_sample_unreviewed', training_admitted=False,
                  plan=plan, scanned=scanned, matched=matched, counts=dict(counts),
                  sample_rows=len(samples), sample_path=str(sample_path), sample_sha256=sha(sample_path),
                  bindings={str(p.relative_to(ROOT)):sha(p) for p in [DATA/'candidate-manifest.json', DATA/'custody.json', REPORT/'quality-review.json', Path(__file__)]},
                  seconds=time.monotonic()-start)
    for p in [OUT/'result.json', REPORT/'quality-score-probe.json']:
        p.write_text(json.dumps(result, indent=2)+'\n')
    signal.alarm(0)
    print(json.dumps({k:result[k] for k in ['state','scanned','matched','counts','seconds']}), flush=True)


if __name__ == '__main__':
    main()
