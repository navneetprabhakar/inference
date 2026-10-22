"""Once-only offline terminal-prefix calibration. No network or IntakeLedger."""
import time
ENTRY_START=time.clock_gettime(time.CLOCK_MONOTONIC)
import argparse,hashlib,json,os,re,signal,shutil,subprocess,sys
from pathlib import Path
import engine,source_guard
HERE=Path(__file__).resolve().parent
BASE=HERE.parent;ROOT=BASE/'m2-intake'
FREE=53474836480
SLOTS={'result.json':1048576,'supervisor.json':65536}
LIMITS={'compressed_bytes':1376358,'decoded_bytes':32000000,'worker_seconds':30,'external_seconds':45,'RSS_bytes':256000000,'all_output_bytes':4000000,'max_group_compressed_bytes':2000000,'network_requests':0}

def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(path):return hashlib.sha256(source_guard.small(path)).hexdigest()
def size(path):return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())
def required(profile):
    paths={str(HERE/n) for n in ['pilot.py','engine.py','source_guard.py','checks.py','profile.json']}
    paths|={profile[k] for k in ['semantic_module','span_helper','selection_path','rows_path']}
    paths|={x['path'] for x in profile['source']['chain'].values()}
    paths|=set(profile['runtime_pins'])
    paths|=set(profile['failed_calibration_receipts'])
    return paths

def verify(a):
    if sha(HERE/'profile.json')!=a.profile_sha256:raise ValueError('external_profile_pin')
    profile=json.loads(source_guard.small(HERE/'profile.json'))
    if profile['limits']!=LIMITS:raise ValueError('fixed_diagnostic_limits')
    if sha(HERE/'code-pins.json')!=a.code_pins_sha256:raise ValueError('external_codepins_pin')
    pins=json.loads(source_guard.small(HERE/'code-pins.json'))['SHA256']
    if set(pins)!=required(profile):raise ValueError('exact_required_inventory')
    if sum(Path(p).stat().st_size for p in pins)>8000000:raise ValueError('metadata_preflight8MB')
    for p,d in pins.items():
        if sha(p)!=d:raise ValueError('code_runtime_metadata_pin_changed')
    if str(Path(sys.executable).resolve())!=profile['python']:raise ValueError('actual_runtime_path')
    selection=json.loads(source_guard.small(profile['selection_path']))
    if selection['groups'][22]!=profile['target_group'] or selection['header_bytes']!=570:raise ValueError('exact_frozen_group23')
    rows=[json.loads(x) for x in source_guard.small(profile['rows_path']).splitlines()][2200:2300]
    if len(rows)!=100 or [r[0] for r in rows]!=list(range(2201,2301)):raise ValueError('exact100_index_ordinals')
    for row in rows:
        ordinal,group,pid,title,h,n,ends,text=row;b=text.encode('utf8')
        if group!=23 or len(b)!=n or hashlib.sha256(b).hexdigest()!=h or ends!=int(b.endswith(b'\n')) or b.rstrip(b'\n').split(b':',2)!=[b'24391408',str(pid).encode(),title.encode()]:raise ValueError('exact_raw_index_identity')
    binding=source_guard.verify(profile)
    return profile,selection,rows,binding

def terminal(out,name,obj):
    raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True)+'\n').encode();cap=SLOTS[name]
    if len(raw)>cap:raise ValueError('terminal_reserved_slot')
    with (Path(out)/name).open('r+b') as f:f.write(raw+b' '*(cap-len(raw)));f.flush();os.fsync(f.fileno())
def tree_rss(snapshot,root,worker=None):
    if not isinstance(snapshot,str) or len(snapshot)>1048576:raise ValueError('invalid_RSS_snapshot')
    rows={}
    for line in snapshot.splitlines():
        if not line.strip():continue
        f=line.split()
        if len(f)!=3 or any(re.fullmatch('[0-9]+',v) is None for v in f):raise ValueError('malformed_RSS_snapshot')
        p,q,r=map(int,f)
        if p<=0 or p==q or p in rows:raise ValueError('invalid_RSS_PID')
        rows[p]=(q,r)
    if root not in rows or rows[root][1]<=0:raise ValueError('missing_positive_root_RSS')
    owned={root}
    while True:
        n=owned|{p for p,(q,r) in rows.items() if q in owned}
        if n==owned:break
        owned=n
    if worker is not None and (worker not in owned or rows[worker][1]<=0):raise ValueError('missing_positive_owned_worker_RSS')
    return sum(rows[p][1]*1024 for p in owned)
def kill(child):
    if child.poll() is None:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    child.wait(timeout=3)
def alarm(signum,frame):raise TimeoutError('shared_external_deadline_or_signal')
def guard(out,start,seconds,extra=0,custody=None):
    if clk()-start>=seconds:raise TimeoutError('shared_deadline')
    if size(out)+extra>4000000 or shutil.disk_usage(ROOT).free<FREE+extra:raise ValueError('aggregate_output_or_free_floor')
    if custody is not None:custody()

def worker(a):
    owned=False;out=None;start=a.start;custody=None
    signal.signal(signal.SIGALRM,alarm)
    try:
        remaining=30-(clk()-start)
        if remaining<=0:raise TimeoutError('expired_before_preflight')
        signal.setitimer(signal.ITIMER_REAL,remaining)
        profile,selection,rows,binding=verify(a);out=Path(profile['output'])
        if os.getppid()!=a.supervisor_pid:raise ValueError('actual_parent_PID')
        # Ownership is written by parent immediately after Popen. Wait bounded
        # only for that exact receipt; never source-read before identity proves.
        wait_end=min(clk()+3,start+30)
        while not (out/'ownership.json').exists() and clk()<wait_end:time.sleep(.01)
        o=json.loads(source_guard.small(out/'ownership.json'))
        if o['worker_PID']!=os.getpid() or o['supervisor_PID']!=a.supervisor_pid or o['shared_start']!=start or o['profile_SHA256']!=a.profile_sha256 or o['codepins_SHA256']!=a.code_pins_sha256:raise ValueError('owned_worker_receipt')
        owned=True
        def check(extra=0):guard(out,start,30,extra,custody)
        try:
            with source_guard.opened(binding,check) as read_at:
                custody=read_at.assert_custody
                result=engine.run(profile,selection,rows,read_at,out,check)
        finally:
            # FD-backed closure must not outlive the owned reader context.
            custody=None
        source_guard.verify(profile);verify(a);check()
        if source_guard.ident(Path(binding['path']).stat())!=binding['stat']:raise ValueError('postflight_source_path_stat')
        result.update({'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256,
            'source_prefix_SHA256_inherited':binding['SHA256'],'source_trust_class':'TLS_ETAG_TERMINAL_LOCALPREFIX_FRESHHASH_STAT_CRC_INDEX',
            'whole_publisher_archive_verified':False,'additional_whole_prefix_rehash_bytes':0,
            'elapsed_shared_seconds':clk()-start})
        result['artifacts']={p.name:{'bytes':p.stat().st_size,'SHA256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in out.iterdir() if p.name not in SLOTS and p.is_file()}
        terminal(out,'result.json',result)
    except BaseException as e:
        if owned:terminal(out,'result.json',{'status':'PARTIAL_CALIBRATION_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'elapsed_shared_seconds':clk()-start,'new_admitted_documents':0})
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)

def supervise(a):
    start=ENTRY_START;child=None;created=False;out=None;old={};peak=0
    try:
        for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[sig]=signal.signal(sig,alarm)
        remaining=45-(clk()-start)
        if remaining<=0:raise TimeoutError('expired_before_supervisor_preflight')
        signal.setitimer(signal.ITIMER_REAL,remaining)
        profile,selection,rows,binding=verify(a);out=Path(profile['output'])
        if out.exists() or out.is_symlink():raise ValueError('once_only_output')
        if size(ROOT)+4000000>4000000000 or shutil.disk_usage(ROOT).free<FREE+4000000:raise ValueError('combined_intake_and_free_reserves')
        out.mkdir();created=True
        for n,c in SLOTS.items():(out/n).write_bytes(b' '*c)
        child=subprocess.Popen([sys.executable,str(HERE/'pilot.py'),'--worker','--start',str(start),
          '--supervisor-pid',str(os.getpid()),'--profile-sha256',a.profile_sha256,
          '--code-pins-sha256',a.code_pins_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        owner={'worker_PID':child.pid,'supervisor_PID':os.getpid(),'shared_start':start,
               'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256}
        b=(json.dumps(owner)+'\n').encode()
        with (out/'ownership.json').open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
        while child.poll() is None:
            guard(out,start,45)
            ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
            rss=tree_rss(ps.stdout,os.getpid(),child.pid if child.poll() is None else None);peak=max(peak,rss)
            if rss>256000000:raise ValueError('observed_process_tree_RSS_limit')
            time.sleep(.1)
        child.wait(timeout=3);guard(out,start,45)
        result=json.loads(source_guard.small(out/'result.json'))
        ok=child.returncode==0 and result.get('status')=='COMPLETE_GROUP23_IDENTITY_DIAGNOSTIC_NO_ADMISSION'
        terminal(out,'supervisor.json',{'status':'COMPLETE_CALIBRATION_PREFIX_ONLY_NO_ADMISSION' if ok else 'PARTIAL_CALIBRATION_NO_RETRY',
           'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,
           'result_SHA256':sha(out/'result.json'),'all_output_bytes':size(out),'new_admitted_documents':0})
        return 0 if ok else 1
    except BaseException as e:
        if child is not None:kill(child)
        if created:terminal(out,'supervisor.json',{'status':'PARTIAL_CALIBRATION_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,'new_admitted_documents':0})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for sig,h in old.items():signal.signal(sig,h)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true')
    parser.add_argument('--profile-sha256',required=True);parser.add_argument('--code-pins-sha256',required=True)
    parser.add_argument('--start',type=float);parser.add_argument('--supervisor-pid',type=int);a=parser.parse_args()
    if a.worker:worker(a)
    elif a.execute:raise SystemExit(supervise(a))
    else:verify(a);print('PREPARATION_ONLY_NO_NATIVE_READ_OR_EXECUTION')
