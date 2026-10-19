"""Separate finite read-only audit of the retained selected-population index."""
# Creator: Navneet Prabhakar
from itertools import combinations
from collections import Counter
import json
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
from slm.data.prefix_near import prefix_length
from slm.data.prose_screen import word_key
from slm.data.schema import digest
from slm.data.stream_hash import sha

OLD=Path('data/prefix-near-benchmark-v1');OUT=Path('data/prefix-near-readonly-audit-v1')


def save(p,v):Path(p).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')


def worker():
    plan=json.loads((OLD/'plan.json').read_text());selection=json.loads((OLD/'selection.json').read_text())
    terminal=json.loads((OLD/'supervisor-terminal.json').read_text())
    if terminal!=dict(complete=False,error_type='KeyboardInterrupt',child_returncode=-9):raise ValueError('Observed sealed original attempt required')
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Original benchmark source changed')
    rng=random.Random(plan['selection_seed'])
    if selection!=dict(ordering_sids=sorted(rng.sample(range(plan['source_records']),512)),benchmark_sids=sorted(rng.sample(range(plan['source_records']),4096))):raise ValueError('Frozen source selection differs')
    db=sqlite3.connect('file:'+str((OLD/'index/near.sqlite').resolve())+'?mode=ro',uri=True)
    source=sqlite3.connect('file:'+str(Path(plan['source_database']).resolve())+'?mode=ro',uri=True)
    db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-131072');db.execute('PRAGMA temp_store=MEMORY')
    roots=[OLD/'index/near.sqlite',OLD/'index/full-shingles.bin',OLD/'ordering-counts.bin']
    before={str(p):sha(p) for p in roots};started=time.monotonic()
    def fields(sid):
        row=json.loads(source.execute('SELECT data FROM records WHERE sid=?',(sid,)).fetchone()[0])
        return {k:t for k,t in row['texts'].items() if len(word_key(t))>=16 and len(word_key(t).split())>=4}
    expected_counts=Counter();ordering_occurrences=0
    for sid in selection['ordering_sids']:
        for text in fields(sid).values():
            values=shingles(text);ordering_occurrences+=len(values)
            expected_counts.update(bytes.fromhex(digest(v)) for v in values)
    counts={}
    with (OLD/'ordering-counts.bin').open('rb') as f:
        while record:=f.read(36):
            if len(record)!=36:raise ValueError('Incomplete fixed-order count stream')
            h=record[:32]
            if h in counts:raise ValueError('Duplicate fixed-order key')
            counts[h]=struct.unpack('<I',record[32:])[0]
    if counts!=dict(expected_counts):raise ValueError('Ordering sample statistics differ')
    references=0
    for sid in selection['benchmark_sids']:
        expected=fields(sid);actual=dict(db.execute('SELECT f.facet,r.data FROM facet_sources f JOIN records r ON r.sid=f.sid WHERE f.source_sid=?',(sid,)))
        if expected!=actual:raise ValueError('Complete selected source mapping differs')
        references+=len(expected)
    if db.execute('SELECT count(*) FROM facet_sources').fetchone()[0]!=references:raise ValueError('Unexpected source mapping')
    # One sequential sorted prefix stream, not one full-index scan per facet.
    prefix_rows=iter(db.execute('SELECT sid,feat FROM prefixes ORDER BY sid,feat'))
    pending=next(prefix_rows,None);values={};nvalues={};features=prefixes=offset_expected=0
    with (OLD/'index/full-shingles.bin').open('rb') as full:
        for sid,text,fingerprint,n,offset,k in db.execute('SELECT sid,data,exact,n,offset,prefix_length FROM records ORDER BY sid'):
            if digest(text)!=fingerprint or offset!=offset_expected:raise ValueError('Raw identity or contiguous full stream differs')
            raw=shingles(text);hashes=sorted(bytes.fromhex(digest(v)) for v in raw)
            if n!=len(hashes) or full.read(n*32)!=b''.join(hashes):raise ValueError('Complete full-reference features differ')
            expected=set(sorted(hashes,key=lambda h:(counts.get(h,0),h))[:prefix_length(n)]);actual=set()
            while pending is not None and pending[0]==sid:
                actual.add(pending[1]);pending=next(prefix_rows,None)
            if actual!=expected or len(actual)!=k:raise ValueError('Complete fixed-order prefix differs')
            values[sid]=raw;nvalues[sid]=n;features+=n;prefixes+=k;offset_expected+=n*32
        if full.read(1) or pending is not None:raise ValueError('Unexpected feature or prefix tail')
    candidates=db.execute('''SELECT DISTINCT p.sid,q.sid FROM prefixes p JOIN prefixes q ON p.feat=q.feat AND p.sid<q.sid
JOIN records a ON a.sid=p.sid JOIN records b ON b.sid=q.sid WHERE 20*a.n>=17*b.n AND 17*a.n<=20*b.n ORDER BY p.sid,q.sid''')
    qualifying=set();candidate_count=0
    for a,b in candidates:
        candidate_count+=1;x,y=values[a],values[b]
        if 20*len(x&y)>=17*len(x|y):qualifying.add((a,b))
    actual=set(db.execute('SELECT a,b FROM near_pairs'))
    if actual!=qualifying:raise ValueError('Full replayed candidate verification differs')
    chosen=set()
    for a,b in sorted(actual)[:20]:chosen.update((a,b))
    for sid, in db.execute('SELECT sid FROM records ORDER BY exact'):
        if len(chosen)>=128:break
        chosen.add(sid)
    brute=set()
    for a,b in combinations(sorted(chosen),2):
        x,y=values[a],values[b]
        if 20*len(x&y)>=17*len(x|y):brute.add((a,b))
    if brute!={p for p in actual if p[0] in chosen and p[1] in chosen}:raise ValueError('Actual128-facet all-pair recall differs')
    for p,h in before.items():
        if sha(p)!=h:raise ValueError('Original index changed during read-only audit')
    result=dict(creator='Navneet Prabhakar',kind='actual-prefix-near-readonly-benchmark-audit-v1',complete=True,
        original_benchmark_complete=False,original_benchmark_terminal=terminal,original_report_absent=not (OLD/'report.json').exists(),
        selected_population_complete=True,source_records=4096,source_facet_references=references,unique_facets=len(values),
        ordering_sample_source_records=512,ordering_feature_occurrences=ordering_occurrences,ordering_unique_features=len(counts),
        full_features=features,prefix_postings=prefixes,candidate_pairs_replayed=candidate_count,qualifying_near_pairs=len(actual),
        brute_force_actual_facets=len(chosen),brute_force_qualifying_pairs=len(brute),raw_inputs_unchanged=True,
        index_files_sha256=before,sqlite_bytes=(OLD/'index/near.sqlite').stat().st_size,full_feature_bytes=(OLD/'index/full-shingles.bin').stat().st_size,
        audit_seconds=time.monotonic()-started,original_index_phase_seconds_measured=False,
        original_index_completion_observed_wall_upper_bound_seconds=(OLD/'supervisor-terminal.json').stat().st_mtime-(OLD/'selection.json').stat().st_mtime,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),
        auditor_sha256=sha(__file__),original_plan_sha256=sha('configs/prefix-near-benchmark-v1.json'),
        full_corpus_grouping=False,training_approved=False,model_updates=0,teacher_calls=0,
        scope='Separate bounded read-only verification of retained fully indexed4096-source benchmark. Original attempt remains interrupted because its per-facet prefix audit query rescanned the index. No old deadline/reset/reindex or exact build-throughput claim. Sampled frequencies choose one global order only; all full facets/prefixes/candidate raw Jaccards are checked for this selected population, not the full corpus.')
    db.close();source.close();save(OUT/'report.json',result);save('reports/prefix-near-benchmark-audit.json',result)
    print(json.dumps(result,indent=2),flush=True)


def main():
    if '--worker' in sys.argv:worker();return
    if OUT.exists():raise FileExistsError('Preserve audit attempt')
    OUT.mkdir();shutil.copyfile(__file__,OUT/'executed-auditor.py')
    child=subprocess.Popen([sys.executable,__file__,'--worker'],start_new_session=True)
    started=time.monotonic()
    try:
        while child.poll() is None:
            if time.monotonic()-started>90:raise TimeoutError('Read-only audit90second cap')
            time.sleep(1)
        if child.returncode:raise RuntimeError('Audit failed; retain original index')
    except BaseException as error:
        if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
        save(OUT/'supervisor-terminal.json',dict(complete=False,error_type=type(error).__name__,child_returncode=child.returncode));raise


if __name__=='__main__':
    import os
    main()
