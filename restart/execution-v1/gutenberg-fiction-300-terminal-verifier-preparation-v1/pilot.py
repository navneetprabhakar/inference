"""Once-only offline terminal-prefix calibration. No network or IntakeLedger."""
import time,signal
def early_alarm(*a):raise TimeoutError('shared_PG300verifier200sec')
signal.signal(signal.SIGALRM,early_alarm);signal.setitimer(signal.ITIMER_REAL,200)
ENTRY_START=time.clock_gettime(time.CLOCK_MONOTONIC)
import argparse,hashlib,json,os,re,signal,shutil,subprocess,sys
from pathlib import Path
import verify as engine,source_guard
HERE=Path(__file__).resolve().parent
BASE=HERE.parent;ROOT=BASE/'m2-intake'
FREE=53474836480
SLOTS={'result.json':1048576,'supervisor.json':1048576}
LIMITS={'worker_seconds': 180, 'external_seconds': 200, 'RSS_bytes': 1000000000, 'all_output_bytes': 16000000, 'source_output_bytes': 800000000, 'network_requests': 0}

def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(path):return hashlib.sha256(source_guard.small(path)).hexdigest()
from tree_size import census as size
def required(profile):
 return {str(HERE/n) for n in ['pilot.py','verify.py','core.py','artifacts.py','source_guard.py','tree_size.py','checks.py','lifecycle_checks.py','profile.json','contract.json','binding-template.json']}|set(profile['provenance_metadata'])
def verify(a):
 if sha(HERE/'profile.json')!=a.profile_sha256 or sha(HERE/'code-pins.json')!=a.code_pins_sha256:raise ValueError('external_verifier_registry_pins')
 p=json.loads(source_guard.small(HERE/'profile.json'));pins=json.loads(source_guard.small(HERE/'code-pins.json'))['SHA256']
 if set(pins)!=required(p) or p['limits']!=LIMITS:raise ValueError('exact_verifier_inventory_limits')
 for f,h in pins.items():
  if hash_file(f)!=h:raise ValueError('pinned_code_changed')
 if str(Path(sys.executable).resolve())!=p['python'] or len(p['records'])!=300:raise ValueError('runtime_exact300')
 if sha(p['producer_profile'])!=p['producer_profile_SHA256'] or sha(p['producer_registry'])!=p['producer_codepins_SHA256']:raise ValueError('frozen_producer_policy')
 if a.execute or a.worker:
  if not a.terminal_binding or not a.terminal_binding_sha256:raise ValueError('external_COMPLETE_reaped_binding_required')
  engine.gate(p,a.terminal_binding,a.terminal_binding_sha256)
  p['terminal_binding_path']=a.terminal_binding;p['terminal_binding_SHA256']=a.terminal_binding_sha256
 return p

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
def hash_file(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
LAST_RESOURCE=0.
LAST_COMBINED=0.
def guard(out,start,seconds,extra=0,custody=None):
    if clk()-start>=seconds:raise TimeoutError('shared_deadline')
    global LAST_RESOURCE,LAST_COMBINED
    if extra or clk()-LAST_RESOURCE>=.25:
        if size(out)+extra>16000000 or shutil.disk_usage(ROOT).free<FREE+extra:raise ValueError('aggregate_output_or_free_floor')
        LAST_RESOURCE=clk()
    if clk()-LAST_COMBINED>=5:
        if size(ROOT)>64000000000:raise ValueError('runtime_combined_intake64GB')
        LAST_COMBINED=clk()
    if custody is not None:custody()

def worker(a):
    owned=False;out=None;start=a.start;custody=None
    signal.signal(signal.SIGALRM,alarm);signal.signal(signal.SIGTERM,alarm);signal.signal(signal.SIGINT,alarm)
    try:
        remaining=180-(clk()-start)
        if remaining<=0:raise TimeoutError('expired_before_preflight')
        signal.setitimer(signal.ITIMER_REAL,remaining)
        profile=verify(a);out=Path(profile['output'])
        if os.getppid()!=a.supervisor_pid:raise ValueError('actual_parent_PID')
        wait_end=min(clk()+3,start+180)
        while not (out/'ownership.json').exists() and clk()<wait_end:time.sleep(.01)
        o=json.loads(source_guard.small(out/'ownership.json'))
        if o['worker_PID']!=os.getpid() or o['supervisor_PID']!=a.supervisor_pid or o['shared_start']!=start or o['profile_SHA256']!=a.profile_sha256 or o['codepins_SHA256']!=a.code_pins_sha256:raise ValueError('owned_worker_receipt')
        owned=True
        def check(extra=0):guard(out,start,180,extra,custody)
        result=engine.run(profile,out,check)
        verify(a);check()
        result.update({'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256,'elapsed_shared_seconds':clk()-start,'artifacts':{q.name:{'bytes':q.stat().st_size,'SHA256':hash_file(q)} for q in out.iterdir() if q.is_file() and q.name not in SLOTS}})
        terminal(out,'result.json',result)
    except BaseException as e:
        if owned:terminal(out,'result.json',{'status':'PARTIAL_PG300_VERIFIER_NO_CLEARANCE','error':type(e).__name__+':'+str(e)[:1500],'partial':getattr(e,'inventory_partial',None),'elapsed_shared_seconds':clk()-start,'new_admitted_documents':0})
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)

def supervise(a):
    start=ENTRY_START;child=None;created=False;out=None;old={};peak=0
    try:
        for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[sig]=signal.signal(sig,alarm)
        remaining=190-(clk()-start)
        if remaining<=0:raise TimeoutError('expired_before_supervisor_preflight')
        signal.setitimer(signal.ITIMER_REAL,remaining)
        profile=verify(a);out=Path(profile['output'])
        if out.exists() or out.is_symlink():raise ValueError('once_only_output')
        if size(ROOT)+16000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+16000000:raise ValueError('combined_intake_and_free_reserves')
        out.mkdir();created=True
        for n,c in SLOTS.items():(out/n).write_bytes(b' '*c)
        child=subprocess.Popen([sys.executable,'-B',str(HERE/'pilot.py'),'--worker','--start',str(start),
          '--supervisor-pid',str(os.getpid()),'--profile-sha256',a.profile_sha256,
          '--code-pins-sha256',a.code_pins_sha256,'--terminal-binding',a.terminal_binding,'--terminal-binding-sha256',a.terminal_binding_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        owner={'worker_PID':child.pid,'supervisor_PID':os.getpid(),'shared_start':start,
               'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256}
        b=(json.dumps(owner)+'\n').encode()
        with (out/'ownership.json').open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
        while child.poll() is None:
            guard(out,start,190)
            ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
            rss=tree_rss(ps.stdout,os.getpid(),child.pid if child.poll() is None else None);peak=max(peak,rss)
            if rss>1000000000:raise ValueError('observed_process_tree_RSS_limit')
            time.sleep(.1)
        child.wait(timeout=3);guard(out,start,190)
        ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
        peak=max(peak,tree_rss(ps.stdout,os.getpid()))
        if peak>1000000000:raise ValueError('terminal_observed_RSS_limit')
        result=json.loads(source_guard.small(out/'result.json'))
        ok=child.returncode==0 and result.get('status')=='PASS_COMPLETE_FINITE_PG300_RAW_DISCOVERY_TERMINAL_VERIFICATION_NO_ADMISSION'
        terminal(out,'supervisor.json',{'status':'COMPLETE_PG300_TERMINAL_VERIFIER_NO_ADMISSION' if ok else 'PARTIAL_PG300_VERIFIER_NO_CLEARANCE',
           'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,
           'result_SHA256':sha(out/'result.json'),'all_output_bytes':size(out),'new_admitted_documents':0})
        return 0 if ok else 1
    except BaseException as e:
        signal.setitimer(signal.ITIMER_REAL,max(.001,start+200-clk()))
        if child is not None:kill(child)
        if created:terminal(out,'supervisor.json',{'status':'PARTIAL_PG300_VERIFIER_NO_CLEARANCE','error':type(e).__name__+':'+str(e)[:1500],'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,'new_admitted_documents':0})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for sig,h in old.items():signal.signal(sig,h)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true')
    parser.add_argument('--profile-sha256',required=True);parser.add_argument('--code-pins-sha256',required=True)
    parser.add_argument('--terminal-binding');parser.add_argument('--terminal-binding-sha256');parser.add_argument('--start',type=float);parser.add_argument('--supervisor-pid',type=int);a=parser.parse_args()
    if a.worker:worker(a)
    elif a.execute:raise SystemExit(supervise(a))
    else:verify(a);print('PREPARATION_ONLY_NO_NATIVE_READ_OR_EXECUTION')
