"""Exactly four fixed canonical shards with independent and joint observers.

Prepared for parent review. No execution on import; no retries or refunds.
"""
import argparse,hashlib,json,os,re,signal,subprocess,sys,time
from pathlib import Path

HERE=Path(__file__).resolve().parent
SHARDS=HERE.parent/'wikibooks-sharded-render-preparation-v2'
sys.path.insert(0,str(SHARDS))
import aggregate
import reader_core as rc
from shared_clock import shared_clock
ROOT=aggregate.ROOT
ARCHIVE=rc.INTAKE_ROOT/'wikibooks-rendered-pilot-v1/enwikibooks-NS0-20250320-ENTERPRISE-HTML.json.tar.gz'
GLOBAL_SECONDS=930
GLOBAL_RSS=4_000_000_000
GLOBAL_CLEANUP_RESERVE_SECONDS=5

def parse_ps(value):
    out={}
    for line in value.splitlines():
        p=line.strip().split(None,9)
        if len(p)<10:continue
        try:pid,ppid,pgid,kib=map(int,p[:4])
        except ValueError:continue
        out[pid]={'pid':pid,'ppid':ppid,'pgid':pgid,'rss':kib*1024,'birth':' '.join(p[4:9]),'command':p[9]}
    return out

def snapshot():
    p=subprocess.run(['/bin/ps','-axo','pid=,ppid=,pgid=,rss=,lstart=,command='],capture_output=True,text=True,check=True,timeout=1)
    return parse_ps(p.stdout)

class Owned:
    def __init__(self,root_pid,supervisor_pids=(),root=ROOT,worker_script=SHARDS/'render_shard.py'):
        self.root_pid=root_pid;self.supervisor_pids=set(supervisor_pids);self.root=root;self.worker_script=str(worker_script.resolve());self.births={}
        self.last_rows={}
    def observe(self,ps):
        if self.root_pid not in ps:raise ValueError('joint_launcher_missing_from_snapshot')
        seeds={self.root_pid}|{pid for pid in self.supervisor_pids if pid in ps and (pid not in self.births or self.births[pid]==ps[pid]['birth'])}
        # Durable worker registrations cover separate sessions and reparenting.
        for shard in range(1,5):
            f=self.root/('shard-'+str(shard))/'process-ownership.json'
            if not f.exists():continue
            r=json.loads(f.read_text());pid=r.get('worker_pid');row=ps.get(pid)
            if r.get('supervisor_pid') in self.supervisor_pids and r.get('worker_script')==self.worker_script and r.get('output')==str(f.parent.resolve()) and row and self.worker_script in row['command'] and '--supervisor-pid '+str(r['supervisor_pid']) in row['command']:seeds.add(pid)
        # Closes the tiny spawn-before-registration window if a supervisor dies.
        for pid,row in ps.items():
            if self.worker_script in row['command'] and any('--supervisor-pid '+str(p)+' ' in row['command']+' ' for p in self.supervisor_pids) and str(self.root.resolve()) in row['command']:seeds.add(pid)
        for pid,birth in self.births.items():
            if pid in ps and ps[pid]['birth']==birth:seeds.add(pid)
        while True:
            expanded=seeds|{pid for pid,r in ps.items() if r['ppid'] in seeds}
            if expanded==seeds:break
            seeds=expanded
        for pid in seeds:self.births.setdefault(pid,ps[pid]['birth'])
        self.last_rows={pid:ps[pid] for pid in seeds if pid in ps and self.births.get(pid)==ps[pid]['birth']}
        return self.last_rows

def decision(elapsed,rss,output_bytes,free_bytes,intake_bytes):
    if elapsed>=GLOBAL_SECONDS-GLOBAL_CLEANUP_RESERVE_SECONDS:return 'global_wall_cap_cleanup_reserve'
    if rss>GLOBAL_RSS:return 'global4GB_observed_owned_tree_RSS_cap'
    if output_bytes>4*rc.CAPS['output_bytes']:return 'joint4GB_output_cap'
    if free_bytes<rc.FREE_RESERVE:return 'joint_disk_weights_free_floor'
    if intake_bytes>rc.PROCESSED_CEILING:return 'joint_combined_intake64GB_cap'
    return None

def stop_owned(tracker,processes,snapshot_fn=snapshot):
    """Kill leaf sessions first; allow supervisors to wait/reap their workers."""
    signals=[];own_group=os.getpgrp();observation_errors=[];cleanup_deadline=shared_clock()+GLOBAL_CLEANUP_RESERVE_SECONDS
    def observe():
        try:return tracker.observe(snapshot_fn())
        except Exception as exc:
            observation_errors.append(str(exc));return tracker.last_rows
    rows=observe()
    def send(groups,sig):
        for pgid in sorted(groups):
            if pgid<=1 or pgid==own_group:continue
            try:os.killpg(pgid,sig);signals.append({'pgid':pgid,'signal':sig})
            except ProcessLookupError:pass
    supervisor_groups={r['pgid'] for pid,r in rows.items() if pid in tracker.supervisor_pids}
    leaf_groups={r['pgid'] for pid,r in rows.items() if pid!=tracker.root_pid and r['pgid'] not in supervisor_groups}
    send(leaf_groups,signal.SIGTERM)
    deadline=shared_clock()+2
    while shared_clock()<deadline and any(p.poll() is None for p in processes):time.sleep(.05)
    rows=observe()
    remaining={r['pgid'] for pid,r in rows.items() if pid!=tracker.root_pid}
    send(remaining,signal.SIGTERM);time.sleep(.2)
    rows=observe();send({r['pgid'] for pid,r in rows.items() if pid!=tracker.root_pid},signal.SIGKILL)
    for p in processes:
        try:p.wait(timeout=max(.01,min(.5,cleanup_deadline-shared_clock())))
        except subprocess.TimeoutExpired:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            try:p.wait(timeout=max(.01,min(.5,cleanup_deadline-shared_clock())))
            except subprocess.TimeoutExpired:observation_errors.append('direct_child_not_reaped_before_cleanup_deadline:'+str(p.pid))
    rows=observe()
    leftovers=[{'pid':pid,'pgid':r['pgid'],'command':r['command']} for pid,r in rows.items() if pid!=tracker.root_pid and not r['command'].startswith('/bin/ps ')]
    return {'signals':signals,'direct_children_reaped':all(p.poll() is not None for p in processes),'remaining_observed_owned_processes':leftovers,'observation_errors':observation_errors,'reaping_scope':'Direct supervisors waited here; supervisors given grace to wait their workers. Any orphaned grandchildren are reaped by the OS, never falsely claimed waitpid children.'}

def verify_pins():
    p=HERE/'code-pins.json';pins=json.loads(p.read_text())
    for path,h in pins['sha256'].items():
        if rc.file_sha(HERE/path)!=h:raise ValueError('joint_code_pin_mismatch:'+path)
    rc.check_pins();return pins

def run():
    start=shared_clock();pins=verify_pins();ROOT.mkdir(parents=True,exist_ok=True)
    if (ROOT/'joint-start.json').exists():raise ValueError('joint_attempt_already_started_no_retry')
    ledger=ROOT/'aggregate-ledger.json'
    if ledger.exists() and json.loads(ledger.read_text()).get('attempts'):raise ValueError('existing_shard_attempts_refuse_joint_retry')
    if rc.output_size(rc.INTAKE_ROOT)+4*rc.CAPS['output_bytes']>rc.PROCESSED_CEILING:raise ValueError('joint_preflight_combined_processed_reservation')
    import shutil
    if shutil.disk_usage(ROOT).free<rc.FREE_RESERVE+4*rc.CAPS['output_bytes']:raise ValueError('joint_preflight4GB_plus_weights_and_free_floor')
    aggregate.durable_write(ROOT/'joint-start.json',{'status':'ONE_JOINT_ATTEMPT_STARTED_NO_RETRY','pid':os.getpid(),'start_shared_monotonic':start,'shards':[1,2,3,4],'global_seconds':GLOBAL_SECONDS,'global_observed_RSS_bytes':GLOBAL_RSS})
    processes=[];logs=[];tracker=Owned(os.getpid());peak=0;reason=None;cleanup=None
    def external_stop(signum,frame):raise RuntimeError('joint_external_signal:'+str(signum))
    previous_handlers={s:signal.signal(s,external_stop) for s in [signal.SIGTERM,signal.SIGINT]}
    try:
        for shard in range(1,5):
            log=(ROOT/('shard-'+str(shard)+'-supervisor.log')).open('xb');logs.append(log)
            cmd=[sys.executable,str(SHARDS/'supervisor.py'),'--archive',str(ARCHIVE),'--shard',str(shard),'--output',str(ROOT/('shard-'+str(shard)))]
            p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);processes.append(p);tracker.supervisor_pids.add(p.pid)
        while any(p.poll() is None for p in processes):
            rows=tracker.observe(snapshot());rss=sum(r['rss'] for r in rows.values());peak=max(peak,rss)
            reason=decision(shared_clock()-start,rss,rc.output_size(ROOT),shutil.disk_usage(ROOT).free,rc.output_size(rc.INTAKE_ROOT))
            if reason is None and any(p.poll() is not None and p.returncode!=0 for p in processes):reason='shard_supervisor_terminal_failure'
            if reason:cleanup=stop_owned(tracker,processes);break
            time.sleep(min(.5,max(0,GLOBAL_SECONDS-(shared_clock()-start))))
        # A failed supervisor must not leave a separate-session worker running.
        rows=tracker.observe(snapshot());active=[pid for pid,r in rows.items() if pid!=os.getpid() and not r['command'].startswith('/bin/ps ')]
        if active:reason=reason or 'owned_processes_remain_after_supervisors';cleanup=stop_owned(tracker,processes)
        receipts={}
        complete=reason is None
        for shard,p in enumerate(processes,1):
            p.wait(timeout=3);file=ROOT/('shard-'+str(shard))/'supervisor-result.json'
            r=json.loads(file.read_text()) if file.exists() else {'status':'MISSING_SUPERVISOR_RECEIPT'}
            receipts[str(shard)]={'exit_code':p.returncode,'status':r['status'],'receipt_sha256':rc.file_sha(file) if file.exists() else None}
            complete=complete and p.returncode==0 and r['status']=='COMPLETE_CANONICAL_RENDER_SHARD_NO_ADMISSION' and r.get('elapsed_seconds',9999)<=900
        state=json.loads(ledger.read_text()) if ledger.exists() else {}
        complete=complete and len(state.get('attempts',{}))==4 and not state.get('aggregate_actual_overrun',True) and shared_clock()-start<=GLOBAL_SECONDS
        result={'status':'COMPLETE_FOUR_RENDER_SHARDS_PROVISIONAL_NO_ADMISSION' if complete else 'PARTIAL_FOUR_RENDER_SHARDS_NO_ADMISSION','reason':reason,'elapsed_seconds':shared_clock()-start,'peak_observed_owned_tree_RSS_bytes':peak,'global_observed_RSS_hard_bytes':GLOBAL_RSS,'global_wall_seconds':GLOBAL_SECONDS,'shards':receipts,'aggregate_ledger_sha256':rc.file_sha(ledger) if ledger.exists() else None,'cleanup':cleanup,'code_pins':pins,'global_cross_shard_reconciliation':'pending','new_admitted_documents':0,'new_admitted_tokens':0}
        aggregate.durable_write(ROOT/'joint-result.json',result);return 0 if complete else 1
    except BaseException as exc:
        if processes:
            try:cleanup=stop_owned(tracker,processes)
            except Exception as cleanup_exc:cleanup={'error':str(cleanup_exc)}
        aggregate.durable_write(ROOT/'joint-result.json',{'status':'PARTIAL_FOUR_RENDER_SHARDS_NO_ADMISSION','reason':'joint_exception:'+str(exc)[:1500],'elapsed_seconds':shared_clock()-start,'cleanup':cleanup,'new_admitted_documents':0,'new_admitted_tokens':0});raise
    finally:
        for f in logs:f.close()
        for s,handler in previous_handlers.items():signal.signal(s,handler)

if __name__=='__main__':raise SystemExit(run())
