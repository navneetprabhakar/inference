import hashlib,json,os
from pathlib import Path
import pytest
from slm.restart import candidate_worker as worker
from slm.restart.supervisor import TimeBudget


@pytest.fixture
def ticket(tmp_path,monkeypatch):
    project=tmp_path/'project';output=project/'restart/execution-v1/candidate-run-v1';output.mkdir(parents=True)
    pin='a'*64;identity='candidate-v1:'+pin
    clock=TimeBudget(output/'time.sqlite',identity=identity,seconds_cap=129600,deadline_utc=1000);clock.reserve(10,100)
    monkeypatch.setattr(worker.candidate_snapshot,'verify',lambda *a,**kw:{'original_deadline':1000})
    t=dict(schema=1,project=str(project),output=str(output),snapshot_sha256=pin,identity=identity,parent_pid=os.getppid(),
           phase='pilot',checkpoint=None,checkpoint_sha256=None,deadline=1000,active_ceiling=7200)
    path=output/'pilot-ticket.json'
    yield path,t,clock
    clock.db.close()


def write(path,t):
    path.write_text(json.dumps(t));return hashlib.sha256(path.read_bytes()).hexdigest()


def test_ticket_single_use_before_any_weights(ticket):
    path,t,_=ticket;pin=write(path,t)
    assert worker.preflight(path,pin,now=100)==t
    with pytest.raises(FileExistsError):worker.preflight(path,pin,now=100)
    assert not (path.parent/'initialization-started.json').exists()


@pytest.mark.parametrize('fault',['parent','identity','phase','ceiling','checkpoint','deadline','terminal','uncharged','schema','snapshot'])
def test_invalid_ticket_never_marks_worker_started(ticket,monkeypatch,fault):
    path,t,clock=ticket
    if fault=='parent':t['parent_pid']=-1
    if fault=='identity':t['identity']='other'
    if fault=='phase':t['phase']='retry'
    if fault=='ceiling':t['active_ceiling']=129600
    if fault=='checkpoint':t['checkpoint']='legacy'
    if fault=='deadline':t['deadline']=2000
    if fault=='terminal':clock.stop('quality stop')
    if fault=='uncharged':clock.db.execute('UPDATE budget SET charged=0')
    if fault=='schema':t['schema']=True
    if fault=='snapshot':
        def refuse(*a,**kw):raise ValueError('changed snapshot')
        monkeypatch.setattr(worker.candidate_snapshot,'verify',refuse)
    pin=write(path,t)
    with pytest.raises(ValueError):worker.preflight(path,pin,now=100)
    assert not (path.parent/'pilot-worker-started.json').exists()


def test_continuation_requires_exact_pilot_checkpoint(ticket):
    path,t,_=ticket;output=path.parent;checkpoint=output/'checkpoints/state-1';checkpoint.mkdir(parents=True)
    (checkpoint/'manifest.json').write_text('{}')
    t.update(phase='continuation',active_ceiling=129600,checkpoint=str(checkpoint),checkpoint_sha256=hashlib.sha256(b'{}').hexdigest())
    pin=write(path,t)
    with pytest.raises(FileNotFoundError):worker.preflight(path,pin,now=100)
    (output/'pilot-completion.json').write_text(json.dumps({'status':'PILOT_PASS','targets':2000000,'checkpoint':str(checkpoint)}))
    assert worker.preflight(path,pin,now=100)==t
    assert not (output/'initialization-started.json').exists()


def test_wrong_architecture_cannot_initialize():
    from slm.common.config import Config
    with pytest.raises(ValueError):worker._fresh(Config())


@pytest.fixture
def recovery_ticket(ticket):
    path,t,clock=ticket;output=path.parent
    original_pin=write(path,t)
    (output/'pilot-worker-started.json').write_text(json.dumps({'ticket_sha256':original_pin}))
    (output/'initialization-complete.json').write_text('{}')
    checkpoint=output/'checkpoints/state-1';checkpoint.mkdir(parents=True)
    (checkpoint/'manifest.json').write_text('{}')
    t.update(phase='pilot-recovery',checkpoint=str(checkpoint),checkpoint_sha256=hashlib.sha256(b'{}').hexdigest())
    return output/'pilot-recovery-ticket.json',t,clock


def test_recovery_dispatch_single_use_and_never_initializes(recovery_ticket):
    path,t,_=recovery_ticket;pin=write(path,t)
    assert worker.preflight(path,pin,now=100)==t
    with pytest.raises(FileExistsError):worker.preflight(path,pin,now=100)
    assert not (path.parent/'initialization-started.json').exists()


@pytest.mark.parametrize('fault',['completed','supervised','worker_stop','parent_stop','uninitialized','original_changed','ceiling'])
def test_recovery_ticket_refuses_closed_or_changed_dispatch(recovery_ticket,fault):
    path,t,_=recovery_ticket;output=path.parent
    names={'completed':'pilot-completion.json','supervised':'pilot-supervisor.json','worker_stop':'worker-stop.json','parent_stop':'parent-stop.json'}
    if fault in names:(output/names[fault]).write_text('{}')
    if fault=='uninitialized':(output/'initialization-complete.json').unlink()
    if fault=='original_changed':(output/'pilot-ticket.json').write_text('{}')
    if fault=='ceiling':t['active_ceiling']=129600
    pin=write(path,t)
    with pytest.raises((ValueError,KeyError)):worker.preflight(path,pin,now=100)
    assert not (output/'pilot-recovery-worker-started.json').exists()
