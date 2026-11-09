"""Independent full packed-span replay against selected source text and metadata."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import sqlite3
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tokenizer import load,EOT

OUT=ROOT/'data/fresh-broad-packed-v1'
SOURCE=ROOT/'data/fresh-broad-score4-dedup-v1'


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    start=time.monotonic();os.nice(10)
    def check():
        assert time.monotonic()-start<3600 and shutil.disk_usage(ROOT).free>20*1024**3
        assert not any(p.exists() for p in [ROOT/'runs/STOP',OUT/'STOP'])
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert rss*(1 if sys.platform=='darwin' else 1024)<3*1024**3
    def deadline(*_):raise TimeoutError('verification deadline')
    signal.signal(signal.SIGALRM,deadline);signal.alarm(3600)
    check();assert not (OUT/'independent-verification.json').exists()
    manifest=json.loads((OUT/'manifest.json').read_text());manifest_hash=digest(OUT/'manifest.json')
    assert manifest['state']=='packed_pending_independent_verification'
    assert digest(OUT/'documents.jsonl')==manifest['documents_sha256']
    for rel,value in manifest['bindings'].items():assert digest(ROOT/rel)==value
    db_path=ROOT/'data/fresh-broad-candidates-v1/candidates.sqlite'
    assert digest(db_path)==manifest['candidate_database_sha256']
    retained=[json.loads(line) for line in (SOURCE/'retained.jsonl').open()]
    expected={r['doc_id']:r for r in retained};assert len(expected)==len(retained)
    custody=json.loads((ROOT/'data/fresh-broad-candidates-v1/custody.json').read_text())
    excluded=set(custody['excluded_domain_families']);denied=set(custody['excluded_doc_ids'])
    for name in ['quality-review.json','quality-score-review.json']:
        excluded.update(json.loads((Path(__file__).parent/name).read_text())['excluded_domains'])
    excluded.update(json.loads((SOURCE/'result.json').read_text())['excluded_domain_families'])
    db=sqlite3.connect(f'file:{db_path}?mode=ro',uri=True);db.row_factory=sqlite3.Row
    db.execute('pragma cache_size=-65536')
    tok=load();counts=Counter();seen=set();domains={};last={};streams={}
    for split,info in manifest['shards'].items():
        path=OUT/info['file'];assert digest(path)==info['sha256'] and path.stat().st_size==2*info['tokens']
        streams[split]=np.memmap(path,dtype='<u2',mode='r')
    for n,line in enumerate((OUT/'documents.jsonl').open()):
        if n%128==0:check()
        r=json.loads(line);identifier=r['document_id'];split=r['split']
        assert identifier not in seen and identifier not in denied and r['domain'] not in excluded
        seen.add(identifier);original=expected[identifier]
        assert all(r[k]==value for k,value in original.items())
        assert domains.setdefault(r['domain'],split)==split
        assert r['priority']>last.get(split,'');last[split]=r['priority']
        assert r['offset']==counts[split+'_tokens'] and r['file']==manifest['shards'][split]['file']
        source=dict(db.execute('select * from documents where rowid=?',(r['candidate_rowid'],)).fetchone())
        assert all(r[k]==value for k,value in source.items() if k!='text')
        text=source['text'];assert hashlib.sha256(text.encode()).hexdigest()==r['raw_sha256']
        span=streams[split][r['offset']:r['offset']+r['tokens']]
        assert len(span)==r['tokens'] and hashlib.sha256(span.tobytes()).hexdigest()==r['token_sha256']
        ids=span.tolist();assert ids[-1]==EOT and EOT not in ids[:-1]
        assert tok.decode(ids[:-1])==text
        assert ids[:-1]==tok.encode(text).ids
        counts[split+'_tokens']+=len(ids);counts[split+'_documents']+=1
    db.close();assert seen==set(expected)
    for split,info in manifest['shards'].items():
        assert counts[split+'_tokens']==info['tokens'] and counts[split+'_documents']==info['documents']
    check();assert digest(OUT/'manifest.json')==manifest_hash
    result=dict(state='PASS_full_packed_span_replay_not_admitted',training_admitted=False,
                manifest_sha256=manifest_hash,documents_sha256=manifest['documents_sha256'],counts=dict(counts),
                checked_documents=len(seen),verifier_sha256=digest(Path(__file__)),seconds=time.monotonic()-start,
                scope='Every packed span retokenized and decoded against immutable candidate text; full retained-set equality, source metadata, contiguous offsets, ordering, token hashes, domain exclusions and split disjointness verified.',
                limitations='Uses the same pinned tokenizer implementation; raw-source verification and approximate custody/dedup are separate bound receipts. Not semantic quality certification or training authorization.')
    for p in [OUT/'independent-verification.json',Path(__file__).parent/'score4-packing-verification.json']:
        p.write_text(json.dumps(result,indent=2)+'\n')
    signal.alarm(0);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
