"""Once-only offline terminal-prefix calibration. No network or IntakeLedger."""
import time
ENTRY_START=time.clock_gettime(time.CLOCK_MONOTONIC)
import argparse,hashlib,json,os,re,signal,shutil,subprocess,sys
from pathlib import Path
import inventory as engine,source_guard
HERE=Path(__file__).resolve().parent
BASE=HERE.parent;ROOT=BASE/'m2-intake'
FREE=53474836480
SLOTS={'result.json':1048576,'supervisor.json':1048576}
LIMITS={'compressed_bytes':247301311,'decoded_bytes':2000000000,'encountered_records':100000,'parsed_record_bytes':4000000,'worker_seconds':570,'external_seconds':600,'RSS_bytes':1000000000,'all_output_bytes':128000000,'SQLite_bytes':112000000,'metadata_bytes':16000000,'network_requests':0}

def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(path):return hashlib.sha256(source_guard.small(path)).hexdigest()
def size(path):return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())
def required(profile):
    paths={str(HERE/n) for n in ['pilot.py','inventory.py','source_guard.py','checks.py','profile.json','contract.json']}
    paths|=set(profile['runtime_pins'])|set(profile['provenance_metadata'])
    return paths

def verify(a):
    if sha(HERE/'profile.json')!=a.profile_sha256:raise ValueError('external_profile_pin')
    profile=json.loads(source_guard.small(HERE/'profile.json'))
    if profile['limits']!=LIMITS:raise ValueError('fixed_inventory_limits')
    if sha(HERE/'code-pins.json')!=a.code_pins_sha256:raise ValueError('external_codepins_pin')
    pins=json.loads(source_guard.small(HERE/'code-pins.json'))['SHA256']
    if set(pins)!=required(profile):raise ValueError('exact_required_inventory')
    if sum(Path(p).stat().st_size for p in pins)>8000000:raise ValueError('metadata_runtime8MB')
    for p,h in pins.items():
        if sha(p)!=h:raise ValueError('pinned_input_changed')
    if str(Path(sys.executable).resolve())!=profile['python']:raise ValueError('runtime')
    proof=json.loads(source_guard.small(profile['integrity_receipt']))
    if proof['status']!='PASS_EXACT_FIRST_SHARD_LOCAL_INTEGRITY_ONLY' or any(proof[k]!=profile['source'][k] for k in ['path','bytes','SHA256','stat']):raise ValueError('exact_first_shard_integrity')
    if profile['source']['bytes']!=247301311 or profile['source']['SHA256']!='67d1135ad65d3c1f2f4d88d44ad35d37a4e381cb518c1bd878e4d2c350c9ff21':raise ValueError('exact_publisher_first_shard')
    return profile,profile['source']

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
    if size(out)+extra>128000000 or shutil.disk_usage(ROOT).free<FREE+extra:raise ValueError('aggregate_output_or_free_floor')
    if custody is not None:custody()

def worker(a):
    owned=False;out=None;start=a.start;custody=None
    signal.signal(signal.SIGALRM,alarm)
    try:
        remaining=570-(clk()-start)
        if remaining<=0:raise TimeoutError('expired_before_preflight')
        signal.setitimer(signal.ITIMER_REAL,remaining)
        profile,binding=verify(a);out=Path(profile['output'])
        if os.getppid()!=a.supervisor_pid:raise ValueError('actual_parent_PID')
        wait_end=min(clk()+3,start+570)
        while not (out/'ownership.json').exists() and clk()<wait_end:time.sleep(.01)
        o=json.loads(source_guard.small(out/'ownership.json'))
        if o['worker_PID']!=os.getpid() or o['supervisor_PID']!=a.supervisor_pid or o['shared_start']!=start or o['profile_SHA256']!=a.profile_sha256 or o['codepins_SHA256']!=a.code_pins_sha256:raise ValueError('owned_worker_receipt')
        owned=True
        def check(extra=0):guard(out,start,570,extra,custody)
        try:
            with source_guard.opened(binding,check) as read:
                custody=read.assert_custody
                result=engine.run(profile,out,read,check)
        finally:custody=None
        verify(a);check()
        if source_guard.ident(Path(binding['path']).stat())!=binding['stat']:raise ValueError('postflight_source_stat')
        result.update({'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256,'elapsed_shared_seconds':clk()-start,'artifacts':{'frame.sqlite':{'bytes':(out/'frame.sqlite').stat().st_size,'SHA256':hashlib.sha256((out/'frame.sqlite').read_bytes()).hexdigest()}}})
        terminal(out,'result.json',result)
    except BaseException as e:
        if owned:terminal(out,'result.json',{'status':'PARTIAL_FIRST_SHARD_INVENTORY_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'partial':getattr(e,'inventory_partial',None),'elapsed_shared_seconds':clk()-start,'new_admitted_documents':0})
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)

def supervise(a):
    start=ENTRY_START;child=None;created=False;out=None;old={};peak=0
    try:
        for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[sig]=signal.signal(sig,alarm)
        remaining=600-(clk()-start)
        if remaining<=0:raise TimeoutError('expired_before_supervisor_preflight')
        signal.setitimer(signal.ITIMER_REAL,remaining)
        profile,binding=verify(a);out=Path(profile['output'])
        if out.exists() or out.is_symlink():raise ValueError('once_only_output')
        if size(ROOT)+128000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+128000000:raise ValueError('combined_intake_and_free_reserves')
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
            guard(out,start,600)
            ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
            rss=tree_rss(ps.stdout,os.getpid(),child.pid if child.poll() is None else None);peak=max(peak,rss)
            if rss>1000000000:raise ValueError('observed_process_tree_RSS_limit')
            time.sleep(.1)
        child.wait(timeout=3);guard(out,start,600)
        ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
        peak=max(peak,tree_rss(ps.stdout,os.getpid()))
        if peak>1000000000:raise ValueError('terminal_observed_RSS_limit')
        result=json.loads(source_guard.small(out/'result.json'))
        ok=child.returncode==0 and result.get('status')=='COMPLETE_FIRST_SHARD_METADATA_FRAME_NO_ADMISSION'
        terminal(out,'supervisor.json',{'status':'COMPLETE_FIRST_SHARD_METADATA_INVENTORY_NO_ADMISSION' if ok else 'PARTIAL_FIRST_SHARD_INVENTORY_NO_RETRY',
           'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,
           'result_SHA256':sha(out/'result.json'),'all_output_bytes':size(out),'new_admitted_documents':0})
        return 0 if ok else 1
    except BaseException as e:
        if child is not None:kill(child)
        if created:terminal(out,'supervisor.json',{'status':'PARTIAL_FIRST_SHARD_INVENTORY_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,'new_admitted_documents':0})
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
