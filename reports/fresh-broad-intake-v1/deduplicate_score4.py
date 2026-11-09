"""Conservative lexical deduplication, historical validation first; no training."""
from collections import Counter, defaultdict
import hashlib
import heapq
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import sqlite3
import sys
import time
import unicodedata

import numpy as np
from quality_score_probe import ROOT, DATA, REPORT, sha
sys.path.insert(0, str(ROOT))
from tokenizer import load, EOT

SOURCE = ROOT/'data/fresh-broad-score4-v1'
OUT = ROOT/'data/fresh-broad-score4-dedup-v1'
WORD = re.compile(r'\w+', re.UNICODE)


def signature(text):
    norm = ' '.join(unicodedata.normalize('NFKC', text).casefold().split())
    words = WORD.findall(norm)
    grams = {int.from_bytes(hashlib.blake2b(' '.join(words[i:i+5]).encode(), digest_size=8).digest(), 'big')
             for i in range(len(words)-4)}
    return hashlib.sha256(norm.encode()).hexdigest(), heapq.nsmallest(16, grams)


def main():
    start = time.monotonic()
    os.nice(10)
    def check():
        assert time.monotonic()-start < 3600
        assert shutil.disk_usage(ROOT).free > 20*1024**3
        assert not any(p.exists() for p in [ROOT/'runs/STOP', SOURCE/'STOP', OUT/'STOP'])
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert rss*(1 if sys.platform=='darwin' else 1024) < 4*1024**3
    def deadline(*_):
        raise TimeoutError('deduplication deadline')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(3600)
    check()
    assert not OUT.exists()
    selection = json.loads((SOURCE/'selection.json').read_text())
    assert sha(SOURCE/'selected.jsonl') == selection['selected_sha256']
    assert sha(DATA/'candidates.sqlite') == selection['candidate_database_sha256']
    OUT.mkdir()
    pins = {str(p.relative_to(ROOT)):sha(p) for p in [SOURCE/'selection.json', SOURCE/'selected.jsonl', Path(__file__), REPORT/'quality_score_probe.py', ROOT/'tokenizer.py']}
    plan = dict(method='NFKC/casefold/whitespace normalized exact SHA256, or >=8 shared entries in bottom16 unique BLAKE2b-64 five-word shingles.',
                order='All historical validation indexed first, then selected validation by priority, then selected train by priority.',
                heldout_policy='Any selected train match to historical or selected validation excludes its entire domain family; within-train duplicate excludes document only.',
                limitations=['Approximate lexical matching can miss paraphrases, containment and some near duplicates.', 'Signature overlap is a conservative exclusion heuristic, not an exact Jaccard threshold; false positives are possible.', 'Public/private conversation custody remains covered by the separately pinned full-text screening, not re-scored here.', 'Historical TRAIN near duplicates are not screened here beyond the prior exact text/URL exclusions.'],
                training_admitted=False)
    (OUT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    inverted = defaultdict(list)
    exact = {}
    held = []
    counts = Counter()
    def add(text, is_held):
        key, sig = signature(text)
        index = len(held)
        held.append(is_held)
        exact.setdefault(key,index)
        for code in sig:
            inverted[code].append(index)
    def matches(text):
        key, sig = signature(text)
        found = set()
        if key in exact:
            found.add(exact[key])
        candidates = Counter(i for code in sig for i in inverted.get(code,()))
        found.update(i for i,n in candidates.items() if n>=8)
        return found, key, sig
    tok = load()
    names = ['feasibility-v1','extended-trial-v1','extended-trial-v2','extended-trial-v3','balanced-continuation-v1','base-foundation-100m','narrative-packed-v1','explanatory-packed-v3']
    seen_spans = set()
    for name in names:
        folder = ROOT/'data'/name
        metadata = folder/('validation.documents.jsonl' if name in names[-2:] else 'documents.jsonl')
        assert metadata.exists()
        pins[str(metadata.relative_to(ROOT))] = sha(metadata)
        streams = {}
        for line in metadata.open():
            r = json.loads(line)
            if r['split'] != 'validation':
                continue
            check()
            source = 'narrative' if name=='narrative-packed-v1' else r['source']
            path = folder/f'{source}-validation.u16'
            if path not in streams:
                pins[str(path.relative_to(ROOT))] = sha(path)
                streams[path] = np.memmap(path, dtype='<u2', mode='r')
            key = (pins[str(path.relative_to(ROOT))], r['offset'], r['tokens'])
            if key in seen_spans:
                counts['repeated_historical_span_skipped'] += 1
                continue
            seen_spans.add(key)
            ids = streams[path][r['offset']:r['offset']+r['tokens']].tolist()
            assert len(ids)==r['tokens'] and ids[-1]==EOT and EOT not in ids[:-1]
            add(tok.decode(ids[:-1]), True)
            counts['historical_validation_documents'] += 1
        del streams
    records = [json.loads(line) for line in (SOURCE/'selected.jsonl').open()]
    records.sort(key=lambda r:(r['split']!='validation',r['priority']))
    db = sqlite3.connect(f'file:{DATA / "candidates.sqlite"}?mode=ro',uri=True)
    db.execute('pragma cache_size=-65536')
    denied_domains = set()
    provisional = []
    with (OUT/'decisions.jsonl').open('x') as decisions:
        for n,r in enumerate(records):
            if n%128==0:
                check()
            text, raw_sha = db.execute('select text,raw_sha256 from documents where rowid=?',(r['candidate_rowid'],)).fetchone()
            assert raw_sha==r['raw_sha256']==hashlib.sha256(text.encode()).hexdigest()
            found,key,sig = matches(text)
            held_match = any(held[i] for i in found)
            reason = None
            if found:
                reason = 'heldout_overlap' if held_match else 'within_train_duplicate'
                if r['split']=='train' and held_match:
                    denied_domains.add(r['domain'])
                counts[r['split']+'_'+reason] += 1
            else:
                provisional.append(r)
            # Index all selected validation, including duplicate ones, to retain
            # the full held-out lexical surface for subsequent train screening.
            if not found or r['split']=='validation':
                index = len(held)
                held.append(r['split']=='validation')
                exact.setdefault(key,index)
                for code in sig:
                    inverted[code].append(index)
            decisions.write(json.dumps(dict(doc_id=r['doc_id'],split=r['split'],reason=reason))+'\n')
            if (n+1)%10000==0:
                (OUT/'progress.json').write_text(json.dumps(dict(reviewed=n+1,seconds=time.monotonic()-start)))
    db.close()
    with (OUT/'retained.jsonl').open('x') as output:
        for r in provisional:
            if r['domain'] in denied_domains:
                counts['additional_domain_excluded_documents'] += 1
                continue
            output.write(json.dumps(r)+'\n')
            counts[r['split']+'_retained_documents'] += 1
            counts[r['split']+'_retained_publisher_tokens'] += r['publisher_tokens']
    check()
    assert all(sha(ROOT/p)==value for p,value in pins.items())
    result = dict(state='lexical_dedup_complete_not_admitted',training_admitted=False,
                  selected_documents=len(records),counts=dict(counts),plan=plan,
                  excluded_domain_families=sorted(denied_domains), bindings=pins,
                  retained_sha256=sha(OUT/'retained.jsonl'),decisions_sha256=sha(OUT/'decisions.jsonl'),
                  seconds=time.monotonic()-start)
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    summary = {k:v for k,v in result.items() if k!='excluded_domain_families'}
    summary['excluded_domain_count'] = len(denied_domains)
    summary['result_sha256'] = sha(OUT/'result.json')
    (REPORT/'score4-deduplication.json').write_text(json.dumps(summary,indent=2)+'\n')
    signal.alarm(0)
    print(json.dumps(dict(state=result['state'],counts=dict(counts),seconds=result['seconds'])),flush=True)


if __name__=='__main__':
    main()
