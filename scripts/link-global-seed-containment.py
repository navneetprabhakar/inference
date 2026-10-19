"""Exhaustive normalized seed containment over consolidated source facets."""
# Creator: Navneet Prabhakar
from collections import Counter
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
from slm.data.seed_containment import PrefixIndex,normalized_bytes
from slm.data.tokenized import sha

ROOT=Path('data/global-seed-containment-v1');PLAN=Path('configs/global-seed-containment-v1.json')

def save(p,v):Path(p).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')

def worker():
    plan=json.loads(PLAN.read_text())
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Pinned seed-link input changed')
    source=sqlite3.connect('file:'+str(Path(plan['source_database']).resolve())+'?mode=ro',uri=True)
    output=sqlite3.connect(ROOT/'links.sqlite')
    output.executescript('''PRAGMA synchronous=FULL; PRAGMA journal_mode=DELETE;
CREATE TABLE patterns(key TEXT PRIMARY KEY,sid INTEGER,root INTEGER,normalized_sha256 TEXT,bytes INTEGER);
CREATE TABLE links(pattern TEXT,seed_sid INTEGER,target_sid INTEGER,facet TEXT,start INTEGER,end INTEGER,PRIMARY KEY(pattern,target_sid,facet,start)) WITHOUT ROWID;
CREATE TABLE status(complete INTEGER);INSERT INTO status VALUES(0);''')
    output.execute('PRAGMA max_page_count='+str(plan['max_db_bytes']//4096))
    counts=Counter();ingredients=Counter()
    try:
        owners={};patterns={}
        for sid,data,root in source.execute('SELECT sid,data,root FROM records ORDER BY sid'):
            r=json.loads(data)
            if 'seed' not in r['texts']:continue
            raw=normalized_bytes(r['texts']['seed']);key=hashlib.sha256(raw).hexdigest();counts['seed_facets']+=1
            if not plan['anchor_width']<=len(raw)<=plan['max_facet_bytes']:raise ValueError('Seed length outside declared index scope')
            if key in owners:
                if owners[key][1]!=root or patterns[key]!=raw:raise ValueError('Equal normalized seed must share prior exact root')
            else:patterns[key]=raw;owners[key]=(sid,root)
        index=PrefixIndex(patterns,width=plan['anchor_width'],max_bytes=plan['max_facet_bytes'])
        output.executemany('INSERT INTO patterns VALUES(?,?,?,?,?)',((key,*owners[key],key,len(raw)) for key,raw in sorted(patterns.items())))
        output.commit()
        for sid,data,root in source.execute('SELECT sid,data,root FROM records ORDER BY sid'):
            r=json.loads(data);counts['target_records']+=1
            for facet,text in r['texts'].items():
                raw=normalized_bytes(text);counts['target_facets']+=1;counts['normalized_target_bytes']+=len(raw)
                if len(raw)>plan['max_facet_bytes']:raise ValueError('Target facet outside complete scope; no truncation')
                for key,start,full in index.candidates(raw):
                    counts['candidate_anchor_hits']+=1
                    if counts['candidate_anchor_hits']>plan['max_anchor_hits']:raise ValueError('Complete candidate budget exhausted')
                    if not full:continue
                    counts['verified_full_occurrences']+=1
                    seed_sid,seed_root=owners[key]
                    if seed_root==root:counts['existing_exact_component_occurrences']+=1;continue
                    output.execute('INSERT INTO links VALUES(?,?,?,?,?,?)',(key,seed_sid,sid,facet,start,start+len(patterns[key])))
                    counts['new_cross_component_occurrences']+=1;ingredients[r['ingredient']]+=1
            if sid%1000==0:
                output.commit()
                if shutil.disk_usage('.').free<plan['minimum_free_disk_bytes']:raise ValueError('Free disk reserve reached')
                print(json.dumps(dict(target_records=counts['target_records'],verified=counts['verified_full_occurrences'],new_links=counts['new_cross_component_occurrences'])),flush=True)
        for p,h in plan['input_bindings'].items():
            if sha(p)!=h:raise ValueError('Pinned seed-link input changed during scan')
        assert counts['target_records']==source.execute('SELECT count(*) FROM records').fetchone()[0]
        output.execute('UPDATE status SET complete=1');output.commit();output.close();source.close()
        result=dict(creator='Navneet Prabhakar',kind='actual-global-seed-containment-v1',complete=True,
            plan_sha256=sha(PLAN),source_database_sha256=plan['input_bindings'][plan['source_database']],
            output_database_sha256=sha(ROOT/'links.sqlite'),distinct_normalized_seed_patterns=len(patterns),counts=dict(counts),target_ingredient_links=dict(ingredients),
            numpy_version=version('numpy'),training_approved=False,split_assignment_performed=False,near_grouping_complete=False,
            model_updates=0,teacher_calls=0,cloud_spend=0,
            scope='Every normalized byte offset of every consolidated text facet is indexed for all captured complete seed patterns, and every full match is byte-verified. New cross-exact-component occurrences retained; existing component matches counted. Normalized offsets are not original-source byte offsets. This verifies quoted-text containment, not unique source document identity, different latent excerpts, semantics, near grouping or admission.')
        save(ROOT/'report.json',result);save('reports/global-seed-containment.json',result);print(json.dumps(result,indent=2),flush=True)
    except BaseException as error:
        try:output.close();source.close()
        except Exception:pass
        save(ROOT/'failure.json',dict(complete=False,error_type=type(error).__name__,counts=dict(counts)))
        raise SystemExit('Global seed scan stopped; preserve outputs, no partial acceptance') from None

def main():
    if '--worker' in sys.argv:worker();return
    if ROOT.exists():raise FileExistsError('Seed scan already attempted')
    ROOT.mkdir();save(ROOT/'plan.json',json.loads(PLAN.read_text()))
    child=subprocess.Popen([sys.executable,__file__,'--worker'],start_new_session=True)
    try:
        code=child.wait(timeout=1800)
        if code:raise SystemExit(code)
    except BaseException:
        if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
        raise

if __name__=='__main__':main()
