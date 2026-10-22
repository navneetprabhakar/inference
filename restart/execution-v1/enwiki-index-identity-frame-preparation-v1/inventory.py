"""Once-only offline index identity inventory; no XML/network/IntakeLedger path."""
import argparse
import bz2
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import pathlib
import io
import heapq
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import inventory_core as core

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE/'m2-intake'
OUT = ROOT/'enwiki-complete-index-identity-frame-v1'
SOURCE = ROOT/'enwiki-native-index-20260801-v1/enwiki-20260801-pages-articles-multistream-index.txt.bz2'
ASSESSOR = BASE/'enwiki-native-index-assessment-preparation-v1/core.py'
RSS_HELPER = BASE/'wikibooks-current20-native-source-capture-preparation-v2/supervisor_core.py'
WORK = 1200
EXTERNAL = 1260
OUTPUT = 4000000000
COMBINED = 64000000000
FREE = 53474836480
RSS = 1000000000
SLOTS = {'result.json':65536,'supervisor.json':65536,'progress.json':16384}


def clock():
    return time.clock_gettime(time.CLOCK_MONOTONIC)


def stat(p):
    s=Path(p).stat()
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    return m


def runtime():
    import _bz2,_sqlite3,_hashlib
    return {'Python':sys.version,'launcher':sys.executable,'binary':str(Path(sys.executable).resolve()),
            'platform':platform.platform(),'SQLite':sqlite3.sqlite_version,
            'origins':{m.__name__:m.__spec__.origin for m in [_bz2,_sqlite3,_hashlib]}}


def inventory():
    paths=[HERE/n for n in ['inventory.py','inventory_core.py','checks.py','profile.json','runtime.json','projection.py','capacity-projection.json']]
    paths += [ASSESSOR,RSS_HELPER,BASE/'disk-budget.json',BASE/'source-acquisition-authorization.json',
              BASE/'enwiki-native-index-assessment-preparation-v1/profile.json',
              ROOT/'enwiki-native-index-assessment-v1/result.json',
              ROOT/'enwiki-native-index-assessment-v1/supervisor.json',
              ROOT/'enwiki-native-index-20260801-v1/worker-result.json',
              ROOT/'enwiki-native-index-20260801-v1/supervisor-result.json',
              ROOT/'enwiki-index-parent-terminal-verification-v1/verification.json']
    for m in [argparse,bz2,hashlib,json,os,platform,shutil,signal,sqlite3,sqlite3.dbapi2,subprocess,time,pathlib,io,heapq]:
        if getattr(m,'__file__',None):paths.append(Path(m.__file__))
    paths += [Path(sys.executable).resolve()]
    return {str(p.resolve()) for p in paths}


def verify(a):
    if sha(HERE/'code-pins.json')!=a.code_pins_sha256 or sha(HERE/'profile.json')!=a.profile_sha256:
        raise ValueError('external_manifest_profile_digest')
    pins=json.loads((HERE/'code-pins.json').read_text())['SHA256']
    p=json.loads((HERE/'profile.json').read_text())
    if set(pins)!=inventory() or p['output']!=str(OUT) or p['source']['path']!=str(SOURCE):
        raise ValueError('exact_inventory_and_paths')
    if p['limits']!={'worker_seconds':WORK,'external_seconds':EXTERNAL,'tree_RSS_bytes':RSS,
                     'output_bytes':OUTPUT,'DB_bytes':core.DB_BYTES,'combined_intake_bytes':COMBINED,
                     'protected_free_bytes':FREE,'commit_rows':core.BATCH}:
        raise ValueError('exact_limits')
    for name,h in pins.items():
        q=Path(name)
        if q.is_symlink() or not q.is_file() or sha(q)!=h:
            raise ValueError('input_pin_changed:'+name)
    if SOURCE.is_symlink() or stat(SOURCE)!=p['source']['stat'] or runtime()!=json.loads((HERE/'runtime.json').read_text()):
        raise ValueError('source_stat_or_runtime_changed')
    r=json.loads((ROOT/'enwiki-native-index-assessment-v1/result.json').read_text())
    w=json.loads((ROOT/'enwiki-native-index-20260801-v1/worker-result.json').read_text())
    s=json.loads((ROOT/'enwiki-native-index-20260801-v1/supervisor-result.json').read_text())
    expected=p['source']
    pv=json.loads((ROOT/'enwiki-index-parent-terminal-verification-v1/verification.json').read_text())
    prior_supervisor=json.loads((ROOT/'enwiki-native-index-assessment-v1/supervisor.json').read_text())
    prior_profile=json.loads((BASE/'enwiki-native-index-assessment-preparation-v1/profile.json').read_text())
    if pv['result_SHA256']!=sha(ROOT/'enwiki-native-index-assessment-v1/result.json') or pv['supervisor_SHA256']!=sha(ROOT/'enwiki-native-index-assessment-v1/supervisor.json') or prior_supervisor['result_sha256']!=pv['result_SHA256'] or prior_supervisor['worker_exit_code']!=0 or prior_supervisor['status']!='COMPLETE_NATIVE_INDEX_ROWS_ONLY_NO_ADMISSION':
        raise ValueError('prior_verified_assessment_receipt_chain')
    if p['source']['XML_bytes']!=prior_profile['publisher_XML_bytes']:
        raise ValueError('publisher_XML_offset_bound')
    if r['status']!='COMPLETE_ONE_PASS_INDEX_ASSESSMENT_ROW_SAMPLE_NO_ADMISSION' or r['stats']!=expected['stats'] or not r['all_BZ2_EOF_CRC_verified'] or not r['trailingdata_absent'] or r['source_SHA256']!=expected['SHA256']:
        raise ValueError('prior_complete_index_assessment_binding')
    if w['status']!='COMPLETE_COMPRESSED_NATIVE_INDEX_ONLY_NO_ADMISSION' or s['status']!='COMPLETE_INDEX_ACQUISITION_NO_ADMISSION' or s['worker_exit_code']!=0 or sha(ROOT/'enwiki-native-index-20260801-v1/worker-result.json')!=s['worker_receipt_sha256']:
        raise ValueError('source_acquisition_terminal_binding')
    if [w[k] for k in ['bytes','MD5','SHA1','local_SHA256']]!=[expected[k] for k in ['bytes','MD5','SHA1','SHA256']]:
        raise ValueError('source_triple_checksum_receipt_binding')
    return p


def arm(seconds):
    def stop(s,f):raise TimeoutError('deadline_or_signal')
    for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:signal.signal(sig,stop)
    if seconds<=0:raise TimeoutError('elapsed_limit')
    signal.setitimer(signal.ITIMER_REAL,seconds)


def size(root):
    return sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file())


def storage(whole=False):
    if size(OUT)>OUTPUT-1048576:raise ValueError('aggregate_output4GB')
    if shutil.disk_usage(ROOT).free<FREE:raise ValueError('weights_scratch_free_floor')
    if whole and size(ROOT)>COMBINED:raise ValueError('combined_intake64GB')


def slot(name,obj):
    raw=(json.dumps(obj,indent=2)+'\n').encode();limit=SLOTS[name]
    if len(raw)>limit:raise ValueError('receipt_slot_bound')
    with (OUT/name).open('r+b') as f:
        f.write(raw+b' '*(limit-len(raw)));f.flush();os.fsync(f.fileno())


def worker(a):
    arm(WORK-(clock()-a.start));store=None;progress={};last=0
    try:
        p=verify(a)
        if os.getppid()!=a.supervisor_pid:raise ValueError('supervisor_PID_binding')
        assessor=load('frozen_index_assessor',ASSESSOR)
        store=core.Store(OUT/'index.sqlite')
        def check():
            nonlocal last
            if clock()-a.start>=WORK:raise TimeoutError('worker_elapsed')
            if clock()-last>=1:
                storage();last=clock()
                slot('progress.json',{'source_stats':progress,'SQLite_rows_attempted':store.rows if store else p['source']['stats']['rows'],
                                     'SQLite_rows_committed':store.committed if store else p['source']['stats']['rows'],'groups':store.groups if store else p['source']['stats']['offset_groups'],
                                     'elapsed_seconds':clock()-a.start})
        before=stat(SOURCE)
        with SOURCE.open('rb') as source:
            if stat(SOURCE)!=before or [getattr(os.fstat(source.fileno()),k) for k in ['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns']]!=before:
                raise ValueError('source_descriptor_identity')
            result=core.build(source,assessor,store,p['source'],check,progress)
        store.close();store=None
        with (OUT/'index.sqlite').open('rb') as f:os.fsync(f.fileno())
        directory_fd=os.open(OUT,os.O_RDONLY)
        try:os.fsync(directory_fd)
        finally:os.close(directory_fd)
        if stat(SOURCE)!=before:raise ValueError('source_mutated_during_stream')
        verify(a);storage();check()
        artifact_sha=sha(OUT/'index.sqlite')
        check()
        slot('result.json',{'status':'COMPLETE_INDEX_IDENTITY_FRAME_NO_ADMISSION',
                            'source_stats':result['stats'],'source_SHA256':result['source_SHA256'],
                            'source_MD5':result['source_MD5'],'source_SHA1':result['source_SHA1'],
                            'global_page_ID_uniqueness_proven':True,'all_BZ2_EOF_CRC_verified':True,
                            'trailing_compressed_data_absent':True,'SQLite_integrity_check':'ok',
                            'SQLite_bytes':(OUT/'index.sqlite').stat().st_size,'SQLite_SHA256':artifact_sha,
                            'elapsed_seconds':clock()-a.start,'no_XML_body_read':True,
                            'new_admitted_documents':0,'new_admitted_tokens':0})
    except BaseException as e:
        slot('result.json',{'status':'TERMINAL_PARTIAL_INDEX_NO_RETRY',
                            'error':type(e).__name__+':'+str(e)[:1500],'source_stats':progress,
                            'SQLite_rows_inserted':store.rows if store else None,
                            'SQLite_rows_committed':store.committed if store else None,
                            'partial_database_may_require_integrity_recovery':True,'new_admitted_documents':0})
        raise
    finally:
        if store is not None:store.close()
        signal.setitimer(signal.ITIMER_REAL,0)


def kill(child):
    if child.poll() is None:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    child.wait(timeout=5)


def supervise(a):
    start=clock();arm(EXTERNAL);child=None;created=False;peak=0
    try:
        verify(a)
        if OUT.exists() or OUT.is_symlink():raise ValueError('existing_output_no_retry')
        if size(ROOT)+OUTPUT>COMBINED or shutil.disk_usage(ROOT).free<FREE+OUTPUT:
            raise ValueError('prelaunch_combined_and_protected_headroom')
        OUT.mkdir();created=True
        for name,n in SLOTS.items():(OUT/name).write_bytes(b' '*n)
        with (OUT/'worker.log').open('xb') as log:
            child=subprocess.Popen([sys.executable,'-B',str(HERE/'inventory.py'),'--worker',
                '--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256,
                '--start',str(start),'--supervisor-pid',str(os.getpid())],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        (OUT/'ownership.json').write_text(json.dumps({'supervisor_pid':os.getpid(),'worker_pid':child.pid,'shared_start':start,
            'code_pins_SHA256':a.code_pins_sha256,'profile_SHA256':a.profile_sha256})+'\n')
        helper=load('index_inventory_RSS',RSS_HELPER)
        while child.poll() is None:
            peak=max(peak,helper.tree_rss(os.getpid()))
            if peak>RSS or clock()-start>=WORK:raise ValueError('worker_tree_RSS_or_elapsed')
            storage(True);time.sleep(.5)
        child.wait(timeout=5)
        r=json.loads((OUT/'result.json').read_text())
        if child.returncode!=0 or r['status']!='COMPLETE_INDEX_IDENTITY_FRAME_NO_ADMISSION':raise ValueError('worker_incomplete')
        verify(a);storage(True)
        peak=max(peak,helper.tree_rss(os.getpid()))
        if peak>RSS or clock()-start>=EXTERNAL:raise ValueError('final_tree_RSS_or_elapsed')
        if sha(OUT/'index.sqlite')!=r['SQLite_SHA256']:raise ValueError('independent_SQLite_artifact_hash')
        peak=max(peak,helper.tree_rss(os.getpid()))
        if peak>RSS or clock()-start>=EXTERNAL:raise ValueError('post_hash_RSS_or_elapsed')
        storage(True)
        slot('supervisor.json',{'status':'COMPLETE_INDEX_IDENTITY_FRAME_SUPERVISED_NO_ADMISSION',
            'worker_exit_code':0,'worker_reaped':True,'elapsed_seconds':clock()-start,
            'peak_tree_RSS_bytes':peak,'output_bytes':size(OUT),'worker_receipt_SHA256':sha(OUT/'result.json'),
            'SQLite_SHA256':r['SQLite_SHA256'],'new_admitted_documents':0})
    except BaseException as e:
        if child is not None:kill(child)
        if created:
            obj={'status':'TERMINAL_PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],
                 'worker_reaped':child is None or child.poll() is not None,'new_admitted_documents':0}
            if (OUT/'supervisor.json').exists():slot('supervisor.json',obj)
            else:(OUT/'supervisor.json').write_text(json.dumps(obj)+'\n')
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)


def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true')
    p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True)
    p.add_argument('--start',type=float);p.add_argument('--supervisor-pid',type=int);a=p.parse_args()
    if a.worker:worker(a)
    elif a.execute:supervise(a)
    else:
        arm(120)
        try:verify(a);print('READY_NO_RETAINED_INDEX_OR_XML_BODY_READ')
        finally:signal.setitimer(signal.ITIMER_REAL,0)


if __name__=='__main__':main()
