"""Once-only offline terminal-prefix calibration. No network or IntakeLedger."""
import time
ENTRY_START=time.clock_gettime(time.CLOCK_MONOTONIC)
import argparse,hashlib,json,os,re,signal,shutil,subprocess,sys
from pathlib import Path
import engine,source_guard
HERE=Path(__file__).resolve().parent
BASE=HERE.parent;ROOT=BASE/'m2-intake'
FREE=53474836480
SLOTS={'result.json':1048576,'supervisor.json':1048576}
LIMITS={'compressed_bytes':150857439,'decoded_bytes':2000000000,'worker_seconds':570,
 'external_seconds':600,'RSS_bytes':1000000000,'all_output_bytes':64000000,
 'metadata_bytes':8000000,'DB_bytes':48000000,'revision_occurrences':30000000,
 'max_group_compressed_bytes':1802826,'network_requests':0}

def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(path):return hashlib.sha256(source_guard.small(path)).hexdigest()
def size(path):return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())
def required(profile):
    paths={str(HERE/n) for n in ['pilot.py','engine.py','codec.py','source_guard.py','checks.py','profile.json','contract.json']}
    paths|={profile[k] for k in ['semantic_module','sink_module','span_helper','selection_path','rows_path','parent_scope_path','title_decoder','title_decoder_contract']}
    paths|={x['path'] for x in profile['source']['chain'].values()}
    paths|=set(profile['runtime_pins'])
    paths|=set(profile['title_proof_receipts'])|set(profile['preserved_prior_failure_receipts'])|set(profile['title_decoder_audits'])
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
    selection=json.loads(source_guard.small(profile['selection_path']))
    raw=source_guard.small(profile['rows_path']);rows=[json.loads(line) for line in raw.splitlines()]
    if len(rows)!=12800 or selection['rows']!=12800 or len(selection['groups'])!=128 or selection['compressed_prefix_end_exclusive']!=150857439:raise ValueError('fixed128_selection')
    previous=570
    for i,g in enumerate(selection['groups'],1):
        if g['group_ordinal']!=i or g['compressed_start']!=previous or g['compressed_end_exclusive']-previous!=g['compressed_bytes'] or not 0<g['compressed_bytes']<=1802826 or g['first_row_ordinal']!=(i-1)*100+1 or g['last_row_ordinal']!=i*100 or g['index_rows']!=100:raise ValueError('fixed_group_partition')
        previous=g['compressed_end_exclusive']
        for row in rows[g['first_row_ordinal']-1:g['last_row_ordinal']]:
            ordinal,group,pid,title,h,n,ends,text=row
            b=text.encode('utf8')
            if group!=i or ordinal<g['first_row_ordinal'] or ordinal>g['last_row_ordinal'] or len(b)!=n or hashlib.sha256(b).hexdigest()!=h or ends!=int(b.endswith(b'\n')):raise ValueError('raw_frozen_index_line')
            fields=b.rstrip(b'\n').split(b':',2)
            if [int(fields[0]),int(fields[1]),fields[2].decode('utf8')]!=[g['compressed_start'],pid,title]:raise ValueError('exact_index_identity_metadata')
    if [r[0] for r in rows]!=list(range(1,12801)) or previous!=150857439:raise ValueError('all_row_ordinals')
    proof=json.loads(source_guard.small(profile['title_proof_receipts'][0]))
    if proof.get('status')!='COMPLETE_GROUP23_IDENTITY_DIAGNOSTIC_NO_ADMISSION' or proof.get('observed_pages')!=100 or proof.get('raw_index_title_mismatches')!=1:raise ValueError('actual_group23_diagnostic_proof')
    mismatch=[r for r in proof['observed'] if not r['titles_literal_equal']]
    if len(mismatch)!=1 or mismatch[0]['expected_global_ordinal']!=2240 or mismatch[0]['native_page_ID']!=3914 or mismatch[0]['native_title']!='British & Irish Lions' or mismatch[0]['raw_index_title_lexeme']!='British &amp; Irish Lions':raise ValueError('actual_diagnostic_exact_mismatch')
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
    if size(out)+extra>64000000 or shutil.disk_usage(ROOT).free<FREE+extra:raise ValueError('aggregate_output_or_free_floor')
    if custody is not None:custody()

def worker(a):
    owned=False;out=None;start=a.start;custody=None
    signal.signal(signal.SIGALRM,alarm)
    try:
        remaining=570-(clk()-start)
        if remaining<=0:raise TimeoutError('expired_before_preflight')
        signal.setitimer(signal.ITIMER_REAL,remaining)
        profile,selection,rows,binding=verify(a);out=Path(profile['output'])
        if os.getppid()!=a.supervisor_pid:raise ValueError('actual_parent_PID')
        # Ownership is written by parent immediately after Popen. Wait bounded
        # only for that exact receipt; never source-read before identity proves.
        wait_end=min(clk()+3,start+570)
        while not (out/'ownership.json').exists() and clk()<wait_end:time.sleep(.01)
        o=json.loads(source_guard.small(out/'ownership.json'))
        if o['worker_PID']!=os.getpid() or o['supervisor_PID']!=a.supervisor_pid or o['shared_start']!=start or o['profile_SHA256']!=a.profile_sha256 or o['codepins_SHA256']!=a.code_pins_sha256:raise ValueError('owned_worker_receipt')
        owned=True
        def check(extra=0):guard(out,start,570,extra,custody)
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
        remaining=600-(clk()-start)
        if remaining<=0:raise TimeoutError('expired_before_supervisor_preflight')
        signal.setitimer(signal.ITIMER_REAL,remaining)
        profile,selection,rows,binding=verify(a);out=Path(profile['output'])
        if out.exists() or out.is_symlink():raise ValueError('once_only_output')
        if size(ROOT)+64000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+64000000:raise ValueError('combined_intake_and_free_reserves')
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
        result=json.loads(source_guard.small(out/'result.json'))
        ok=child.returncode==0 and result.get('status')=='COMPLETE_FIRST128_TERMINAL_PREFIX_CALIBRATION_NO_ADMISSION'
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
