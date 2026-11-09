"""Freeze score-four candidate locators without altering source data or weights."""
from collections import Counter
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import sqlite3
import sys
import time

import pyarrow.parquet as pq
from quality_score_probe import ROOT, DATA, RAW, REPORT, sha

OUT = ROOT/'data/fresh-broad-score4-v1'


def main():
    start = time.monotonic()
    os.nice(10)
    def check():
        assert time.monotonic()-start < 1800
        assert shutil.disk_usage(ROOT).free > 20*1024**3
        assert not any(p.exists() for p in [ROOT/'runs/STOP', DATA/'STOP', OUT/'STOP'])
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert rss*(1 if sys.platform == 'darwin' else 1024) < 3*1024**3
    def deadline(*_):
        raise TimeoutError('selection deadline')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(1800)
    check()
    assert not OUT.exists()
    paths = [DATA/'candidate-manifest.json', DATA/'custody.json',
             REPORT/'source-verification.json', REPORT/'quality-review.json',
             REPORT/'quality-score-review.json', RAW/'receipt.json', Path(__file__),
             REPORT/'quality_score_probe.py']
    bindings = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    manifest, custody, verification, review1, review2, receipt = [json.loads(p.read_text()) for p in paths[:6]]
    assert sha(DATA/'candidates.sqlite') == manifest['candidate_database_sha256']
    assert custody['candidate_database_sha256'] == verification['database_sha256'] == manifest['candidate_database_sha256']
    assert verification['state'] == 'PASS_all_retained_source_records_not_admitted'
    assert not verification['failures']
    excluded = set(custody['excluded_domain_families']) | set(review1['excluded_domains']) | set(review2['excluded_domains'])
    denied_ids = set(custody['excluded_doc_ids'])
    OUT.mkdir()
    db = sqlite3.connect(f'file:{DATA / "candidates.sqlite"}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    db.execute('pragma cache_size=-65536')
    counts, rejects = Counter(), Counter()
    scanned = matched = 0
    with (OUT/'selected.jsonl').open('x') as dest:
        for entry in receipt['files']:
            check()
            p = RAW/entry['file']
            assert p.stat().st_size == entry['bytes'] and sha(p) == entry['sha256']
            scores = []
            for batch in pq.ParquetFile(p).iter_batches(batch_size=4096, columns=['id','int_score'], use_threads=False):
                check()
                scores.extend((str(r['id']),int(r['int_score'])) for r in batch.to_pylist())
            scanned += len(scores)
            query = 'select rowid as candidate_rowid,priority,source_file,row_index,doc_id,domain,canonical_url,split,normalized_sha256,raw_sha256,publisher_tokens from documents where source_file=?'
            for n, record in enumerate(db.execute(query, (entry['file'],))):
                if n%4096 == 0:
                    check()
                r = dict(record)
                doc_id, score = scores[r['row_index']]
                assert doc_id == r['doc_id']
                matched += 1
                if r['domain'] in excluded or doc_id in denied_ids:
                    rejects['custody_or_quality_excluded'] += 1
                    continue
                if score < 4:
                    rejects['education_score_below4'] += 1
                    continue
                r['int_score'] = score
                r['raw_source_sha256'] = entry['sha256']
                dest.write(json.dumps(r)+'\n')
                counts[r['split']+'_docs'] += 1
                counts[r['split']+'_publisher_tokens'] += r['publisher_tokens']
            del scores
    db.close()
    assert scanned == 2944000 and matched == 2384706
    assert sum(v for k,v in counts.items() if k.endswith('_docs')) + sum(rejects.values()) == matched
    assert all(sha(ROOT/p) == value for p,value in bindings.items())
    result = dict(state='score4_selection_complete_not_deduplicated_not_admitted',
                  training_admitted=False, counts=dict(counts), rejections=dict(rejects),
                  scanned_raw_rows=scanned, matched_candidate_rows=matched,
                  selected_sha256=sha(OUT/'selected.jsonl'), selected_path=str(OUT/'selected.jsonl'),
                  candidate_database_sha256=manifest['candidate_database_sha256'],
                  excluded_domain_count=len(excluded), bindings=bindings,
                  seconds=time.monotonic()-start,
                  pending=['Near-duplicate screening including historical holdouts', 'GPT2 token packing', 'Independent packing verification', 'Explicit source admission'])
    for p in [OUT/'selection.json', REPORT/'score4-selection.json']:
        p.write_text(json.dumps(result,indent=2)+'\n')
    signal.alarm(0)
    print(json.dumps({k:result[k] for k in ['state','counts','rejections','seconds']}),flush=True)


if __name__ == '__main__':
    main()
