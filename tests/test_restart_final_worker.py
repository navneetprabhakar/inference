import hashlib,json,os
import pytest
from slm.restart import final_worker as worker
from slm.restart.supervisor import TimeBudget


def write(path,value):
    path.write_text(json.dumps(value));return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    candidate=tmp_path/'restart/execution-v1/candidate-run-v1';output=candidate/'final-run-v1';output.mkdir(parents=True)
    pin='a'*64;identity='candidate-v1:'+pin;best={'path':'fixture-best'}
    completion=candidate/'continuation-completion.json';completion_pin=write(completion,{'status':'NORMAL_BUDGET_END','best':best})
    write(candidate/'continuation-supervisor.json',{'status':'PASS'})
    state=candidate/'final-state-v1';state.mkdir();state_pin=write(state/'manifest.json',{})
    profile=candidate/'final-worker.sb';profile.write_text('fixture-profile')
    clock=TimeBudget(candidate/'time.sqlite',identity=identity,seconds_cap=129600,deadline_utc=1000);clock.reserve(10,100)
    monkeypatch.setattr(worker.candidate_snapshot,'verify',lambda *a,**kw:{'original_deadline':1000})
    monkeypatch.setattr(worker.final_custody,'profile',lambda *a:'fixture-profile')
    ticket=dict(schema=1,project=str(tmp_path),candidate=str(candidate),output=str(output),identity=identity,
        snapshot_sha256=pin,state_sha256=state_pin,completion_sha256=completion_pin,training_phase='continuation',
        selection=best,deadline=1000,parent_pid=os.getppid(),profile_sha256=worker.final_state.digest(profile))
    yield candidate/'final-ticket.json',ticket,clock
    clock.db.close()


def test_final_ticket_single_use_without_loading_model(fixture):
    path,t,_=fixture;pin=write(path,t)
    assert worker.preflight(path,pin,now=100)[0]==t
    with pytest.raises(FileExistsError):worker.preflight(path,pin,now=100)


@pytest.mark.parametrize('fault',['parent','schema','identity','deadline','phase','selection','completion','state','profile','terminal','empty_clock','prior_failure'])
def test_invalid_final_ticket_rejected_before_marker(fixture,fault):
    path,t,clock=fixture
    if fault=='parent':t['parent_pid']=-1
    if fault=='schema':t['schema']=True
    if fault=='identity':t['identity']='other'
    if fault=='deadline':t['deadline']=2000
    if fault=='phase':t['training_phase']='pilot'
    if fault=='selection':t['selection']={'path':'other'}
    if fault=='completion':t['completion_sha256']='b'*64
    if fault=='state':t['state_sha256']='b'*64
    if fault=='profile':t['profile_sha256']='b'*64
    if fault=='terminal':clock.stop('quality failure')
    if fault=='empty_clock':clock.db.execute('UPDATE budget SET charged=0')
    if fault=='prior_failure':(path.parent/'worker-stop.json').write_text('{}')
    pin=write(path,t)
    with pytest.raises(ValueError):worker.preflight(path,pin,now=100)
    assert not (path.parent/'final-run-v1/worker-started.json').exists()
