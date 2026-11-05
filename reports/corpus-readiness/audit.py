"""Verify shards and draw an auditable sample without reading any conversation prompts."""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tokenizer import load


def verify(path, salt):
    tokenizer=load()
    manifest=json.loads((path/'manifest.json').read_text())
    with (path/'documents.jsonl').open('rb') as docs:
        assert hashlib.file_digest(docs,'sha256').hexdigest()==manifest['documents_sha256']
    rows=[json.loads(s) for s in (path/'documents.jsonl').read_text().splitlines()]
    for key in ('document_id','normalized_sha256'):
        assert len({r[key] for r in rows})==len(rows)
    groups={s:{(r['source'],r['group']) for r in rows if r['split']==s} for s in ('train','validation')}
    assert groups['train'].isdisjoint(groups['validation'])
    examples=[]
    for key,m in manifest['shards'].items():
        p=path/(key+'.u16')
        with p.open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==m['sha256']
        data=np.memmap(p,mode='r',dtype='<u2')
        assert int(data.max())==50256 and len(data)==m['tokens']
        docs=[r for r in rows if r['source']+'-'+r['split']==key]
        assert len(docs)==m['docs']
        offset=0
        for r in docs:
            assert r['offset']==offset
            offset+=r['tokens']
            assert data[offset-1]==50256 and not np.any(data[r['offset']:offset-1]==50256)
        assert offset==len(data)
        # Fixed salt orders IDs before rendering samples. Training and evaluation each contribute.
        docs.sort(key=lambda r: hashlib.sha256((salt+r['document_id']).encode()).digest())
        for r in docs[:12 if key.startswith('wiki') else 6]:
            s=tokenizer.decode(data[r['offset']:r['offset']+r['tokens']-1].tolist())
            examples.append(dict(key=key,id=r['document_id'],text=s))
    (path/'sample-for-review.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in examples))
    print('All four shard hashes, offsets, EOT boundaries, ID range, document uniqueness and group isolation passed.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('path',type=Path)
    parser.add_argument('--salt',default='audit-20261105-trial-v1')
    args=parser.parse_args()
    verify(args.path,args.salt)
