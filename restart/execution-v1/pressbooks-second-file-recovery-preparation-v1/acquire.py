"""Two separately dispatched finite raw acquisitions; no decompression/quality."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import sqlite3
import ssl
import subprocess
import sys
import time
import urllib.request
import http.client
import transport as t

HERE=Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake'
ORIGINAL=BASE/'pressbooks-hansard-acquisition-metadata-preparation-v1'
TLS=ROOT/'gutenberg-preparation-parallel-v4/discover.py'
CA=Path('/opt/homebrew/etc/ca-certificates/cert.pem')
RSS_HELPER=BASE/'wikibooks-current20-native-source-capture-preparation-v2/supervisor_core.py'
FREE=53474836480;COMBINED=64000000000
SLOTS={'worker-result.json':262144,'supervisor-result.json':65536,'current-attempt.json':65536,'progress.json':16384}


def clock():return time.clock_gettime(time.CLOCK_MONOTONIC)


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def stat(path):
    s=Path(path).stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def runtime():
    return {'Python':sys.version,'launcher':sys.executable,'binary':str(Path(sys.executable).resolve()),
            'OpenSSL':ssl.OPENSSL_VERSION,'SQLite':sqlite3.sqlite_version,'platform':platform.platform()}


def helpers():
    sys.path[:0]=[str(BASE),str(REPO/'src')]
    import acquire_sources
    from slm.data import intake_ledger
    if Path(acquire_sources.__file__).resolve()!=BASE/'acquire_sources.py' or Path(intake_ledger.__file__).resolve()!=REPO/'src/slm/data/intake_ledger.py':raise t.Fault('ledger_import_origin')
    tls=load('pinned_hf_TLS',TLS);context=tls.trusted_context()
    if context.verify_mode!=ssl.CERT_REQUIRED or not context.check_hostname:raise t.Fault('strict_TLS_required')
    return acquire_sources.IntakeLedger,acquire_sources.CONTRACT,context


def verify(a):
    if sha(HERE/'code-pins.json')!=a.code_pins_sha256 or sha(HERE/'profiles.json')!=a.profiles_sha256:raise t.Fault('external_pins')
    all_profiles=json.loads((HERE/'profiles.json').read_text());pins=json.loads((HERE/'code-pins.json').read_text())['SHA256']
    if set(pins)!=set(all_profiles['required_inventory']):raise t.Fault('exact_inventory')
    for path,h in pins.items():
        if Path(path).is_symlink() or sha(path)!=h:raise t.Fault('pinned_input_changed')
    if runtime()!=json.loads((HERE/'runtime.json').read_text()):raise t.Fault('runtime_changed')
    source=a.source
    if source!='pressbooks':raise t.Fault('PressBooks_second_file_only_no_Hansard')
    p=all_profiles['sources'][source]
    original=json.loads((ORIGINAL/(source+'-profile.proposed.json')).read_text())
    manifest=json.loads((ORIGINAL/(source+'-files.json')).read_text())
    fixed_limits={**original['limits'],'body_bytes_exact':174453169,
        'body_reservation_including_one_byte_EOF_probe_per_file':174453170,
        'output_precharge_bytes':200000000,'max_physical_GETs':3}
    if sha(ORIGINAL/(source+'-files.json'))!=original['source_manifest_sha256'] or p['limits']!=fixed_limits or p['output']!=str(ROOT/'common-pile-pressbooks-second-file-recovery-v2'):raise t.Fault('frozen_second_file_recovery_scope')
    first=json.loads((BASE/'pressbooks-first-shard-parent-integrity-v1/verification.json').read_text())
    if p['inherited_first']!=first or first['status']!='PASS_EXACT_FIRST_SHARD_LOCAL_INTEGRITY_ONLY' or first['bytes']!=247301311 or first['SHA256']!='67d1135ad65d3c1f2f4d88d44ad35d37a4e381cb518c1bd878e4d2c350c9ff21' or first['path']!=str(ROOT/'common-pile-pressbooks-raw-v1/00000_pressbooks.json.gz'):raise t.Fault('inherited_first_exact_parent_binding')
    prior=ROOT/'common-pile-pressbooks-raw-v1'
    o=json.loads((prior/'ownership.json').read_text());terminal=json.loads((prior/'supervisor-result.json').read_text())
    for key in ['supervisor_pid','worker_pid']:
        try:os.kill(o[key],0)
        except ProcessLookupError:pass
        else:raise t.Fault('prior_PressBooks_owner_not_reaped')
    if terminal['status']!='TERMINAL_PARTIAL_SOURCE_NO_RETRY' or terminal['worker_reaped'] is not True:raise t.Fault('prior_PressBooks_failure_not_preserved')
    expected=[]
    for f in manifest['files']:
        relative=Path(f['path'])
        if relative.is_absolute() or '..' in relative.parts or not relative.parts:raise t.Fault('manifest_relative_path')
        expected.append({'ordinal':f['ordinal'],'path':f['path'],'url':f['future_body_url'],
            'expected_bytes':f['expected_bytes'],'expected_sha256':f['expected_sha256'],'revision':manifest['immutable_revision']})
    expected=[f for f in expected if f['ordinal']==1]
    if p['files']!=expected or len(expected)!=1 or expected[0]['expected_bytes']!=174453169 or p['hosts']!=sorted(t.HOSTS):raise t.Fault('exact_second_immutable_file_only')
    if http.client._MAXHEADERS!=100 or http.client._MAXLINE!=65536:raise t.Fault('HTTP_parser_bounds')
    for item in expected:t.url(item['url'])
    helpers();return p


def owned(p):
    key=p['key'];return [key+'-output']+[key+f'-body-{f["ordinal"]:03}' for f in p['files']]+[key+f'-hop-{f["ordinal"]:03}-{hop}' for f in p['files'] for hop in range(3)]


def settle(ledger,p):
    changed=[]
    for key in owned(p):
        row=ledger.db.execute('SELECT state FROM attempts WHERE key=?',(key,)).fetchone()
        if row==('pending',):ledger.finish(key,raw=None);changed.append(key)
    return changed


def custody(ledger,p):
    result=[]
    for key in owned(p):
        row=ledger.db.execute('SELECT charge,state,actual_bytes,body_sha256 FROM attempts WHERE key=?',(key,)).fetchone()
        result.append({'key':key,'state':'UNATTEMPTED_NOT_RESERVED' if row is None else row[1],
            'charge':None if row is None else json.loads(row[0]),'actual_successful_body_bytes':None if row is None else row[2],
            'successful_body_SHA256':None if row is None else row[3]})
    return result


def handoff(source):
    path=ROOT/'enwiki-native-segmented-tail-20260801-v1'
    ownership=json.loads((path/'ownership.json').read_text())
    for field in ['supervisor_pid','coordinator_pid']:
        try:os.kill(ownership[field],0)
        except ProcessLookupError:pass
        else:raise t.Fault('segmented_supervisor_or_coordinator_not_reaped')
    supervisor=json.loads((path/'supervisor-result.json').read_text())
    if supervisor['status'] not in ['COMPLETE_VIRTUAL_ARCHIVE_NO_ADMISSION','TERMINAL_PARTIAL_NO_RETRY_NO_COMPLETE_ARCHIVE'] or supervisor['coordinator_reaped'] is not True:raise t.Fault('segmented_terminal_handoff_missing')
    result={'segmented_ownership_SHA256':sha(path/'ownership.json'),'segmented_supervisor_SHA256':sha(path/'supervisor-result.json'),'both_segmented_PIDs_absent':True,'segmented_terminal_status':supervisor['status']}
    if source=='uk_hansard':
        previous=ROOT/'common-pile-pressbooks-raw-v1'
        owner=json.loads((previous/'ownership.json').read_text());terminal=json.loads((previous/'supervisor-result.json').read_text())
        for field in ['supervisor_pid','worker_pid']:
            try:os.kill(owner[field],0)
            except ProcessLookupError:pass
            else:raise t.Fault('PressBooks_before_Hansard_not_reaped')
        if terminal['status'] not in ['COMPLETE_RAW_SOURCE_FILES_NO_ADMISSION','TERMINAL_PARTIAL_SOURCE_NO_RETRY'] or not terminal['worker_reaped']:raise t.Fault('PressBooks_terminal_required_before_Hansard')
        result['PressBooks_terminal_SHA256']=sha(previous/'supervisor-result.json')
    return result


def size(path):return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())


def disk(p,additional=0):
    out=Path(p['output']);current=size(out);cap=p['limits']['output_precharge_bytes']
    if additional<0 or current+additional>cap-1048576:raise t.Fault('source_output_prewrite_cap')
    remaining=max(0,cap-current)
    if size(ROOT)+remaining>COMBINED or shutil.disk_usage(ROOT).free<FREE+remaining:
        raise t.Fault('combined64GB_or_weights_scratch_remaining_reserve')


def save(p,name,obj,replace=False):
    out=Path(p['output']);raw=(json.dumps(obj,indent=2)+'\n').encode()
    if not replace:disk(p,len(raw))
    if replace:
        if name not in SLOTS or len(raw)>SLOTS[name]:raise t.Fault('fixed_receipt_slot')
        with (out/name).open('r+b') as f:f.write(raw+b' '*(SLOTS[name]-len(raw)));f.flush();os.fsync(f.fileno())
    else:
        with (out/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())


def mark_body_complete(ledger,key,receipt):
    row=ledger.db.execute('SELECT charge,state FROM attempts WHERE key=?',(key,)).fetchone()
    if row is None or row[1]!='pending' or json.loads(row[0])!={'requests':0,'body_bytes':receipt['bytes']+1,'rows':0,'output_bytes':0}:raise t.Fault('exact_body_allocation')
    if ledger.db.execute('UPDATE attempts SET state=?,actual_bytes=?,body_sha256=? WHERE key=? AND state=?',('complete',receipt['bytes'],receipt['SHA256'],key,'pending')).rowcount!=1:raise t.Fault('body_complete_exactonce')


def verify_inherited(p,guard):
    """Read-only bounded-buffer proof; original first shard never copied/GET."""
    first=p['inherited_first'];path=Path(first['path']);guard()
    if path.is_symlink() or str(path.resolve())!=str(path) or stat(path)!=first['stat'] or path.stat().st_size!=first['bytes']:raise t.Fault('inherited_first_stat_or_path')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        fstat=os.fstat(fd)
        if [fstat.st_dev,fstat.st_ino,fstat.st_size,fstat.st_mtime_ns,fstat.st_ctime_ns]!=first['stat']:raise t.Fault('inherited_first_FD_stat')
        digest=hashlib.sha256();n=0
        while True:
            data=os.read(fd,1048576)
            if not data:break
            n+=len(data)
            if n>first['bytes']:raise t.Fault('inherited_first_excess')
            digest.update(data)
        after=os.fstat(fd)
        if [after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns]!=first['stat'] or stat(path)!=first['stat'] or n!=first['bytes'] or digest.hexdigest()!=first['SHA256']:raise t.Fault('inherited_first_readonly_SHA256_binding')
    finally:os.close(fd)
    guard()
    return {'path':str(path),'bytes':n,'SHA256':digest.hexdigest(),'stat':first['stat'],'method':'READONLY_NOFOLLOW_STREAM_SHA256_NO_COPY_NO_GET'}


def worker(a,start):
    ledger=None;p=None;records=[];state={'last_start':None,'requests':0};file_deadline=None
    try:
        p=verify(a);out=Path(p['output']);limit=p['limits']['worker_seconds']
        if os.getppid()!=a.supervisor_pid:raise t.Fault('owned_parent_PID')
        L,C,context=helpers();ledger=L(ROOT/'charges',C)
        allocation=ledger.db.execute('SELECT charge,state FROM attempts WHERE key=?',(p['key']+'-output',)).fetchone()
        if allocation is None or allocation[1]!='pending' or json.loads(allocation[0])!={'requests':0,'body_bytes':0,'rows':0,'output_bytes':p['limits']['output_precharge_bytes']}:raise t.Fault('exact_output_precharge')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),t.NoRedirect(),urllib.request.HTTPSHandler(context=context))
        def check():
            if clock()-start>=limit or (file_deadline is not None and clock()>=file_deadline):raise TimeoutError('shared_or_file_deadline')
            ledger.check_time();disk(p)
        def arm_io():
            seconds=min(start+limit,file_deadline)-clock()
            if seconds<=0:raise TimeoutError('shared_or_file_deadline')
            signal.setitimer(signal.ITIMER_REAL,seconds)
            return min(30,seconds)
        inherited=verify_inherited(p,check)
        for item in p['files']:
            file_deadline=min(start+limit,clock()+p['limits']['per_file_seconds_all_hops']);check()
            partial=out/(item['path']+'.partial')
            receipt=t.acquire(item,partial,ledger,p['key']+f'-body-{item["ordinal"]:03}',
                [p['key']+f'-hop-{item["ordinal"]:03}-{h}' for h in range(3)],opener,check,
                lambda n,r,replace:save(p,n,r,replace),state,arm_io)
            if partial.is_symlink() or partial.stat().st_size!=item['expected_bytes'] or sha(partial)!=item['expected_sha256']:raise t.Fault('worker_independent_local_hash')
            check();final=out/item['path'];os.replace(partial,final)
            fd=os.open(final.parent,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
            mark_body_complete(ledger,p['key']+f'-body-{item["ordinal"]:03}',receipt)
            receipt['file']=item['path'];receipt['stat']=stat(final);save(p,f'file-{item["ordinal"]:03}.receipt.json',receipt)
            records.append(receipt);save(p,'progress.json',{'completed_files':len(records),'expected_files':len(p['files']),
                'verified_file_bytes':sum(r['bytes'] for r in records),'physical_GETs':state['requests'],'elapsed_seconds':clock()-start},True)
            file_deadline=None;signal.setitimer(signal.ITIMER_REAL,max(.001,start+limit-clock()))
        check();verify(a)
        save(p,'worker-result.json',{'status':'COMPLETE_WORKER_RAW_FILES_PENDING_INDEPENDENT_SUPERVISOR',
            'records':records,'inherited_first':inherited,'physical_GETs':state['requests'],'verified_raw_bytes':sum(r['bytes'] for r in records),
            'elapsed_seconds':clock()-start,'new_admitted_documents':0,'no_decompression_or_quality_claim':True},True)
        return 0
    except BaseException as error:
        signal.setitimer(signal.ITIMER_REAL,0)
        if ledger is not None:settle(ledger,p)
        if p is not None:
            save(p,'worker-result.json',{'status':'TERMINAL_PARTIAL_WORKER_NO_RETRY','error':t.safe_error(error),
                'completed_files':len(records),'physical_GETs':state['requests'],'new_admitted_documents':0},True)
        return 1
    finally:
        if ledger is not None:ledger.close()


def kill(child):
    if child.poll() is None:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    child.wait(timeout=3)


def independent_files(ledger,p,worker_result,guard):
    """Independent local bytes, exact file/hop identities and charged count."""
    receipts=[];last_start=None;hop_count=0;out=Path(p['output'])
    for item in p['files']:
        guard();path=out/item['path'];r=json.loads((out/f'file-{item["ordinal"]:03}.receipt.json').read_text())
        if r['source_ordinal']!=item['ordinal'] or r['file']!=item['path'] or r['body_key']!=p['key']+f'-body-{item["ordinal"]:03}' or r['status']!='COMPLETE_EXACT_BYTES_SHA256_RAW_FILE' or r['expected_bytes']!=item['expected_bytes'] or r['expected_SHA256']!=item['expected_sha256'] or r['bytes']!=item['expected_bytes'] or r['SHA256']!=item['expected_sha256']:
            raise t.Fault('exact_file_receipt_identity')
        if path.is_symlink() or stat(path)!=r['stat'] or path.stat().st_size!=item['expected_bytes'] or sha(path)!=item['expected_sha256'] or stat(path)!=r['stat']:raise t.Fault('supervisor_raw_file_stat_size_SHA256')
        guard()
        row=ledger.db.execute('SELECT charge,state,actual_bytes,body_sha256 FROM attempts WHERE key=?',(r['body_key'],)).fetchone()
        if row is None or row[1:]!=('complete',item['expected_bytes'],item['expected_sha256']) or json.loads(row[0])!={'requests':0,'body_bytes':item['expected_bytes']+1,'rows':0,'output_bytes':0}:raise t.Fault('body_ledger_receipt_binding')
        if not 1<=len(r['hops'])<=3:raise t.Fault('physical_hop_count')
        for ordinal,hop in enumerate(r['hops']):
            expected=p['key']+f'-hop-{item["ordinal"]:03}-{ordinal}'
            if hop['key']!=expected or hop['hop']!=ordinal or hop['request_precharged'] is not True or hop['headers']['status'] not in ([200] if ordinal==len(r['hops'])-1 else [301,302,303,307,308]):raise t.Fault('physical_hop_identity_status')
            instant=hop['start_monotonic']
            if type(instant) not in (float,int) or not 0<instant<float('inf') or (last_start is not None and instant-last_start<1):raise t.Fault('physical_GET_start_spacing')
            last_start=instant;hop_count+=1
            row=ledger.db.execute('SELECT charge,state,actual_bytes FROM attempts WHERE key=?',(expected,)).fetchone()
            if row is None or row[1:]!=('complete',0) or json.loads(row[0])!={'requests':1,'body_bytes':0,'rows':0,'output_bytes':0}:raise t.Fault('physical_hop_accounting')
        receipts.append(r)
    if receipts!=worker_result['records'] or worker_result['physical_GETs']!=hop_count or hop_count>p['limits']['max_physical_GETs'] or worker_result['verified_raw_bytes']!=sum(i['expected_bytes'] for i in p['files']):raise t.Fault('worker_independent_aggregate')
    used={h['key'] for r in receipts for h in r['hops']}
    for key in owned(p):
        if '-hop-' in key and key not in used and ledger.db.execute('SELECT 1 FROM attempts WHERE key=?',(key,)).fetchone() is not None:raise t.Fault('unexpected_extra_hop_charge')
    return receipts


def supervise(a,start):
    p=None;ledger=None;child=None;created=False;allocated=False;peak=0
    try:
        p=verify(a);out=Path(p['output']);handoff_receipt=handoff(a.source)
        if out.exists() or out.is_symlink():raise t.Fault('existing_output_no_retry')
        disk(p);L,C,_=helpers();ledger=L(ROOT/'charges',C)
        if ledger.db.execute("SELECT COUNT(*) FROM attempts WHERE state='pending'").fetchone()[0]:raise t.Fault('other_pending_global_operation')
        totals=ledger.totals();limits=p['limits']
        if totals['body_bytes']+limits['body_reservation_including_one_byte_EOF_probe_per_file']>C['limits']['body_bytes'] or totals['output_bytes']+limits['output_precharge_bytes']>C['limits']['output_bytes'] or totals['requests']+limits['max_physical_GETs']>C['limits']['requests']:raise t.Fault('global_intake_budget')
        ledger.reserve(p['key']+'-output',requests=0,body_bytes=0,output_bytes=limits['output_precharge_bytes']);allocated=True;ledger.close();ledger=None
        out.mkdir();created=True
        for name,n in SLOTS.items():(out/name).write_bytes(b' '*n)
        save(p,'handoff.json',handoff_receipt)
        with (out/'worker.log').open('xb') as log:
            child=subprocess.Popen([sys.executable,'-B',str(HERE/'entry.py'),'--worker','--source',a.source,
                '--code-pins-sha256',a.code_pins_sha256,'--profiles-sha256',a.profiles_sha256,
                '--start',str(start),'--supervisor-pid',str(os.getpid())],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        save(p,'ownership.json',{'supervisor_pid':os.getpid(),'worker_pid':child.pid,'shared_start':start,
            'source':a.source,'code_pins_SHA256':a.code_pins_sha256,'profiles_SHA256':a.profiles_sha256})
        helper=load('HF_owned_RSS',RSS_HELPER)
        while child.poll() is None:
            peak=max(peak,helper.tree_rss(os.getpid()))
            if peak>limits['observed_process_tree_RSS_bytes'] or clock()-start>=limits['worker_seconds']:raise t.Fault('owned_tree_RSS_or_worker_time')
            disk(p);time.sleep(.2)
        child.wait(timeout=3);worker_result=json.loads((out/'worker-result.json').read_text())
        if child.returncode!=0 or worker_result['status']!='COMPLETE_WORKER_RAW_FILES_PENDING_INDEPENDENT_SUPERVISOR':raise t.Fault('worker_incomplete')
        L,C,_=helpers();ledger=L(ROOT/'charges',C)
        inherited=verify_inherited(p,lambda:disk(p))
        if worker_result.get('inherited_first')!=inherited:raise t.Fault('worker_supervisor_inherited_first_proof')
        verified_receipts=independent_files(ledger,p,worker_result,lambda:disk(p))
        verify(a);disk(p);peak=max(peak,helper.tree_rss(os.getpid()))
        if clock()-start>=limits['external_seconds_including_preflight_hashes_and_terminal'] or peak>limits['observed_process_tree_RSS_bytes']:raise t.Fault('terminal_resource_bound')
        save(p,'combined-files.json',{'status':'COMPLETE_TWO_RAW_FILES_REUSING_FIRST_NO_ADMISSION',
            'retained_first':inherited,'new_second':{'path':str(out/p['files'][0]['path']),
            'bytes':p['files'][0]['expected_bytes'],'SHA256':p['files'][0]['expected_sha256'],'stat':stat(out/p['files'][0]['path'])},
            'combined_compressed_bytes':421754480,'new_downloaded_file_count':1,
            'old_failed_attempt_preserved':True,'first_file_copied_or_redownloaded':False,'decompressed':False,'new_admitted_documents':0})
        verify(a);disk(p)
        ledger.finish(p['key']+'-output',raw=b'');terminal_custody=custody(ledger,p);ledger.close();ledger=None
        save(p,'supervisor-result.json',{'status':'COMPLETE_RAW_SOURCE_FILES_NO_ADMISSION','worker_reaped':True,
            'worker_exit_code':0,'new_files':len(p['files']),'combined_files':2,'combined_manifest_SHA256':sha(out/'combined-files.json'),'raw_bytes':sum(f['expected_bytes'] for f in p['files']),
            'worker_receipt_SHA256':sha(out/'worker-result.json'),'peak_tree_RSS_bytes':peak,'owned_allocations':terminal_custody,
            'elapsed_seconds':clock()-start,'new_admitted_documents':0,'no_decompression':True},True)
        return 0
    except BaseException as error:
        if p is not None:
            # Cleanup is bounded by the original shared external deadline too.
            remaining=start+p['limits']['external_seconds_including_preflight_hashes_and_terminal']-clock()
            signal.setitimer(signal.ITIMER_REAL,max(.001,remaining))
        if child is not None:kill(child)
        if ledger is not None:ledger.close();ledger=None
        settled=[];terminal_custody=[]
        if allocated:
            L,C,_=helpers();ledger=L(ROOT/'charges',C);settled=settle(ledger,p);terminal_custody=custody(ledger,p);ledger.close();ledger=None
        if created:
            # Do not rehash unknown failed bodies outside the finite budget.
            partials=[{'path':str(q.relative_to(out)),'bytes':q.stat().st_size} for q in out.rglob('*.partial') if q.is_file()]
            record={'status':'TERMINAL_PARTIAL_SOURCE_NO_RETRY','worker_reaped':child is None or child.poll() is not None,
                'error':t.safe_error(error),'owned_pending_settled_failed_no_refund':settled,
                'retained_partial_files':partials,'owned_allocations':terminal_custody,'unknown_partial_full_hash_not_claimed':True,'new_admitted_documents':0}
            if (out/'supervisor-result.json').exists():save(p,'supervisor-result.json',record,True)
            else:
                with (out/'supervisor-result.json').open('x') as f:json.dump(record,f)
        return 1
    finally:
        if ledger is not None:ledger.close()


def main(start,boot_start):
    p=argparse.ArgumentParser();p.add_argument('--source',choices=['pressbooks','uk_hansard'],required=True)
    p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profiles-sha256',required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true')
    p.add_argument('--start',type=float);p.add_argument('--supervisor-pid',type=int);a=p.parse_args()
    if a.worker:return worker(a,start)
    if a.execute:return supervise(a,start)
    verify(a);print('READY_STATIC_NO_GET_OR_GLOBAL_LEDGER_WRITES_HANDOFF_REQUIRED');return 0
