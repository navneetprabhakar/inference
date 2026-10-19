"""Complete reference shingle join over every eligible consolidated text facet."""
# Creator: Navneet Prabhakar
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from slm.data.facet_near import FacetStore
from slm.data.prose_screen import word_key
from slm.data.stream_hash import sha
from slm.data.facet_near_resume import resume

ROOT=Path('data/global-near-facets-v2');PLAN=Path('configs/global-near-facets-v2.json')

def save(p,v):
    target=Path(p);temp=target.with_suffix('.partial')
    temp.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n');os.replace(temp,target)

def worker():
    plan=json.loads(PLAN.read_text())
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Pinned near input changed')
    source=sqlite3.connect('file:'+str(Path(plan['source_database']).resolve())+'?mode=ro',uri=True)
    store=resume(ROOT/'near.sqlite',max_bytes=plan['max_db_bytes'],max_facets=plan['max_facets'],max_features=plan['max_features'],max_shingles=plan['max_shingles_per_facet'])
    records=considered=excluded=skipped=0;stage='full_feature_index'
    recovered=dict(unique_facets=store.facets,full_feature_occurrences=store.features,source_mappings=store.db.execute('SELECT count(*) FROM facet_sources').fetchone()[0])
    save(ROOT/'recovered-index.json',recovered)
    try:
        for sid,data in source.execute('SELECT sid,data FROM records ORDER BY sid'):
            record=json.loads(data);records+=1
            for facet,text in record['texts'].items():
                key=word_key(text)
                if len(key)<16 or len(key.split())<4:excluded+=1;continue
                existing=store.db.execute('SELECT r.data FROM facet_sources f JOIN records r ON r.sid=f.sid WHERE f.source_sid=? AND f.facet=?',(sid,facet)).fetchone()
                if existing:
                    if existing[0]!=text:raise ValueError('Recovered facet differs from original source')
                    skipped+=1
                else:store.insert_facet(sid,facet,text)
                considered+=1
            if records%1024==0:
                state=dict(stage=stage,records=records,facet_references=considered,unique_facets=store.facets,full_feature_occurrences=store.features,db_bytes=store.usage())
                save(ROOT/'status.json',state);print(json.dumps(state),flush=True)
        store.db.commit()
        if records!=plan['expected_records']:raise ValueError('Full source coverage differs')
        save(ROOT/'feature-index.json',dict(complete=True,records=records,facet_references=considered,excluded_short_facets=excluded,unique_facets=store.facets,full_feature_occurrences=store.features))
        stage='complete_prefix_similarity_join';save(ROOT/'status.json',dict(stage=stage,records=records,unique_facets=store.facets,full_feature_occurrences=store.features))
        print(json.dumps(dict(stage=stage,unique_facets=store.facets,full_feature_occurrences=store.features)),flush=True)
        store.group(plan['max_pair_checks'])
        store.db.execute('UPDATE status SET complete=1');store.db.commit()
        pair_count=store.db.execute('SELECT count(*) FROM near_pairs').fetchone()[0]
        source_pairs=store.db.execute('''SELECT count(*) FROM near_pairs p WHERE EXISTS(
SELECT 1 FROM facet_sources a JOIN facet_sources b ON a.source_sid!=b.source_sid WHERE a.sid=p.a AND b.sid=p.b)''').fetchone()[0]
        result=dict(creator='Navneet Prabhakar',kind='actual-global-near-facets-v2',complete=True,plan_sha256=sha(PLAN),
            records=records,facet_references=considered,excluded_short_facets=excluded,unique_raw_facets=store.facets,recovered_index=recovered,reused_source_facet_references=skipped,
            original_deadline_epoch_seconds=plan['original_deadline_epoch_seconds'],prior_rolled_back_cpu_work_exact_count_known=False,full_feature_occurrences=store.features,
            candidate_pairs_verified=store.pairs,qualifying_facet_pairs=pair_count,cross_record_qualifying_facet_pairs=source_pairs,
            sqlite_peak_bytes=store.peak,sqlite_temp_pages_peak_bytes=store.scratch_peak,
            training_approved=False,component_overlay_applied=False,new_split_assignment=False,model_updates=0,teacher_calls=0,cloud_spend=0,
            scope='Every eligible original facet represented; identical raw facets share an indexed representative with all source mappings retained. Existing complete global-frequency prefix join verifies full5-token punctuation-aware shingle sets at17/20Jaccard. No LSH/sampling/truncation/role prefix/source rewrite or new split. Consume these facet links with exact+containment roots and immutable witness flags before admission.')
        for p,h in plan['input_bindings'].items():
            if sha(p)!=h:raise ValueError('Pinned near input changed during execution')
        store.db.close();source.close();result['database_sha256']=sha(ROOT/'near.sqlite')
        save(ROOT/'report.json',result);save('reports/global-near-facets.json',result);save(ROOT/'status.json',dict(stage='complete',**result));print(json.dumps(result,indent=2),flush=True)
    except BaseException as error:
        store.db.close();source.close();save(ROOT/'failure.json',dict(complete=False,stage=stage,error_type=type(error).__name__,records=records,facet_references=considered,unique_facets=store.facets,features=store.features))
        raise SystemExit('Near grouping stopped; retain incomplete output; no partial grouping acceptance') from None

def main():
    if '--worker' in sys.argv:worker();return
    if ROOT.exists():raise FileExistsError('Near grouping already attempted')
    ROOT.mkdir();(ROOT/'scratch').mkdir();plan=json.loads(PLAN.read_text());save(ROOT/'plan.json',plan)
    if time.time()>=plan['original_deadline_epoch_seconds']:raise ValueError('Original near-job deadline already reached')
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Pinned recovery input changed')
    shutil.copyfile(plan['recovery_database'],ROOT/'near.sqlite')
    if plan['recovery_journal']:shutil.copyfile(plan['recovery_journal'],ROOT/'near.sqlite-journal')
    environment=dict(os.environ,SQLITE_TMPDIR=str((ROOT/'scratch').resolve()))
    child=subprocess.Popen([sys.executable,__file__,'--worker'],start_new_session=True,env=environment)
    started=time.monotonic()
    try:
        while child.poll() is None:
            if time.time()>=plan['original_deadline_epoch_seconds']:raise ValueError('Near process-group wall deadline reached')
            if shutil.disk_usage('.').free<plan['minimum_free_disk_bytes']:raise ValueError('Near free disk reserve reached')
            if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())>plan['max_work_bytes']:raise ValueError('Near retained work cap reached')
            time.sleep(2)
        if child.returncode:raise SystemExit(child.returncode)
    except BaseException as error:
        if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
        save(ROOT/'supervisor-terminal.json',dict(complete=False,error_type=type(error).__name__,child_returncode=child.returncode))
        raise

if __name__=='__main__':main()
