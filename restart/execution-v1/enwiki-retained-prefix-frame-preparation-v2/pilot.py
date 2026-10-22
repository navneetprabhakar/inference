"""Once-only offline terminal-prefix calibration. No network or IntakeLedger."""
import time
ENTRY_START=time.clock_gettime(time.CLOCK_MONOTONIC)
import argparse,hashlib,json,os,re,signal,shutil,subprocess,sys
from pathlib import Path
import engine,source_guard,index_reader
from tree_size import census as size
HERE=Path(__file__).resolve().parent
BASE=HERE.parent;ROOT=BASE/'m2-intake'
FREE=53474836480
SLOTS={'result.json':1048576,'supervisor.json':1048576}
LIMITS={'compressed_bytes':17988779480,'decoded_bytes':100000000000,'worker_seconds':21600,
 'external_seconds':21900,'RSS_bytes':1000000000,'all_output_bytes':3000000000,
 'metadata_bytes':256000000,'DB_bytes':2000000000,'revision_occurrences':30000000,
 'max_group_compressed_bytes':4078038,'network_requests':0}

def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(path):return hashlib.sha256(source_guard.small(path)).hexdigest()
def required(profile):
    paths={str(HERE/n) for n in ['pilot.py','engine.py','codec.py','source_guard.py','checks.py','tree_size.py','index_reader.py','measurement.json','capacity.json','profile.json','contract.json']}
    paths|={profile[k] for k in ['semantic_module','sink_module','span_helper','parent_scope_path','title_decoder','title_decoder_contract']}
    paths|={x['path'] for x in profile['source']['chain'].values()}
    paths|=set(profile['runtime_pins'])
    paths|=set(profile['title_proof_receipts'])|set(profile['preserved_prior_failure_receipts'])|set(profile['title_decoder_audits'])
    paths|=set(profile['inherited_metadata_receipts'])
    return paths
def verify(a):
    ppath=HERE/'profile.json'
    if sha(ppath)!=a.profile_sha256:raise ValueError('external_profile_pin')
    profile=json.loads(source_guard.small(ppath))
    if profile['limits']!=LIMITS:raise ValueError('fixed_calibration_limits')
    if hashlib.sha256(json.dumps(profile['source'],sort_keys=True,separators=(',',':')).encode()).hexdigest()!=profile['source_binding_canonical_SHA256']:raise ValueError('source_binding_section_digest')
    if sha(HERE/'code-pins.json')!=a.code_pins_sha256:raise ValueError('external_codepins_pin')
    pins=json.loads(source_guard.small(HERE/'code-pins.json'))['SHA256']
    if set(pins)!=required(profile):raise ValueError('exact_required_inventory')
    if sum(Path(p).stat().st_size for p in pins)>8000000:raise ValueError('frozen_metadata_runtime_total8MB')
    for p,d in pins.items():
        if sha(p)!=d:raise ValueError('code_runtime_metadata_pin_changed:'+p)
    if str(Path(sys.executable).resolve())!=profile['python']:raise ValueError('actual_runtime_path')
    selection=profile['selection']
    if selection!={'rows':15840694,'groups':158433,'header_bytes':570,'compressed_prefix_end_exclusive':17988779480,'require_next_group_outside_prefix':True}:raise ValueError('exact_retained_prefix_subset')
    index=profile['index'];p=Path(index['path'])
    if p.is_symlink() or str(p.resolve())!=str(p) or index_reader.identity(p.stat())!=index['stat'] or p.stat().st_size!=2579058688 or index['SHA256']!='b3da13e0080303b5500cb98501e2396ce38fe634369f9f9937c36e3243a6936e':raise ValueError('inherited_verified_index_stat_binding')
    proof=json.loads(source_guard.small(profile['index_verification']))
    if proof['status']!='COMPLETE_INDEPENDENT_INDEX_IDENTITY_METADATA_VERIFICATION_NO_ADMISSION' or proof['SQLite_SHA256_independently_rehashed']!=index['SHA256'] or not proof['global_index_page_ID_uniqueness_proven']:raise ValueError('independent_index_unique_proof')
    proof=json.loads(source_guard.small(profile['title_proof_receipts'][0]))
    if proof.get('status')!='COMPLETE_GROUP23_IDENTITY_DIAGNOSTIC_NO_ADMISSION' or proof.get('observed_pages')!=100 or proof.get('raw_index_title_mismatches')!=1:raise ValueError('actual_group23_diagnostic_proof')
    mismatch=[r for r in proof['observed'] if not r['titles_literal_equal']]
    if len(mismatch)!=1 or mismatch[0]['expected_global_ordinal']!=2240 or mismatch[0]['native_page_ID']!=3914 or mismatch[0]['native_title']!='British & Irish Lions' or mismatch[0]['raw_index_title_lexeme']!='British &amp; Irish Lions':raise ValueError('actual_diagnostic_exact_mismatch')
    binding=source_guard.verify(profile)
    return profile,binding

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
    current=size(out);remaining=max(0,LIMITS['all_output_bytes']-current)
    if extra<0 or current+extra>LIMITS['all_output_bytes'] or shutil.disk_usage(ROOT).free<FREE+remaining or size(ROOT)+remaining>64000000000:raise ValueError('aggregate_output_combined64GB_or_protected_floor')
    if custody is not None:custody()

def stream_sha(path,check):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while True:
            b=f.read(1048576)
            if not b:break
            h.update(b);check()
    return h.hexdigest()

def worker(a):
    owned=False;out=None;start=a.start;custody=None
    signal.signal(signal.SIGALRM,alarm)
    try:
        remaining=21600-(clk()-start)
        if remaining<=0:raise TimeoutError('expired_before_preflight')
        signal.setitimer(signal.ITIMER_REAL,remaining)
        profile,binding=verify(a);out=Path(profile['output'])
        if os.getppid()!=a.supervisor_pid:raise ValueError('actual_parent_PID')
        # Ownership is written by parent immediately after Popen. Wait bounded
        # only for that exact receipt; never source-read before identity proves.
        wait_end=min(clk()+3,start+21600)
        while not (out/'ownership.json').exists() and clk()<wait_end:time.sleep(.01)
        o=json.loads(source_guard.small(out/'ownership.json'))
        if o['worker_PID']!=os.getpid() or o['supervisor_PID']!=a.supervisor_pid or o['shared_start']!=start or o['profile_SHA256']!=a.profile_sha256 or o['codepins_SHA256']!=a.code_pins_sha256:raise ValueError('owned_worker_receipt')
        owned=True
        last_full=[0.0]
        def check(extra=0,force=False):
            if clk()-start>=21600:raise TimeoutError('shared_worker_deadline')
            # File sizes are independently hard-bounded by SQLite and Evidence;
            # full disk/stat custody checks recur at most1second and everycommit.
            now=clk()
            if force or extra or now-last_full[0]>=1:
                guard(out,start,21600,extra,custody);last_full[0]=now
        try:
            with source_guard.opened(binding,check) as read_at:
                with index_reader.opened(profile,check) as groups:
                    def custody_both():read_at.assert_custody();groups.assert_custody()
                    custody=custody_both
                    result=engine.run(profile,groups,read_at,out,check)
        finally:
            custody=None
        source_guard.verify(profile);verify(a);check()
        if source_guard.ident(Path(binding['path']).stat())!=binding['stat']:raise ValueError('postflight_source_path_stat')
        result.update({'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256,
            'source_prefix_SHA256_inherited':binding['SHA256'],'source_trust_class':'TLS_ETAG_TERMINAL_LOCALPREFIX_FRESHHASH_STAT_CRC_INDEX',
            'whole_publisher_archive_verified':False,'additional_whole_prefix_rehash_bytes':0,
            'elapsed_shared_seconds':clk()-start})
        result['artifacts']={p.name:{'bytes':p.stat().st_size,'SHA256':stream_sha(p,check)} for p in out.iterdir() if p.name not in SLOTS and p.is_file()}
        terminal(out,'result.json',result)
    except BaseException as e:
        if owned:terminal(out,'result.json',{'status':'PARTIAL_RETAINED_PREFIX_FRAME_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'elapsed_shared_seconds':clk()-start,'new_admitted_documents':0})
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)

def supervise(a):
    start=ENTRY_START;child=None;created=False;out=None;old={};peak=0
    try:
        for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[sig]=signal.signal(sig,alarm)
        remaining=21895-(clk()-start)
        if remaining<=0:raise TimeoutError('expired_before_supervisor_preflight')
        signal.setitimer(signal.ITIMER_REAL,remaining)
        profile,binding=verify(a);out=Path(profile['output'])
        if out.exists() or out.is_symlink():raise ValueError('once_only_output')
        if size(ROOT)+3000000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+3000000000:raise ValueError('combined_intake_and_free_reserves')
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
            guard(out,start,21900)
            ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
            rss=tree_rss(ps.stdout,os.getpid(),child.pid if child.poll() is None else None);peak=max(peak,rss)
            if rss>1000000000:raise ValueError('observed_process_tree_RSS_limit')
            time.sleep(1)
        child.wait(timeout=3);guard(out,start,21900)
        result=json.loads(source_guard.small(out/'result.json'))
        ok=child.returncode==0 and result.get('status')=='COMPLETE_RETAINED_PREFIX_FRAGMENT_FRAME_NO_ADMISSION'
        terminal(out,'supervisor.json',{'status':'COMPLETE_RETAINED_PREFIX_FRAGMENT_NO_ADMISSION' if ok else 'PARTIAL_RETAINED_PREFIX_FRAME_NO_RETRY',
           'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,
           'result_SHA256':sha(out/'result.json'),'all_output_bytes':size(out),'new_admitted_documents':0})
        return 0 if ok else 1
    except BaseException as e:
        signal.setitimer(signal.ITIMER_REAL,max(.001,start+21900-clk()))
        if child is not None:kill(child)
        if created:terminal(out,'supervisor.json',{'status':'PARTIAL_RETAINED_PREFIX_FRAME_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,'new_admitted_documents':0})
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
