"""Finite raw20 development capture; no network/parser/model/IntakeLedger."""
import time
START=time.clock_gettime(time.CLOCK_MONOTONIC)
import argparse,contextlib,hashlib,importlib.util,json,os,signal,sqlite3,shutil,subprocess,sys
from pathlib import Path
import capture_core
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake';FREE=53474836480
LIMITS={'compressed_bytes':40000000,'decoded_bytes':256000000,'page_bytes':1000000,'output_bytes':64000000,'worker_seconds':60,'external_seconds':90,'RSS_bytes':1000000000}
SLOTS={'result.json':1048576,'supervisor.json':1048576}
def clock():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def stat(p):
    s=Path(p).stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def alarm(*args):raise TimeoutError('shared_deadline_or_signal')
def required(p):
    source=json.loads(Path(p['source_profile']).read_text())
    return {str(HERE/n) for n in ['capture.py','capture_core.py','selection.py','checks.py','reproduce_selection.py','profile.json','frozen-selection.json','contract.json']}|{p['source_profile'],p['source_guard'],p['supervisor_helpers'],p['size_helper']}|set(p['runtime_pins'])|{x['path'] for x in source['source']['chain'].values()}|set(p['metadata_proof_paths'])
def verify(a):
    if sha(HERE/'profile.json')!=a.profile_sha256 or sha(HERE/'code-pins.json')!=a.codepins_sha256:raise ValueError('external_profile_codepins')
    p=json.loads((HERE/'profile.json').read_text());pins=json.loads((HERE/'code-pins.json').read_text())['SHA256']
    if p['limits']!=LIMITS or set(pins)!=required(p):raise ValueError('exact_limits_input_inventory')
    for path,digest in pins.items():
        if Path(path).is_symlink() or sha(path)!=digest:raise ValueError('pinned_metadata_code_changed')
    if str(Path(sys.executable).resolve())!=p['python']:raise ValueError('runtime_path')
    s=json.loads((HERE/'frozen-selection.json').read_text())
    if s['totals']['pages']!=20 or len(s['selected'])!=20 or len({r['row_ordinal'] for r in s['selected']})!=20 or len(s['groups'])>20:raise ValueError('frozen20identity')
    if [sum(r['selection_role']==role for r in s['selected']) for role in ['ns0_nonredirect','ns0_redirect','nonzero_namespace']]!=[16,2,2]:raise ValueError('frozen_role_counts')
    if sum(g['compressed_bytes'] for g in s['groups'])>LIMITS['compressed_bytes'] or sum(g['decoded_bytes'] for g in s['groups'])>LIMITS['decoded_bytes'] or any(not 0<r['raw_XML_bytes']<=LIMITS['page_bytes'] for r in s['selected']):raise ValueError('precontent_caps')
    frame=p['frame'];fp=Path(frame['path'])
    if stat(fp)!=frame['stat'] or frame['SHA256']!='be10e7a0bc970548f19ef5cb5742048f20e8593597d7989afc05f6ff789df36e':raise ValueError('verified128frame_identity')
    proof=json.loads(Path(p['frame_verification']).read_text())
    if proof['status']!='PASS_COMPLETE_FIRST128_PREFIX_CALIBRATION_METADATA_NOT_FULL_ARCHIVE' or proof['SQLite_SHA256']!=frame['SHA256'] or proof['output_pins']['original-header.xml']!=p['header']['SHA256']:raise ValueError('verified_frame_and_original_header_proof')
    db=sqlite3.connect(fp.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('PRAGMA query_only=ON');db.row_factory=sqlite3.Row
    try:
        for row in s['selected']:
            got=db.execute('SELECT p.*,g.group_ordinal FROM groups g JOIN pages p ON p.row_ordinal BETWEEN g.first_page_ordinal AND g.last_page_ordinal WHERE p.row_ordinal=?',(row['row_ordinal'],)).fetchone()
            if got is None:raise ValueError('selected_frame_row_missing')
            for key in got.keys():
                value=got[key].hex() if key=='raw_SHA256' else got[key]
                if row[key]!=value:raise ValueError('exact_selected_locator_fields')
    finally:db.close()
    receipts=json.loads(Path(p['group_receipts']).read_text())['groups'];ids={r['group_ordinal'] for r in s['selected']}
    if s['groups']!=[g for g in receipts if g['group_ordinal'] in ids]:raise ValueError('exact_verified_group_receipts')
    guard=load('raw20_source_guard',p['source_guard']);binding=guard.verify(json.loads(Path(p['source_profile']).read_text()))
    if stat(binding['path'])!=binding['stat'] or Path(binding['path']).is_symlink():raise ValueError('native_prefix_stat')
    if stat(p['header']['path'])!=p['header']['stat'] or Path(p['header']['path']).is_symlink():raise ValueError('header_stat')
    dependencies(p)
    return p,s,binding

def dependencies(p):
    size=load('raw20_size',p['size_helper']).census;helpers=load('raw20_supervisor_helpers',p['supervisor_helpers'])
    return size,helpers

def disk(out,extra,size):
    n=size(out);remaining=max(0,LIMITS['output_bytes']-n)
    if extra<0 or n+extra>LIMITS['output_bytes'] or size(ROOT)+remaining>64000000000 or shutil.disk_usage(ROOT).free<FREE+remaining:raise ValueError('disk_output_protected_reserves')
def terminal(out,name,obj):
    raw=(json.dumps(obj,sort_keys=True)+'\n').encode();cap=SLOTS[name]
    if len(raw)>cap:raise ValueError('terminal_slot')
    with (Path(out)/name).open('r+b') as f:f.write(raw+b' '*(cap-len(raw)));f.flush();os.fsync(f.fileno())
@contextlib.contextmanager
def readers(p,s,binding,check):
    path=Path(binding['path']);expected=binding['stat'];fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);seen=set();header_seen=[False]
    def custody():
        a=os.fstat(fd)
        if [a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns]!=expected or stat(path)!=expected or path.is_symlink():raise ValueError('native_source_FD_path_custody')
    try:
        custody();allowed={(g['group_ordinal'],g['compressed_start'],g['compressed_end_exclusive']) for g in s['groups']}
        def group(g):
            check();custody();key=(g['group_ordinal'],g['compressed_start'],g['compressed_end_exclusive'])
            if key not in allowed or key in seen:raise ValueError('exact_selected_group_once')
            seen.add(key);n=g['compressed_end_exclusive']-g['compressed_start']
            if not 0<n<=40000000 or g['compressed_end_exclusive']>binding['bytes']:raise ValueError('approved_group_range')
            data=os.pread(fd,n,g['compressed_start']);custody()
            if len(data)!=n:raise ValueError('short_group_source_read')
            return data
        def header():
            if header_seen[0]:raise ValueError('original_header_once')
            header_seen[0]=True;h=p['header'];hp=Path(h['path'])
            if hp.is_symlink() or str(hp.resolve())!=str(hp) or stat(hp)!=h['stat']:raise ValueError('header_before_custody')
            hfd=os.open(hp,os.O_RDONLY|os.O_NOFOLLOW)
            try:data=os.read(hfd,65537);a=os.fstat(hfd)
            finally:os.close(hfd)
            if len(data)>65536 or len(data)!=h['bytes'] or hashlib.sha256(data).hexdigest()!=h['SHA256'] or [a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns]!=h['stat'] or stat(hp)!=h['stat']:raise ValueError('original_header_exact')
            return data
        yield group,header,custody
        custody();check()
        if seen!=allowed or not header_seen[0]:raise ValueError('all_selected_groups_once_header')
    finally:os.close(fd)

def worker(a):
    out=None;owned=False;size=None
    for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:signal.signal(sig,alarm)
    try:
        remaining=a.start+60-clock()
        if remaining<=0:raise TimeoutError('worker_start_expired')
        signal.setitimer(signal.ITIMER_REAL,remaining);p,s,binding=verify(a);out=Path(p['output']);size,helpers=dependencies(p)
        if os.getppid()!=a.supervisor_pid:raise ValueError('actual_parent_PID')
        until=min(clock()+3,a.start+60)
        while not (out/'ownership.json').exists() and clock()<until:time.sleep(.01)
        own=json.loads((out/'ownership.json').read_text())
        if own!={'worker_PID':os.getpid(),'supervisor_PID':a.supervisor_pid,'shared_start':a.start,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.codepins_sha256}:raise ValueError('owned_worker_receipt')
        owned=True;custody=None
        def check():
            if clock()-a.start>=60:raise TimeoutError('worker_shared_deadline')
            disk(out,0,size)
            if custody is not None:custody()
        def write(name,data):
            check();disk(out,len(data),size)
            with (out/name).open('xb') as f:
                if f.write(data)!=len(data):raise ValueError('short_local_write')
                f.flush();os.fsync(f.fileno())
        try:
            with readers(p,s,binding,check) as (read_group,read_header,proof):
                custody=proof;result=capture_core.run(p,s,read_group,read_header,write,check)
        finally:custody=None
        verify(a);check()
        result['artifacts']={q.name:{'bytes':q.stat().st_size,'SHA256':sha(q)} for q in out.iterdir() if q.is_file() and q.name not in SLOTS}
        result.update({'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.codepins_sha256,'inherited_native_prefix_SHA256':binding['SHA256'],'whole_publisher_archive_verified':False,'elapsed_shared_seconds':clock()-a.start})
        terminal(out,'result.json',result)
    except BaseException as e:
        if owned:terminal(out,'result.json',{'status':'PARTIAL_RAW20_CAPTURE_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'new_admitted_documents':0})
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)

def kill(child):
    if child.poll() is None:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    child.wait(timeout=3)
def supervise(a):
    child=None;created=False;out=None;peak=0;old={}
    try:
        for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[sig]=signal.signal(sig,alarm)
        remain=START+85-clock()
        if remain<=0:raise TimeoutError('supervisor_preflight_expired')
        signal.setitimer(signal.ITIMER_REAL,remain);p,s,binding=verify(a);out=Path(p['output']);size,helpers=dependencies(p)
        if out.exists() or out.is_symlink():raise ValueError('once_only_output')
        if size(ROOT)+64000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+64000000:raise ValueError('initial_reserves')
        out.mkdir();created=True
        for n,cap in SLOTS.items():(out/n).write_bytes(b' '*cap)
        child=subprocess.Popen([sys.executable,'-B',str(HERE/'capture.py'),'--worker','--start',str(START),'--supervisor-pid',str(os.getpid()),'--profile-sha256',a.profile_sha256,'--codepins-sha256',a.codepins_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        own={'worker_PID':child.pid,'supervisor_PID':os.getpid(),'shared_start':START,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.codepins_sha256}
        with (out/'ownership.json').open('x') as f:json.dump(own,f);f.flush();os.fsync(f.fileno())
        while child.poll() is None:
            if clock()-START>=85:raise TimeoutError('external_deadline')
            rss=helpers.tree_rss(subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1).stdout,os.getpid(),child.pid if child.poll() is None else None);peak=max(peak,rss)
            if peak>1000000000:raise ValueError('owned_RSS_cap')
            disk(out,0,size);time.sleep(.1)
        child.wait(timeout=3);verify(a);disk(out,0,size);r=json.loads((out/'result.json').read_text());ok=child.returncode==0 and r.get('status')=='COMPLETE_RAW_DEVELOPMENT20_CAPTURE_NO_ADMISSION'
        terminal(out,'supervisor.json',{'status':'COMPLETE_RAW20_CAPTURE_NO_ADMISSION' if ok else 'PARTIAL_RAW20_CAPTURE_NO_RETRY','worker_exit_code':child.returncode,'worker_reaped':True,'result_SHA256':sha(out/'result.json'),'elapsed_shared_seconds':clock()-START,'peak_tree_RSS_bytes':peak,'new_admitted_documents':0})
        return 0 if ok else 1
    except BaseException as e:
        signal.setitimer(signal.ITIMER_REAL,max(.001,START+90-clock()))
        if child is not None:kill(child)
        if created:terminal(out,'supervisor.json',{'status':'PARTIAL_RAW20_CAPTURE_NO_RETRY','worker_reaped':child is None or child.poll() is not None,'error':type(e).__name__+':'+str(e)[:1000],'new_admitted_documents':0})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for sig,handler in old.items():signal.signal(sig,handler)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--profile-sha256',required=True);p.add_argument('--codepins-sha256',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--start',type=float);p.add_argument('--supervisor-pid',type=int);a=p.parse_args()
    if a.worker:worker(a)
    elif a.execute:raise SystemExit(supervise(a))
    else:verify(a);print('READY_METADATA_ONLY_NO_NATIVE_SOURCE_CAPTURE')
