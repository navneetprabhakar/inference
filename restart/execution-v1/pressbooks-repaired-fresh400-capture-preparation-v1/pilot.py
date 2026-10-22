"""Once-only offline terminal-prefix calibration. No network or IntakeLedger."""
import time,signal
def early_alarm(*a):raise TimeoutError('shared_fresh400capture300sec')
signal.signal(signal.SIGALRM,early_alarm);signal.setitimer(signal.ITIMER_REAL,300)
ENTRY_START=time.clock_gettime(time.CLOCK_MONOTONIC)
import argparse,hashlib,json,os,re,signal,shutil,subprocess,sys
from pathlib import Path
import capture as engine,source_guard,adapter
HERE=Path(__file__).resolve().parent
BASE=HERE.parent;ROOT=BASE/'m2-intake'
FREE=53474836480
SLOTS={'result.json':1048576,'supervisor.json':1048576}
LIMITS={'worker_seconds': 285, 'external_seconds': 300, 'RSS_bytes': 1000000000, 'all_output_bytes': 128000000, 'decoded_bytes_per_file': 2000000000, 'record_bytes': 4000000, 'text_bytes_per_record': 2196000, 'records_per_source': 100000, 'network_requests': 0}

def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(path):return hashlib.sha256(source_guard.small(path)).hexdigest()
from tree_size import census as size
def required(profile):
 return {str(HERE/n) for n in ['pilot.py','capture.py','retained_capture.py','adapter.py','bind_terminal_metadata.py','source_guard.py','inventory.py','tree_size.py','checks.py','lifecycle_checks.py','focused_checks.py','profile.json','contract.json','selection.json','metadata-binding.json']}|set(profile['runtime_pins'])|set(profile['provenance_metadata'])
def verify(a):
 if sha(HERE/'profile.json')!=a.profile_sha256 or sha(HERE/'code-pins.json')!=a.code_pins_sha256:raise ValueError('external_profile_registry_pins')
 p=json.loads(source_guard.small(HERE/'profile.json'));pins=json.loads(source_guard.small(HERE/'code-pins.json'))['SHA256']
 if set(pins)!=required(p) or p['limits']!=LIMITS:raise ValueError('exact_inventory_fixed_limits')
 for f,h in pins.items():
  if sha(f)!=h:raise ValueError('input_code_pin')
 if str(Path(sys.executable).resolve())!=p['python']:raise ValueError('actual_runtime')
 for source in p['sources']:
  for item in [source['raw'],source['frame']]:
   q=Path(item['path'])
   if q.is_symlink() or str(q.resolve())!=str(q) or source_guard.ident(q.stat())!=item['stat']:raise ValueError('original_source_frame_stat')
  if hash_file(source['frame']['path'])!=source['frame']['inherited_SHA256']:raise ValueError('original_metadata_frame_hash')
 b=p['candidate_frame'];q=Path(b['path'])
 if q.is_symlink() or source_guard.ident(q.stat())!=b['stat'] or hash_file(q)!=b['inherited_verified_SHA256']:raise ValueError('verified_candidate_metadata_stat_hash')
 proof=json.loads(source_guard.small(p['independent_terminal_proof']));binding=json.loads(source_guard.small(p['producer_binding']))
 if proof['status']!='ROOT_REAPED0_COMPLETE_INDEPENDENT_STORED_PB_REPAIRED_COUNT_PROOF_NO_ADMISSION' or proof['verifier_exit_code']!=0 or proof['verifier_owned_PIDs_absent'] is not True or proof['producer_exec15331_reaped0'] is not True or binding['producer_reaped'] is not True or binding['producer_exec_exit']!=0 or binding['producer_owners_absent'] is not True:raise ValueError('complete_repaired_count_proofs')
 terminalproof=json.loads(source_guard.small(p['selection_terminal_parent_proof']))
 if terminalproof['status']!='ROOT_REAPED0_INDEPENDENT_FULLFRAME_UNIFORM_AND_WEIGHTED_DRAW_RECOMPUTATION_NO_BODY_READ' or terminalproof['producer_exit_code']!=0 or terminalproof['owned_PIDs_absent'] is not True:raise ValueError('independent_draw_complete_reaped')
 original=Path(p['selection_terminal_parent_proof']).parent.parent/'m2-intake/pressbooks-repaired-clear-fresh400-selection-v1'
 for name,key in [('result.json','result_SHA256'),('fresh-review-selection.json','selection_SHA256'),('capture-selection.json','capture_selection_SHA256')]:
  if sha(original/name)!=terminalproof[key]:raise ValueError('terminal_selection_proof_hash')
 owner=json.loads(source_guard.small(original/'ownership.json'))
 for pid in [owner['worker_PID'],owner['supervisor_PID']]:
  x=subprocess.run(['/bin/ps','-p',str(pid),'-o','pid='],capture_output=True,text=True,timeout=1)
  if x.returncode not in [0,1] or x.stdout.strip():raise ValueError('selection_owner_PID_not_absent')
 if sha(p['selection'])!=terminalproof['capture_selection_SHA256']:raise ValueError('exact_approved_capture_selection')
 sel=json.loads(source_guard.small(p['selection']));stats=adapter.verify_derived(sel)
 if stats!=p['stats'] or stats['unique_raw_SHA']!=391 or stats['text_UTF8_bytes']!=10755436 or stats['original_JSON_bytes']!=11227434 or stats['max_text_UTF8_bytes']!=958137:raise ValueError('actual391_capture_costs')
 if stats['text_UTF8_bytes']+stats['original_JSON_bytes']+16000000>128000000:raise ValueError('capture_cost_bound_no_reroll')

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
        if size(out)+extra>128000000 or shutil.disk_usage(ROOT).free<FREE+extra:raise ValueError('aggregate_output_or_free_floor')
        LAST_RESOURCE=clk()
    if clk()-LAST_COMBINED>=5:
        if size(ROOT)>64000000000:raise ValueError('runtime_combined_intake64GB')
        LAST_COMBINED=clk()
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
        if owned:terminal(out,'result.json',{'status':'PARTIAL_FRESH400_WHOLE_CAPTURE_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'partial':getattr(e,'inventory_partial',None),'elapsed_shared_seconds':clk()-start,'new_admitted_documents':0})
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
        if size(ROOT)+128000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+128000000:raise ValueError('combined_intake_and_free_reserves')
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
        ok=child.returncode==0 and result.get('status')=='COMPLETE_FRESH400_DRAW_WHOLE_ORIGINAL_PRESSBOOKS_CAPTURE_NO_ADMISSION'
        terminal(out,'supervisor.json',{'status':'COMPLETE_FRESH400_WHOLE_CAPTURE_NO_ADMISSION' if ok else 'PARTIAL_FRESH400_WHOLE_CAPTURE_NO_RETRY',
           'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,
           'result_SHA256':sha(out/'result.json'),'all_output_bytes':size(out),'new_admitted_documents':0})
        return 0 if ok else 1
    except BaseException as e:
        signal.setitimer(signal.ITIMER_REAL,max(.001,start+300-clk()))
        if child is not None:kill(child)
        if created:terminal(out,'supervisor.json',{'status':'PARTIAL_FRESH400_WHOLE_CAPTURE_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,'new_admitted_documents':0})
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
