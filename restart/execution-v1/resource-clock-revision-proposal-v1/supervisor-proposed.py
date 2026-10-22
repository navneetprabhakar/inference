"""Owned-process supervision with persistent time reservations and orphan reaping.

The eventual scoped launcher must validate approvals/artifacts before calling
this primitive. This module does not open the legacy model/training guard.
"""
import json
import hashlib
import os
from pathlib import Path
import select
import signal
import sqlite3
import subprocess
import sys
import time
from .monitor import Resources,StopRun
from .telemetry import snapshot,swap_mib


def atomic_json(path,value):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('w') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


class ResourceHistory:
    """Exclusive durable observations; a crash leaves the completed prefix."""
    def __init__(self,path):
        self.path=Path(path);self.file=self.path.open('x');self.count=0
        self.digest=hashlib.sha256()

    def append(self,kind,**values):
        encoded=(json.dumps(dict(sequence=self.count,kind=kind,**values),sort_keys=True,allow_nan=False)+'\n').encode()
        self.file.write(encoded.decode());self.file.flush();os.fsync(self.file.fileno())
        self.digest.update(encoded);self.count+=1

    def close(self):
        self.file.close()
        return dict(path=str(self.path),sha256=self.digest.hexdigest(),records=self.count,
            scope='Observed supervisor samples only; intervals and sub-tick peaks are not reconstructed')


def verify_resource_history(receipt_path):
    """Bind retained samples to their supervisor result; never infer missed peaks."""
    receipt_path=Path(receipt_path).absolute()
    if receipt_path.resolve(strict=True)!=receipt_path:raise ValueError('Redirected supervisor receipt')
    result=json.loads(receipt_path.read_bytes());pin=result['resource_history']
    path=receipt_path.with_name(receipt_path.name+'.resources.jsonl')
    if str(path)!=pin['path'] or path.resolve(strict=True)!=path:raise ValueError('Redirected resource history')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Changed resource history')
    rows=[json.loads(line) for line in raw.splitlines()]
    if len(rows)!=pin['records'] or len(rows)<2 or any(type(r['sequence']) is not int or r['sequence']!=i for i,r in enumerate(rows)):
        raise ValueError('Incomplete resource history')
    if rows[0]['kind']!='start' or rows[-1]['kind']!='completion':raise ValueError('Unfinished resource history')
    if any(r['kind']!='resource' or r['worker_pid']!=result['worker_pid'] for r in rows[1:-1]):
        raise ValueError('Mixed resource history')
    for key in ('status','reason','charged_active_seconds','observed_seconds'):
        if rows[-1][key]!=result[key]:raise ValueError('Resource completion differs from supervisor')
    if rows[0]['stage_active_ceiling']!=result['stage_active_ceiling'] or rows[0]['baseline_swap_mib']!=result['baseline_swap_mib']:
        raise ValueError('Resource contract differs from supervisor')
    return rows


class TimeBudget:
    """Charge the next interval before allowing it; crashes never refund time."""
    def __init__(self,path,*,identity,seconds_cap,deadline_utc):
        if not identity or type(seconds_cap) is not int or seconds_cap<=0:raise ValueError('Invalid time contract')
        if type(deadline_utc) not in (int,float) or not 0<deadline_utc<float('inf'):raise ValueError('Invalid deadline')
        self.db=sqlite3.connect(path,isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY CHECK(id=1), contract TEXT NOT NULL, charged REAL NOT NULL, terminal TEXT)')
        contract=json.dumps(dict(identity=identity,seconds_cap=seconds_cap,deadline_utc=deadline_utc),sort_keys=True)
        self.db.execute('INSERT OR IGNORE INTO budget VALUES (1,?,0,NULL)',(contract,))
        if self.db.execute('SELECT contract FROM budget').fetchone()[0]!=contract:raise StopRun('Changed time contract')
        self.cap=seconds_cap;self.deadline=deadline_utc

    def reserve(self,seconds,now_utc):
        if not 0<seconds<=10 or not 0<now_utc<float('inf'):raise ValueError('Invalid tick/clock')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            used,terminal=self.db.execute('SELECT charged,terminal FROM budget').fetchone()
            if terminal:raise StopRun('Terminal time ledger: '+terminal)
            if now_utc+seconds>self.deadline:raise StopRun('Elapsed time budget exhausted')
            if used+seconds>self.cap:raise StopRun('Active time budget exhausted')
            self.db.execute('UPDATE budget SET charged=charged+? WHERE id=1',(seconds,));self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise

    def settle_elapsed(self,absolute_seconds):
        # No refunds: account for time spent collecting telemetry as well as waits.
        if not 0<=absolute_seconds<=self.cap:raise ValueError('Invalid elapsed settlement')
        self.db.execute('UPDATE budget SET charged=max(charged,?) WHERE id=1',(absolute_seconds,))

    def stop(self,reason):
        if not isinstance(reason,str) or not reason:raise ValueError('Terminal reason required')
        # A denied restart must not overwrite the original terminal failure.
        self.db.execute('UPDATE budget SET terminal=coalesce(terminal,?) WHERE id=1',(reason,))
    def terminal(self):return self.db.execute('SELECT terminal FROM budget WHERE id=1').fetchone()[0]
    def charged(self):return self.db.execute('SELECT charged FROM budget').fetchone()[0]


def kill_group(pgid):
    if pgid<=1 or pgid==os.getpgrp():raise ValueError('Refuse to kill unowned/current process group')
    try:os.killpg(pgid,signal.SIGKILL)
    except ProcessLookupError:pass
    except PermissionError:
        # Darwin can return EPERM when only a dead/zombie group remains.
        check=subprocess.run(['/bin/ps','-axo','pgid=,stat='],check=True,capture_output=True,text=True,timeout=5)
        live=[line for line in check.stdout.splitlines() if line.split() and int(line.split()[0])==pgid and not line.split()[1].startswith('Z')]
        if live:raise


def orphan_reaper(pgid,deadline):
    """Separate process: parent pipe EOF or >30s silence kills owned worker group."""
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:kill_group(pgid);return
        ready,_,_=select.select([sys.stdin.buffer],[],[],min(30,remaining))
        if not ready or not os.read(sys.stdin.fileno(),1):
            kill_group(pgid);return


def supervise(argv,*,cwd,env,heartbeat,budget,receipt,tick=10,telemetry=snapshot,baseline_reader=swap_mib,active_ceiling=None):
    if not 0<tick<=10:raise ValueError('Supervisor tick must be <=10s')
    active_ceiling=budget.cap if active_ceiling is None else active_ceiling
    if type(active_ceiling) not in (int,float) or not 0<active_ceiling<=budget.cap:
        raise ValueError('Invalid stage active-time ceiling')
    cwd=Path(cwd).resolve(strict=True);receipt=Path(receipt)
    baseline=baseline_reader()  # fail before worker starts if unavailable
    monitor=Resources();reason=None;worker=None;reaper=None;last_hb=None
    started=time.monotonic();worker_code=None;history=None
    initial_charge=budget.charged()
    hard_deadline=started+min(active_ceiling-initial_charge,budget.deadline-time.time())
    def reserve_tick():
        remaining=active_ceiling-budget.charged()
        if remaining<=0:raise StopRun('Stage active-time budget exhausted')
        budget.reserve(min(tick,remaining),time.time())
    # A fresh heartbeat is required, never inherit a stale prior worker file.
    if Path(heartbeat).exists():raise StopRun('Existing heartbeat must be archived before launch')
    try:
        history=ResourceHistory(receipt.with_name(receipt.name+'.resources.jsonl'))
        history.append('start',monotonic=started,utc=time.time(),baseline_swap_mib=baseline,initial_charged_seconds=initial_charge,stage_active_ceiling=active_ceiling,elapsed_deadline=budget.deadline,tick_seconds=tick)
        reserve_tick()
        worker=subprocess.Popen(argv,cwd=cwd,env=env,start_new_session=True,close_fds=True)
        # Use this same interpreter/package; child has no worker's heldout inputs.
        reaper_env=dict(PATH='/usr/bin:/bin',PYTHONPATH=str(Path(__file__).resolve().parents[2]))
        reaper=subprocess.Popen([sys.executable,'-m','slm.restart.supervisor','reap',str(worker.pid),str(hard_deadline)],stdin=subprocess.PIPE,env=reaper_env,close_fds=True)
        while True:
            reaper.stdin.write(b'.');reaper.stdin.flush()
            # Reservation-clock anchoring includes telemetry/checkpoint overhead.
            until=min(started+budget.charged()-initial_charge,hard_deadline)
            while time.monotonic()<until:
                worker_code=worker.poll()
                if worker_code is not None:break
                if reaper.poll() is not None:raise StopRun('Orphan reaper stopped')
                time.sleep(min(.1,max(0,until-time.monotonic())))
            if time.monotonic()>=hard_deadline:raise StopRun('Active/elapsed wall-clock budget exhausted')
            if worker_code is not None:
                if worker_code!=0:raise StopRun('Worker exited '+str(worker_code))
                reason='worker_completed';break
            event=telemetry(worker.pid,cwd,baseline)
            if Path(heartbeat).exists():
                hb=json.loads(Path(heartbeat).read_text())
                if set(hb)!={'pid','monotonic'} or hb['pid']!=worker.pid:raise StopRun('Invalid heartbeat identity')
                value=hb['monotonic']
                if type(value) not in (int,float) or not started<=value<=time.monotonic():raise StopRun('Invalid heartbeat clock')
                if last_hb is not None and value<last_hb:raise StopRun('Heartbeat clock reversed')
                last_hb=value
            # Startup has the same 120-second heartbeat allowance as later work.
            event['heartbeat_at']=last_hb if last_hb is not None else started
            sampled_at=event['now'];observed_at=time.monotonic()
            if sampled_at>observed_at or (monitor.last_clock is not None and sampled_at<monitor.last_clock):
                raise StopRun('Invalid resource sample clock')
            # Heartbeat can advance while native telemetry is being collected.
            # Compare it with the clock after both reads, preserving the sample time.
            event['now']=observed_at
            history.append('resource',worker_pid=worker.pid,charged_active_seconds=budget.charged(),resource_sample_started_monotonic=sampled_at,measurement=event)
            monitor.observe(**event)
            reserve_tick()
    except BaseException as exc:
        reason=f'{type(exc).__name__}: {exc}';budget.stop(reason)
        if isinstance(exc,(KeyboardInterrupt,SystemExit)):reason='user_or_supervisor_interruption'
    finally:
        budget.settle_elapsed(min(budget.cap,initial_charge+max(0,min(time.monotonic(),hard_deadline)-started)))
        if worker is not None:
            kill_group(worker.pid)
            worker.wait(timeout=10)
        if reaper is not None:
            try:reaper.stdin.close()
            except BrokenPipeError:pass  # reaper may already have enforced deadline
            reaper.wait(timeout=10)
        result={'status':'PASS' if reason=='worker_completed' else 'STOP','reason':reason,'worker_pid':worker.pid if worker else None,'worker_returncode':worker_code,'charged_active_seconds':budget.charged(),'observed_seconds':time.monotonic()-started,'baseline_swap_mib':baseline,'stage_active_ceiling':active_ceiling,'scope':'supervision only; worker completion does not prove milestone acceptance'}
        if history is not None:
            history.append('completion',status=result['status'],reason=reason,charged_active_seconds=budget.charged(),observed_seconds=result['observed_seconds'])
            result['resource_history']=history.close()
        atomic_json(receipt,result)
    return result

if __name__=='__main__':
    if len(sys.argv)!=4 or sys.argv[1]!='reap':raise SystemExit('Only internal orphan reaper entrypoint supported')
    orphan_reaper(int(sys.argv[2]),float(sys.argv[3]))
