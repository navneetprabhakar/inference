"""Separate full retained-record replay against pinned raw shards; no admission."""
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import sqlite3
import sys
import time
import unicodedata

import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from own_base_dev_run import atomic


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    start=time.monotonic();d=ROOT/'data/fresh-broad-candidates-v1';raw=ROOT/'data/fresh-broad-intake-v1'
    output=d/'source-verification.json';assert not output.exists();os.nice(10)
    def guard():
        assert time.monotonic()-start<5400 and shutil.disk_usage(ROOT).free>20*1024**3
        assert not (ROOT/'runs/STOP').exists() and not (d/'STOP').exists()
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<4*1024**3
    def deadline(*args):raise TimeoutError('source replay deadline')
    signal.signal(signal.SIGALRM,deadline);signal.alarm(5400)
    try:
        m=json.loads((d/'candidate-manifest.json').read_text());mh=sha(d/'candidate-manifest.json')
        assert m['state']=='candidate_extraction_complete_not_admitted' and not m['training_admitted']
        assert sha(d/'candidates.sqlite')==m['candidate_database_sha256']
        receipt=json.loads((raw/'receipt.json').read_text());assert sha(raw/'receipt.json')==m['source_receipt_sha256']
        for name,h in m['code_sha256'].items():assert sha(ROOT/name)==h
        p=ROOT/'reports/base-foundation-100m/build.py';s=importlib.util.spec_from_file_location('old_filter',p)
        helper=importlib.util.module_from_spec(s);s.loader.exec_module(helper);domains=helper.Domains()
        prior_hashes=set();prior_urls=set();held_domains=set();held_ids=set()
        for name,h in m['previous_document_indexes'].items():
            p=ROOT/name;assert sha(p)==h
            for line in p.open():
                row=json.loads(line)
                if row.get('normalized_sha256'):prior_hashes.add(row['normalized_sha256'])
                url=row.get('canonical_url',row.get('group',''));domain,canonical=domains.canonical(url) if isinstance(url,str) and url.startswith('http') else (None,None)
                if canonical:prior_urls.add(canonical)
                if row.get('split') in ('validation','val','dev','test'):
                    if domain:held_domains.add(domain)
                    if row.get('document_id'):held_ids.add(row['document_id'])
                    if name=='data/base-foundation-100m/documents.jsonl':held_domains.add(row['group'])
        excluded=set(json.loads((ROOT/'data/broad-replay-v1/manifest.json').read_text())['excluded_domain_families'])
        db=sqlite3.connect(f'file:{d}/candidates.sqlite?mode=ro',uri=True)
        db.execute('pragma temp_store=FILE');db.execute('pragma cache_size=-65536')
        assert db.execute('pragma quick_check').fetchone()==('ok',)
        # Sort only row locators; fetch text by rowid without a multi-GB text sort.
        cursor=iter(db.execute('select rowid,source_file,row_index from documents order by source_file,row_index'))
        pending=next(cursor,None);counts=Counter();scanned=0
        for entry in sorted(receipt['files'],key=lambda e:e['file']):
            guard();p=raw/entry['file'];assert p.stat().st_size==entry['bytes'] and sha(p)==entry['sha256']
            index=0
            for batch in pq.ParquetFile(p).iter_batches(batch_size=128,use_threads=False):
                guard()
                for original in batch.to_pylist():
                    key=(entry['file'],index);index+=1;scanned+=1
                    if pending is None or (pending[1],pending[2])!=key:
                        assert pending is None or (pending[1],pending[2])>key
                        continue
                    row=db.execute('select priority,doc_id,domain,canonical_url,split,normalized_sha256,raw_sha256,publisher_tokens,text from documents where rowid=?',(pending[0],)).fetchone()
                    priority,identifier,domain,url,split,norm,rawhash,n,text=row
                    assert identifier==str(original['id']) and text==original['text'] and n==original['token_count']
                    assert helper.quality(original) is None
                    assert (domain,url)==domains.canonical(original['url']) and domain not in excluded
                    expected_norm=hashlib.sha256(' '.join(unicodedata.normalize('NFKC',text).casefold().split()).encode()).hexdigest()
                    assert norm==expected_norm and rawhash==hashlib.sha256(text.encode()).hexdigest()
                    assert norm not in prior_hashes and url not in prior_urls and identifier not in held_ids
                    expected_split='validation' if domain in held_domains or int(hashlib.sha256((m['split_salt']+'split'+domain).encode()).hexdigest()[:8],16)%50==0 else 'train'
                    assert split==expected_split
                    assert priority==hashlib.sha256(('forge-fresh-broad-20261109-order'+identifier).encode()).hexdigest()
                    counts[split+'_docs']+=1;counts[split+'_publisher_tokens']+=n
                    pending=next(cursor,None)
                if scanned%16384==0:atomic(d/'source-verification-progress.json',dict(scanned=scanned,verified=sum(counts[s+'_docs'] for s in ('train','validation')),seconds=time.monotonic()-start))
        assert pending is None and scanned==m['scanned']==2944000 and dict(counts)==m['counts']
        db.close();guard();assert sha(d/'candidates.sqlite')==m['candidate_database_sha256'] and sha(d/'candidate-manifest.json')==mh
        result=dict(state='PASS_all_retained_source_records_not_admitted',failures=[],training_admitted=False,
                    database_sha256=m['candidate_database_sha256'],manifest_sha256=mh,scanned_raw_rows=scanned,
                    verified_rows=sum(counts[s+'_docs'] for s in ('train','validation')),counts=dict(counts),seconds=time.monotonic()-start,
                    scope='Every retained text and provenance field replayed against pinned raw source; prior hash/URL exclusions and inherited split rules checked. Shared pinned quality/domain helpers reused; no proof that every rejected row needed rejection.',
                    pending='Near-duplicate and quality screening; token packing; independent packing verification; source admission')
        atomic(output,result);atomic(Path(__file__).parent/'source-verification.json',result);print(json.dumps(result))
    finally:signal.alarm(0)


if __name__=='__main__':main()
