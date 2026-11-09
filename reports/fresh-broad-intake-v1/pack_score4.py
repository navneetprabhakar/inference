"""Pack complete verified candidate texts, one EOT per document, no admission."""
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
from quality_score_probe import ROOT, DATA, REPORT, sha
sys.path.insert(0,str(ROOT))
from tokenizer import load, document_ids, EOT

SOURCE=ROOT/'data/fresh-broad-score4-dedup-v1'
OUT=ROOT/'data/fresh-broad-packed-v1'


def main():
    start=time.monotonic()
    os.nice(10)
    def check():
        assert time.monotonic()-start<3600 and shutil.disk_usage(ROOT).free>20*1024**3
        assert not any(p.exists() for p in [ROOT/'runs/STOP',SOURCE/'STOP',OUT/'STOP'])
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert rss*(1 if sys.platform=='darwin' else 1024)<3*1024**3
    def deadline(*_):raise TimeoutError('packing deadline')
    signal.signal(signal.SIGALRM,deadline);signal.alarm(3600)
    check();assert not OUT.exists()
    dedup=json.loads((SOURCE/'result.json').read_text())
    assert dedup['state']=='lexical_dedup_complete_not_admitted'
    assert sha(SOURCE/'retained.jsonl')==dedup['retained_sha256']
    selection=json.loads((ROOT/'data/fresh-broad-score4-v1/selection.json').read_text())
    assert sha(DATA/'candidates.sqlite')==selection['candidate_database_sha256']
    bindings=dict(dedup['bindings'])
    bindings.update(selection['bindings'])
    for p in [SOURCE/'result.json',SOURCE/'retained.jsonl',Path(__file__),ROOT/'tokenizer.py']:
        bindings[str(p.relative_to(ROOT))]=sha(p)
    assert all(sha(ROOT/p)==h for p,h in bindings.items())
    tok=load();OUT.mkdir()
    db=sqlite3.connect(f'file:{DATA / "candidates.sqlite"}?mode=ro',uri=True)
    db.execute('pragma cache_size=-65536')
    records=[json.loads(line) for line in (SOURCE/'retained.jsonl').open()]
    records.sort(key=lambda r:(r['split'],r['priority']))
    shards={};seen=set();domains={}
    with (OUT/'documents.jsonl').open('x') as index:
        for split in ['train','validation']:
            offset=count=0
            with (OUT/f'{split}.u16').open('xb') as stream:
                for r in records:
                    if r['split']!=split:continue
                    check()
                    assert r['doc_id'] not in seen;seen.add(r['doc_id'])
                    assert domains.setdefault(r['domain'],split)==split
                    text,doc_id,raw_sha=db.execute('select text,doc_id,raw_sha256 from documents where rowid=?',(r['candidate_rowid'],)).fetchone()
                    assert doc_id==r['doc_id'] and hashlib.sha256(text.encode()).hexdigest()==raw_sha==r['raw_sha256']
                    ids=document_ids(tok,text)
                    assert ids[-1]==EOT and EOT not in ids[:-1] and min(ids)>=0 and max(ids)<=EOT
                    assert tok.decode(ids[:-1])==text
                    raw=np.asarray(ids,dtype='<u2').tobytes();stream.write(raw)
                    record=dict(r,document_id=doc_id,group=r['domain'],source='fresh_broad_score4',
                                offset=offset,tokens=len(ids),file=f'{split}.u16',
                                token_sha256=hashlib.sha256(raw).hexdigest())
                    index.write(json.dumps(record)+'\n');offset+=len(ids);count+=1
                    if count%10000==0:
                        (OUT/'progress.json').write_text(json.dumps(dict(split=split,documents=count,tokens=offset,seconds=time.monotonic()-start)))
            assert count==dedup['counts'][split+'_retained_documents']
            shards[split]=dict(file=f'{split}.u16',tokens=offset,documents=count,sha256=sha(OUT/f'{split}.u16'))
    db.close();check()
    assert all(sha(ROOT/p)==h for p,h in bindings.items())
    result=dict(state='packed_pending_independent_verification',training_admitted=False,
                shards=shards,documents_sha256=sha(OUT/'documents.jsonl'),bindings=bindings,
                candidate_database_sha256=selection['candidate_database_sha256'],
                tokenizer_assets={n:sha(ROOT/'data/tokenizer'/n) for n in ['encoder.json','vocab.bpe']},
                ordering='Lexicographic SHA256 priority within each split; complete documents, no truncation, one EOT.',
                seconds=time.monotonic()-start,
                limitations=dedup['plan']['limitations'],
                pending=['Independent full-span token/provenance verification','Canonical source adapter and explicit admission','Separately bounded training activation'])
    for p in [OUT/'manifest.json',REPORT/'score4-packing.json']:
        p.write_text(json.dumps(result,indent=2)+'\n')
    signal.alarm(0)
    print(json.dumps(dict(state=result['state'],shards=shards,seconds=result['seconds'])),flush=True)


if __name__=='__main__':main()
