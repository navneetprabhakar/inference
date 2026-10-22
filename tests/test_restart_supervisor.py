import json
import os
from pathlib import Path
import subprocess
import sys
import time
import pytest
from slm.restart.supervisor import TimeBudget,supervise
from slm.restart.monitor import StopRun
from slm.restart.telemetry import thermal_state,swap_mib,group_rss_gib


def test_time_reservation_survives_crash_and_cannot_reset(tmp_path):
    p=tmp_path/'time.sqlite';a=TimeBudget(p,identity='x',seconds_cap=20,deadline_utc=1000)
    a.reserve(10,1);a.db.close()
    a=TimeBudget(p,identity='x',seconds_cap=20,deadline_utc=1000);assert a.charged()==10
    with pytest.raises(StopRun):TimeBudget(p,identity='x',seconds_cap=30,deadline_utc=1000)
    with pytest.raises(StopRun):a.reserve(10,995)
    assert a.charged()==10
    a.reserve(10,2)
    with pytest.raises(StopRun):a.reserve(1,3)
    a.stop('terminal')
    with pytest.raises(StopRun):a.reserve(1,3)


def event(pgid,cwd,baseline):
    return dict(now=time.monotonic(),rss_gib=1,swap_growth_mib=0,free_disk_gib=100,thermal='nominal')


def test_real_worker_failure_and_resource_stop(tmp_path):
    for name,script,telemetry in [
        ('normal','pass',event),
        ('failed','raise SystemExit(7)',event),
        ('rss','import time;time.sleep(60)',lambda *a:dict(event(*a),rss_gib=19)),
        ('missing','import time;time.sleep(60)',lambda *a:dict(event(*a),thermal=None)),
    ]:
        out=tmp_path/name;out.mkdir();budget=TimeBudget(out/'time',identity=name,seconds_cap=5,deadline_utc=time.time()+20)
        result=supervise([sys.executable,'-c',script],cwd=out,env={"PATH":"/usr/bin:/bin"},heartbeat=out/'heartbeat',budget=budget,receipt=out/'receipt.json',tick=.2,telemetry=telemetry,baseline_reader=lambda:0)
        assert result['status']==('PASS' if name=='normal' else 'STOP')
        assert json.loads((out/'receipt.json').read_text())==result
        with pytest.raises(ProcessLookupError):os.kill(result['worker_pid'],0)

@pytest.mark.skipif(sys.platform!='darwin',reason='macOS native telemetry')
def test_native_telemetry_on_owned_live_process():
    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)'],start_new_session=True)
    try:
        assert thermal_state() in ('nominal','fair','serious','critical')
        assert swap_mib()>=0
        assert group_rss_gib(child.pid)>=0
    finally:child.kill();child.wait()

def test_supervisor_death_reaper_kills_worker(tmp_path):
    project=Path(__file__).resolve().parents[1]
    worker_code="import os,pathlib,time;pathlib.Path('pid').write_text(str(os.getpid()));time.sleep(60)"
    runner='''
import os,pathlib,sys,time
from slm.restart.supervisor import TimeBudget,supervise
p=pathlib.Path(sys.argv[1]);b=TimeBudget(p/'time',identity='orphan-test',seconds_cap=60,deadline_utc=time.time()+90)
supervise([sys.executable,'-c',sys.argv[2]],cwd=p,env={"PATH":"/usr/bin:/bin"},heartbeat=p/'heartbeat',budget=b,receipt=p/'receipt',tick=.2,baseline_reader=lambda:0,telemetry=lambda *a:dict(now=time.monotonic(),rss_gib=1,swap_growth_mib=0,free_disk_gib=100,thermal='nominal'))
'''
    parent=subprocess.Popen([sys.executable,'-c',runner,str(tmp_path),worker_code],env=dict(PATH='/usr/bin:/bin',PYTHONPATH=str(project/'src')))
    worker_pid=None
    try:
        deadline=time.monotonic()+5
        while not (tmp_path/'pid').exists() and time.monotonic()<deadline:time.sleep(.05)
        assert (tmp_path/'pid').exists()
        worker_pid=int((tmp_path/'pid').read_text())
        # Allow reaper setup before deliberate supervisor death.
        time.sleep(.3);parent.kill();parent.wait(timeout=5)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            result=subprocess.run(['/bin/ps','-p',str(worker_pid),'-o','stat='],capture_output=True,text=True)
            if result.returncode or result.stdout.strip().startswith('Z'):break
            time.sleep(.05)
        else:pytest.fail('Worker survived supervisor death')
    finally:
        if parent.poll() is None:parent.kill();parent.wait()
        if worker_pid:
            try:os.killpg(worker_pid,9)
            except ProcessLookupError:pass

def test_slow_telemetry_cannot_extend_worker_budget(tmp_path):
    budget=TimeBudget(tmp_path/'time',identity='slow-metrics',seconds_cap=1,deadline_utc=time.time()+20)
    def slow(*args):
        time.sleep(1.2)
        return event(*args)
    started=time.monotonic()
    result=supervise([sys.executable,'-c','import time;time.sleep(60)'],cwd=tmp_path,env={"PATH":"/usr/bin:/bin"},heartbeat=tmp_path/'heartbeat',budget=budget,receipt=tmp_path/'receipt',tick=.2,telemetry=slow,baseline_reader=lambda:0)
    assert result['status']=='STOP'
    assert time.monotonic()-started<3
    with pytest.raises(ProcessLookupError):os.kill(result['worker_pid'],0)


@pytest.mark.parametrize('failure',['worker','resource','telemetry'])
def test_terminal_stop_survives_reopen_and_cannot_launch_new_worker(tmp_path,failure):
    deadline=time.time()+30
    budget=TimeBudget(tmp_path/'time',identity='persistent-failure',seconds_cap=5,deadline_utc=deadline)
    script='raise SystemExit(7)' if failure=='worker' else 'import time;time.sleep(60)'
    def measured(*args):
        if failure=='telemetry':raise RuntimeError('telemetry fixture failure')
        return dict(event(*args),rss_gib=19) if failure=='resource' else event(*args)
    first=supervise([sys.executable,'-c',script],cwd=tmp_path,env={'PATH':'/usr/bin:/bin'},heartbeat=tmp_path/'heartbeat1',budget=budget,receipt=tmp_path/'first.json',tick=.1,telemetry=measured,baseline_reader=lambda:0)
    assert first['status']=='STOP'
    original=budget.terminal();charged=budget.charged();assert original
    budget.db.close()
    budget=TimeBudget(tmp_path/'time',identity='persistent-failure',seconds_cap=5,deadline_utc=deadline)
    second=supervise([sys.executable,'-c',"from pathlib import Path;Path('forbidden-worker-start').write_text('started')"],cwd=tmp_path,env={'PATH':'/usr/bin:/bin'},heartbeat=tmp_path/'heartbeat2',budget=budget,receipt=tmp_path/'second.json',tick=.1,telemetry=event,baseline_reader=lambda:0)
    assert second['status']=='STOP' and second['worker_pid'] is None
    assert not (tmp_path/'forbidden-worker-start').exists()
    assert budget.terminal()==original and budget.charged()>=charged
    budget.db.close()


def test_stage_ceiling_kills_hung_worker_without_resetting_total_contract(tmp_path):
    deadline=time.time()+30
    budget=TimeBudget(tmp_path/'time',identity='candidate-stage',seconds_cap=10,deadline_utc=deadline)
    budget.reserve(.5,time.time())
    started=time.monotonic()
    result=supervise([sys.executable,'-c','import time;time.sleep(60)'],cwd=tmp_path,env={'PATH':'/usr/bin:/bin'},
        heartbeat=tmp_path/'hb',budget=budget,receipt=tmp_path/'result',tick=.2,telemetry=event,baseline_reader=lambda:0,active_ceiling=1)
    assert result['status']=='STOP' and result['stage_active_ceiling']==1
    assert time.monotonic()-started<2
    assert .5<budget.charged()<=1 and budget.cap==10 and budget.deadline==deadline
    with pytest.raises(ProcessLookupError):os.kill(result['worker_pid'],0)
    budget.db.close()


def test_successful_stage_retains_clock_for_next_stage(tmp_path):
    budget=TimeBudget(tmp_path/'time',identity='candidate-stages',seconds_cap=10,deadline_utc=time.time()+30)
    def stage(name,ceiling):
        return supervise([sys.executable,'-c','pass'],cwd=tmp_path,env={'PATH':'/usr/bin:/bin'},heartbeat=tmp_path/(name+'hb'),
            budget=budget,receipt=tmp_path/name,tick=.2,telemetry=event,baseline_reader=lambda:0,active_ceiling=ceiling)
    assert stage('pilot',1)['status']=='PASS'
    charged=budget.charged();assert charged>0
    assert stage('continuation',10)['status']=='PASS'
    assert budget.charged()>charged and budget.terminal() is None
    budget.db.close()


def test_exhausted_stage_refuses_launch_even_with_total_budget_remaining(tmp_path):
    budget=TimeBudget(tmp_path/'time',identity='spent-stage',seconds_cap=10,deadline_utc=time.time()+30)
    budget.reserve(1,time.time())
    result=supervise([sys.executable,'-c',"from pathlib import Path;Path('started').touch()"],cwd=tmp_path,env={'PATH':'/usr/bin:/bin'},
        heartbeat=tmp_path/'hb',budget=budget,receipt=tmp_path/'result',tick=.2,telemetry=event,baseline_reader=lambda:0,active_ceiling=1)
    assert result['status']=='STOP' and result['worker_pid'] is None
    assert not (tmp_path/'started').exists() and budget.charged()==1
    budget.db.close()


def test_resource_history_preserves_stop_trigger_and_receipt_hash(tmp_path):
    import hashlib
    budget=TimeBudget(tmp_path/'time',identity='logged-stop',seconds_cap=5,deadline_utc=time.time()+20)
    result=supervise([sys.executable,'-c','import time;time.sleep(60)'],cwd=tmp_path,env={'PATH':'/usr/bin:/bin'},
        heartbeat=tmp_path/'hb',budget=budget,receipt=tmp_path/'receipt.json',tick=.1,
        telemetry=lambda *a:dict(event(*a),rss_gib=19),baseline_reader=lambda:123)
    pin=result['resource_history'];raw=Path(pin['path']).read_bytes()
    records=[json.loads(line) for line in raw.splitlines()]
    assert hashlib.sha256(raw).hexdigest()==pin['sha256']
    assert pin['records']==len(records)==3
    assert [r['sequence'] for r in records]==[0,1,2]
    assert records[0]['baseline_swap_mib']==123
    assert records[1]['measurement']['rss_gib']==19
    assert records[1]['worker_pid']==result['worker_pid']
    assert records[-1]['status']=='STOP' and 'RSS' in records[-1]['reason']
    budget.db.close()


def test_existing_resource_history_refuses_worker_without_overwrite(tmp_path):
    budget=TimeBudget(tmp_path/'time',identity='logged-collision',seconds_cap=5,deadline_utc=time.time()+20)
    journal=tmp_path/'receipt.json.resources.jsonl';journal.write_text('original')
    result=supervise([sys.executable,'-c',"from pathlib import Path;Path('started').touch()"],cwd=tmp_path,env={'PATH':'/usr/bin:/bin'},
        heartbeat=tmp_path/'hb',budget=budget,receipt=tmp_path/'receipt.json',tick=.1,telemetry=event,baseline_reader=lambda:0)
    assert result['status']=='STOP' and result['worker_pid'] is None
    assert journal.read_text()=='original' and not (tmp_path/'started').exists()
    assert budget.terminal()
    budget.db.close()


def test_resource_history_rejects_nonfinite_without_corrupting_prefix(tmp_path):
    from slm.restart.supervisor import ResourceHistory
    journal=ResourceHistory(tmp_path/'resources')
    journal.append('start',value=1)
    with pytest.raises(ValueError):journal.append('resource',value=float('nan'))
    pin=journal.close()
    assert pin['records']==1 and len((tmp_path/'resources').read_text().splitlines())==1


def test_verified_resource_history_detects_tampering(tmp_path):
    from slm.restart.supervisor import verify_resource_history
    budget=TimeBudget(tmp_path/'time',identity='logged-success',seconds_cap=5,deadline_utc=time.time()+20)
    result=supervise([sys.executable,'-c','pass'],cwd=tmp_path,env={'PATH':'/usr/bin:/bin'},heartbeat=tmp_path/'hb',budget=budget,
        receipt=tmp_path/'receipt.json',tick=.1,telemetry=event,baseline_reader=lambda:0)
    rows=verify_resource_history(tmp_path/'receipt.json')
    assert rows[0]['kind']=='start' and rows[-1]['status']=='PASS'
    path=Path(result['resource_history']['path']);path.write_text(path.read_text()+'{}\n')
    with pytest.raises(ValueError,match='Changed'):verify_resource_history(tmp_path/'receipt.json')
    budget.db.close()
