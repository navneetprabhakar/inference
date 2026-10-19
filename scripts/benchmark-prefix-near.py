"""Finite actual-source benchmark of complete fixed-order prefix retrieval."""
# Creator: Navneet Prabhakar
from collections import Counter
from itertools import combinations
import json
import os
from pathlib import Path
import random
import resource
import shutil
import signal
import sqlite3
import struct
import subprocess
import sys
import time
from slm.data.curation import shingles
from slm.data.near_audit import verify_near_pairs
from slm.data.prefix_near import PrefixStore,prefix_length
from slm.data.prose_screen import word_key
from slm.data.schema import digest
from slm.data.stream_hash import sha

ROOT=Path('data/prefix-near-benchmark-v1');PLAN=Path('configs/prefix-near-benchmark-v1.json')


def save(path,value):Path(path).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def fields(source,sid):
    row=source.execute('SELECT data FROM records WHERE sid=?',(sid,)).fetchone()
    if row is None:raise ValueError('Selected source record missing')
    for name,text in json.loads(row[0])['texts'].items():
        key=word_key(text)
        if len(key)>=16 and len(key.split())>=4:yield name,text


def worker():
    plan=json.loads(PLAN.read_text());selection=json.loads((ROOT/'selection.json').read_text())
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Frozen benchmark input changed')
    source=sqlite3.connect('file:'+str(Path(plan['source_database']).resolve())+'?mode=ro',uri=True)
    started=time.monotonic();counts=Counter();ordering_occurrences=ordering_facets=0
    for sid in selection['ordering_sids']:
        for name,text in fields(source,sid):
            values=shingles(text);ordering_occurrences+=len(values);ordering_facets+=1
            if ordering_occurrences>plan['maximum_ordering_feature_occurrences']:raise ValueError('Finite ordering-statistic cap reached')
            counts.update(bytes.fromhex(digest(v)) for v in values)
    with (ROOT/'ordering-counts.bin').open('xb') as out:
        for key in sorted(counts):out.write(key+struct.pack('<I',counts[key]))
    ordering_seconds=time.monotonic()-started
    store=PrefixStore(ROOT/'index',counts,max_facets=20000,max_features=10000000,max_shingles=1000000,
                      max_pairs=1000000,max_db_bytes=1024**3,cache_kib=262144)
    index_started=time.monotonic();references=0
    for i,sid in enumerate(selection['benchmark_sids'],1):
        for name,text in fields(source,sid):store.insert_facet(sid,name,text);references+=1
        if i%512==0:print(json.dumps(dict(source_records=i,unique_facets=store.facets,full_features=store.features,prefix_postings=store.postings,candidate_pairs=store.pairs)),flush=True)
    store.commit();index_seconds=time.monotonic()-index_started
    # Every selected source/facet mapping is checked against immutable originals.
    for sid in selection['benchmark_sids']:
        actual=dict(store.db.execute('SELECT f.facet,r.data FROM facet_sources f JOIN records r ON r.sid=f.sid WHERE f.source_sid=?',(sid,)))
        if actual!=dict(fields(source,sid)):raise ValueError('Actual source coverage differs')
    audit_started=time.monotonic();full_count=prefix_count=0
    for sid,text,n,offset,k in store.db.execute('SELECT sid,data,n,offset,prefix_length FROM records ORDER BY sid'):
        hashes=sorted({bytes.fromhex(digest(v)) for v in shingles(text)})
        store.file.seek(offset)
        if n!=len(hashes) or store.file.read(n*32)!=b''.join(hashes):raise ValueError('Full reference-shingle stream differs')
        expected=sorted(hashes,key=lambda h:(counts.get(h,0),h))[:prefix_length(n)]
        actual={r[0] for r in store.db.execute('SELECT feat FROM prefixes WHERE sid=?',(sid,))}
        if len(expected)!=k or set(expected)!=actual:raise ValueError('Complete fixed-order prefix differs')
        full_count+=n;prefix_count+=k
    pairs=verify_near_pairs(store.db)
    sample=store.db.execute('SELECT sid,data FROM records ORDER BY exact LIMIT 128').fetchall()
    values={sid:shingles(text) for sid,text in sample};gold=set()
    for a,b in combinations(values,2):
        x,y=values[a],values[b]
        if 20*len(x&y)>=17*len(x|y):gold.add(tuple(sorted((a,b))))
    selected=set(values)
    actual={tuple(p) for p in store.db.execute('SELECT a,b FROM near_pairs') if p[0] in selected and p[1] in selected}
    if gold!=actual:raise ValueError('Actual128-facet brute-force result differs')
    audit_seconds=time.monotonic()-audit_started
    result=dict(creator='Navneet Prabhakar',kind='actual-prefix-only-near-benchmark-v1',complete=True,
        plan_sha256=sha(PLAN),selected_source_records=len(selection['benchmark_sids']),source_facet_references=references,
        ordering_sample_source_records=len(selection['ordering_sids']),ordering_sample_facets=ordering_facets,
        ordering_feature_occurrences=ordering_occurrences,ordering_distinct_features=len(counts),
        unique_facets=store.facets,complete_features=full_count,indexed_prefix_postings=prefix_count,
        candidate_pairs=store.pairs,qualifying_facet_pairs=pairs,ordering_seconds=ordering_seconds,index_seconds=index_seconds,
        audit_seconds=audit_seconds,brute_force_actual_facets=len(sample),brute_force_actual_qualifying_pairs=len(gold),
        reference_full_sets_and_prefixes_checked=True,selected_source_coverage_checked=True,
        sqlite_bytes=(ROOT/'index/near.sqlite').stat().st_size,full_feature_bytes=(ROOT/'index/full-shingles.bin').stat().st_size,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),
        full_corpus_grouping=False,training_approved=False,model_updates=0,teacher_calls=0,paid_resources_created=0,
        scope='512sampled source records only define one fixed global shingle order; full reference sets from every selected benchmark facet participate. Prefix retrieval and exact17/20raw-set verification are complete for this selected population. Not a full235779-record corpus result or guaranteed full-run performance.')
    store.close();source.close()
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Original benchmark input changed')
    save(ROOT/'report.json',result);save('reports/prefix-near-benchmark.json',result);print(json.dumps(result,indent=2),flush=True)


def main():
    if '--worker' in sys.argv:worker();return
    if ROOT.exists():raise FileExistsError('Retain prior benchmark')
    plan=json.loads(PLAN.read_text());ROOT.mkdir()
    rng=random.Random(plan['selection_seed'])
    selection=dict(ordering_sids=sorted(rng.sample(range(plan['source_records']),512)),
                   benchmark_sids=sorted(rng.sample(range(plan['source_records']),4096)))
    save(ROOT/'selection.json',selection);save(ROOT/'plan.json',plan)
    shutil.copyfile(__file__,ROOT/'executed-benchmark.py');shutil.copyfile('src/slm/data/prefix_near.py',ROOT/'executed-prefix-near.py')
    child=subprocess.Popen([sys.executable,__file__,'--worker'],start_new_session=True)
    started=time.monotonic()
    try:
        while child.poll() is None:
            if time.monotonic()-started>plan['wall_seconds']:raise TimeoutError('Benchmark wall cap')
            if shutil.disk_usage(ROOT).free<plan['minimum_free_disk_bytes']:raise ValueError('Free-disk reserve')
            size=0
            for p in ROOT.rglob('*'):
                try:
                    if p.is_file():size+=p.stat().st_size
                except FileNotFoundError:pass
            if size>plan['max_work_bytes']:raise ValueError('Benchmark retained-work cap')
            time.sleep(1)
        if child.returncode:raise RuntimeError('Benchmark worker failed; retain partial artifacts')
    except BaseException as error:
        if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
        save(ROOT/'supervisor-terminal.json',dict(complete=False,error_type=type(error).__name__,child_returncode=child.returncode));raise


if __name__=='__main__':main()
