"""Once-only offline terminal-prefix calibration. No network or IntakeLedger."""
import time,signal
def early_alarm(*a):raise TimeoutError('shared_capture300sec')
signal.signal(signal.SIGALRM,early_alarm);signal.setitimer(signal.ITIMER_REAL,300)
ENTRY_START=time.clock_gettime(time.CLOCK_MONOTONIC)
import argparse,hashlib,json,os,re,signal,shutil,subprocess,sys
from pathlib import Path
import capture as engine,source_guard
HERE=Path(__file__).resolve().parent
BASE=HERE.parent;ROOT=BASE/'m2-intake'
FREE=53474836480
SLOTS={'result.json':1048576,'supervisor.json':1048576}
LIMITS={'worker_seconds': 285, 'external_seconds': 300, 'RSS_bytes': 1000000000, 'all_output_bytes': 100000000, 'decoded_bytes_per_file': 2000000000, 'record_bytes': 981231, 'text_bytes_per_record': 976482, 'selected_text_bytes': 30000000, 'records_per_source': 100000, 'network_requests': 0}

def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(path):return hashlib.sha256(source_guard.small(path)).hexdigest()
from tree_size import census as size
def required(profile):
 paths={str(HERE/n) for n in ['pilot.py','capture.py','inventory.py','stream_core.py','source_guard.py','checks.py','core_checks.py','profile.json','tree_size.py','selection.json','select_core.py','select_metadata.py']}
 return paths|set(profile['runtime_pins'])|set(profile['provenance_metadata'])
def verify(a):
 if sha(HERE/'profile.json')!=a.profile_sha256 or sha(HERE/'code-pins.json')!=a.code_pins_sha256:raise ValueError('external_profile_registry_pins')
 p=json.loads(source_guard.small(HERE/'profile.json'));pins=json.loads(source_guard.small(HERE/'code-pins.json'))['SHA256']
 if set(pins)!=required(p) or p['limits']!=LIMITS:raise ValueError('exact_inventory_fixed_limits')
 for f,h in pins.items():
  if sha(f)!=h:raise ValueError('input_code_pin')
 if str(Path(sys.executable).resolve())!=p['python']:raise ValueError('actual_runtime')
 for item in p['sources']:
  for binding in [item['raw'],item['frame']]:
   q=Path(binding['path'])
   if q.is_symlink() or str(q.resolve())!=str(q) or source_guard.ident(q.stat())!=binding['stat']:raise ValueError('source_frame_stat_custody')
   if 'inherited_SHA256' in binding and hash_file(q)!=binding['inherited_SHA256']:raise ValueError('metadata_frame_hash')
 q=Path(p['selection_frame']['path'])
 if q.is_symlink() or source_guard.ident(q.stat())!=p['selection_frame']['stat'] or hash_file(q)!=p['selection_frame']['inherited_SHA256']:raise ValueError('selection_frame_stat_hash_custody')
 sel=json.loads(source_guard.small(p['selection']));
 if sel['population_distinct_textSHA']!=15799 or len(sel['draws'])!=30 or sel['capture_distinct_textSHA']!=30 or sum(r['text_UTF8_bytes'] for r in sel['selected_capture_occurrences'])!=p['planned_capture_text_bytes']:raise ValueError('fixed_draw_metadata')
 if p['planned_capture_text_bytes']>30000000 or p['planned_capture_text_bytes']+p['planned_capture_raw_line_bytes']+2097152>100000000 or sel['removed_exact_semantic_hold_textSHA']!=['1ac03f93f6b77284ceb6e8ba36420e39f8d0157e2f6dd30515df6c3b7cb4a77d']:raise ValueError('fixed_selected_text_raw_capacity_or_knownhold')
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
def guard(out,start,seconds,extra=0,custody=None):
    if clk()-start>=seconds:raise TimeoutError('shared_deadline')
    global LAST_RESOURCE
    if extra or clk()-LAST_RESOURCE>=.25:
        if size(out)+extra>100000000 or shutil.disk_usage(ROOT).free<FREE+extra:raise ValueError('aggregate_output_or_free_floor')
        LAST_RESOURCE=clk()
    if custody is not None:custody()

def worker(a):
    owned=False;out=None;start=a.start;custody=None
    signal.signal(signal.SIGALRM,alarm);signal.signal(signal.SIGTERM,alarm);signal.signal(signal.SIGINT,alarm)
    try:
        remaining=285-(clk()-start)
        if remaining<=0:raise TimeoutError('expired_before_preflight')
        signal.setitimer(signal.ITIMER_REAL,remaining)
        profile=verify(a);out=Path(profile['output'])
        if os.getppid()!=a.supervisor_pid:raise ValueError('actual_parent_PID')
        wait_end=min(clk()+3,start+285)
        while not (out/'ownership.json').exists() and clk()<wait_end:time.sleep(.01)
        o=json.loads(source_guard.small(out/'ownership.json'))
        if o['worker_PID']!=os.getpid() or o['supervisor_PID']!=a.supervisor_pid or o['shared_start']!=start or o['profile_SHA256']!=a.profile_sha256 or o['codepins_SHA256']!=a.code_pins_sha256:raise ValueError('owned_worker_receipt')
        owned=True
        def check(extra=0):guard(out,start,285,extra,custody)
        result=engine.run(profile,out,check)
        verify(a);check()
        result.update({'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256,'elapsed_shared_seconds':clk()-start,'artifacts':{q.name:{'bytes':q.stat().st_size,'SHA256':hash_file(q)} for q in out.iterdir() if q.is_file() and q.name not in SLOTS}})
        terminal(out,'result.json',result)
    except BaseException as e:
        if owned:terminal(out,'result.json',{'status':'PARTIAL_FIXED_DRAW_CAPTURE_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'partial':getattr(e,'inventory_partial',None),'elapsed_shared_seconds':clk()-start,'new_admitted_documents':0})
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)

def supervise(a):
    start=ENTRY_START;child=None;created=False;out=None;old={};peak=0
    try:
        for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[sig]=signal.signal(sig,alarm)
        remaining=295-(clk()-start)
        if remaining<=0:raise TimeoutError('expired_before_supervisor_preflight')
        signal.setitimer(signal.ITIMER_REAL,remaining)
        profile=verify(a);out=Path(profile['output'])
        if out.exists() or out.is_symlink():raise ValueError('once_only_output')
        if size(ROOT)+100000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+100000000:raise ValueError('combined_intake_and_free_reserves')
        out.mkdir();created=True
        for n,c in SLOTS.items():(out/n).write_bytes(b' '*c)
        child=subprocess.Popen([sys.executable,'-B',str(HERE/'pilot.py'),'--worker','--start',str(start),
          '--supervisor-pid',str(os.getpid()),'--profile-sha256',a.profile_sha256,
          '--code-pins-sha256',a.code_pins_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        owner={'worker_PID':child.pid,'supervisor_PID':os.getpid(),'shared_start':start,
               'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256}
        b=(json.dumps(owner)+'\n').encode()
        with (out/'ownership.json').open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
        while child.poll() is None:
            guard(out,start,295)
            ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
            rss=tree_rss(ps.stdout,os.getpid(),child.pid if child.poll() is None else None);peak=max(peak,rss)
            if rss>1000000000:raise ValueError('observed_process_tree_RSS_limit')
            time.sleep(.1)
        child.wait(timeout=3);guard(out,start,295)
        ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
        peak=max(peak,tree_rss(ps.stdout,os.getpid()))
        if peak>1000000000:raise ValueError('terminal_observed_RSS_limit')
        result=json.loads(source_guard.small(out/'result.json'))
        ok=child.returncode==0 and result.get('status')=='COMPLETE_FIXED30_DRAW_WHOLE_HANSARD_DEVELOPMENT_CAPTURE_NO_ADMISSION'
        terminal(out,'supervisor.json',{'status':'COMPLETE_FIXED_DRAW_PRESSBOOKS_CAPTURE_NO_ADMISSION' if ok else 'PARTIAL_FIXED_DRAW_CAPTURE_NO_RETRY',
           'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,
           'result_SHA256':sha(out/'result.json'),'all_output_bytes':size(out),'new_admitted_documents':0})
        return 0 if ok else 1
    except BaseException as e:
        signal.setitimer(signal.ITIMER_REAL,max(.001,start+300-clk()))
        if child is not None:kill(child)
        if created:terminal(out,'supervisor.json',{'status':'PARTIAL_FIXED_DRAW_CAPTURE_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,'new_admitted_documents':0})
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
