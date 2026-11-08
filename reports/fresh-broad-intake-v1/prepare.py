"""Finite candidate extraction with inherited domain splits; no training admission."""
from collections import Counter
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

import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
OLD=ROOT/'reports/base-foundation-100m/build.py'
spec=importlib.util.spec_from_file_location('foundation_builder',OLD)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
RAW=ROOT/'data/fresh-broad-intake-v1'
OUT=ROOT/'data/fresh-broad-candidates-v1'


def main():
    start=time.monotonic();assert not OUT.exists();os.nice(10)
    def check():
        assert time.monotonic()-start<3600 and shutil.disk_usage(ROOT).free>30*1024**3
        assert not (ROOT/'runs/STOP').exists() and not (RAW/'STOP').exists() and not (OUT/'STOP').exists()
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        assert rss<4*1024**3
    def deadline(*args):raise TimeoutError('candidate extraction deadline')
    signal.signal(signal.SIGALRM,deadline);signal.alarm(3600)
    check();receipt=json.loads((RAW/'receipt.json').read_text())
    assert receipt['state']=='verified_raw_shards_not_admitted' and not receipt['training_admitted']
    for entry in receipt['files']:
        check();p=RAW/entry['file'];assert p.stat().st_size==entry['bytes'] and base.checksum(p)==entry['sha256']
    domains=base.Domains();old_hashes,old_urls,old_receipts=base.previous_documents(domains)
    held_domains=set();held_ids=set();rejected_domains=set()
    # The old deterministic domain split salt is retained. Explicit historical
    # validation domains also override a proposed TRAIN assignment.
    prior=[ROOT/p for p in old_receipts]+[ROOT/'data/base-foundation-100m/documents.jsonl']
    for p in prior:
        old_receipts[str(p.relative_to(ROOT))]=base.checksum(p)
        for line in p.open():
            d=json.loads(line)
            if d.get('normalized_sha256'):old_hashes.add(d['normalized_sha256'])
            url=d.get('canonical_url',d.get('group',''))
            domain,canonical=domains.canonical(url) if isinstance(url,str) and url.startswith('http') else (None,None)
            if canonical:old_urls.add(canonical)
            if d.get('split') in ('validation','val','dev','test'):
                if domain:held_domains.add(domain)
                if d.get('document_id'):held_ids.add(d['document_id'])
    old_source=json.loads((ROOT/'data/base-foundation-100m/manifest.json').read_text())
    assert base.checksum(ROOT/'reports/base-foundation-100m/public_suffix_list.dat')==old_source['source']['psl_sha256']
    for line in (ROOT/'data/base-foundation-100m/documents.jsonl').open():
        d=json.loads(line)
        if d['split']=='validation':held_domains.add(d['group'])
    replay=json.loads((ROOT/'data/broad-replay-v1/manifest.json').read_text())
    rejected_domains.update(replay['excluded_domain_families'])
    OUT.mkdir();db=sqlite3.connect(OUT/'candidates.sqlite');db.execute('pragma journal_mode=DELETE')
    db.execute('create table documents (priority text primary key, source_file text, row_index integer, doc_id text unique, domain text, canonical_url text unique, split text, normalized_sha256 text unique, raw_sha256 text, publisher_tokens integer, text text)')
    counts=Counter();rejects=Counter();scanned=0
    try:
        for entry in receipt['files']:
            row_index=0
            for batch in pq.ParquetFile(RAW/entry['file']).iter_batches(batch_size=256,use_threads=False):
                check()
                for row in batch.to_pylist():
                    current=row_index;row_index+=1;scanned+=1
                    reason=base.quality(row)
                    if reason:rejects[reason]+=1;continue
                    domain,url=domains.canonical(row['url'])
                    if not domain:rejects['invalid_url']+=1;continue
                    if domain in rejected_domains:rejects['prior_public_overlap_domain']+=1;continue
                    norm=base.digest(base.normalized(row['text']).encode())
                    if norm in old_hashes or url in old_urls or str(row['id']) in held_ids:
                        rejects['previous_document_or_url']+=1;continue
                    split='validation' if domain in held_domains or int(base.digest((base.SALT+'split'+domain).encode())[:8],16)%50==0 else 'train'
                    priority=base.digest(('forge-fresh-broad-20261109-order'+str(row['id'])).encode())
                    try:
                        db.execute('insert into documents values (?,?,?,?,?,?,?,?,?,?,?)',
                          (priority,entry['file'],current,str(row['id']),domain,url,split,norm,
                           base.digest(row['text'].encode()),int(row['token_count']),row['text']))
                    except sqlite3.IntegrityError:rejects['exact_text_url_or_source_id_duplicate']+=1;continue
                    counts[split+'_docs']+=1;counts[split+'_publisher_tokens']+=int(row['token_count'])
                db.commit()
                if scanned%8192==0:base.write_json(OUT/'progress.json',dict(scanned=scanned,counts=dict(counts),seconds=time.monotonic()-start))
        db.execute('create index domain_split on documents(domain,split)');db.commit()
        assert db.execute('pragma quick_check').fetchone()==('ok',)
    finally:db.close();signal.alarm(0)
    assert scanned==2944000
    result=dict(state='candidate_extraction_complete_not_admitted',training_admitted=False,
                candidate_database_sha256=base.checksum(OUT/'candidates.sqlite'),scanned=scanned,
                counts=dict(counts),rejections=dict(rejects),source_receipt_sha256=base.checksum(RAW/'receipt.json'),
                previous_document_indexes=old_receipts,heldout_domain_count=len(held_domains),
                excluded_public_domain_count=len(rejected_domains),split_salt=base.SALT,
                code_sha256={str(OLD.relative_to(ROOT)):base.checksum(OLD),str(Path(__file__).relative_to(ROOT)):base.checksum(Path(__file__))},
                seconds=time.monotonic()-start,pending=['Near-duplicate screening','Full protected/historical/public custody','Quality review','Actual GPT2 token counting and packing','Independent verification and admission'])
    base.write_json(OUT/'candidate-manifest.json',result)
    base.write_json(Path(__file__).parent/'candidate-manifest.json',result)
    print(json.dumps(dict(state=result['state'],scanned=scanned,counts=dict(counts),seconds=result['seconds'])),flush=True)


if __name__=='__main__':main()
