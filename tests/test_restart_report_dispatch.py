import json,os,sys,time,subprocess
from pathlib import Path
import pytest
from slm.restart import report_dispatch as dispatch
from slm.restart.supervisor import TimeBudget,ResourceHistory


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    candidate=tmp_path/'restart/execution-v1/candidate-run-v1';candidate.mkdir(parents=True)
    binding=dict(project=str(tmp_path),output=str(candidate),identity='candidate-v1:'+'a'*64,snapshot_sha256='a'*64,deadline=time.time()+600)
    write(candidate/'parent-binding.json',binding);write(candidate/'snapshot.json',{})
    write(candidate/'final-run-v1/parent-completion.json',{})
    clock=TimeBudget(candidate/'time.sqlite',identity=binding['identity'],seconds_cap=129600,deadline_utc=binding['deadline']);clock.reserve(10,time.time())
    monkeypatch.setattr(dispatch.candidate_snapshot,'verify',lambda *a,**kw:{'original_deadline':binding['deadline']})
    yield binding,candidate,clock
    clock.db.close()


def mock_worker(argv,**kw):
    output=kw['cwd'];candidate=output.parent;ticket=json.loads((candidate/'report-ticket.json').read_bytes())
    pin=dispatch.final_state.digest(candidate/'report-ticket.json')
    kw['budget'].reserve(10,time.time())
    verdict=dict(status='NARRATIVE_RESEARCH_FAIL',final_research_pass=False,identity=ticket['identity'],code_snapshot_sha256=ticket['snapshot_sha256'])
    root=output/'delivery';root.mkdir()
    manifest=dict(schema=1,identity=ticket['identity'],files={})
    write(root/'manifest.json',manifest)
    verdict['delivery']=dict(directory=str(root),manifest_sha256=dispatch.final_state.digest(root/'manifest.json'),**manifest)
    write(output/'research-report-v1.json',verdict)
    write(output/'completion.json',dict(status='REPORT_COMPLETE',report_sha256=dispatch.final_state.digest(output/'research-report-v1.json'),ticket_sha256=pin))
    write(output/'worker-started.json',dict(pid=123,parent_pid=os.getpid(),ticket_sha256=pin))
    result=dict(status='PASS',reason='worker_completed',worker_pid=123,charged_active_seconds=20,observed_seconds=1,stage_active_ceiling=129600,baseline_swap_mib=0)
    history=ResourceHistory(output/'supervisor.json.resources.jsonl')
    history.append('start',stage_active_ceiling=129600,baseline_swap_mib=0)
    history.append('completion',**{k:result[k] for k in ('status','reason','charged_active_seconds','observed_seconds')})
    result['resource_history']=history.close();write(output/'supervisor.json',result)
    return result


def test_parent_report_uses_original_budget_and_publishes_once(fixture,monkeypatch):
    b,candidate,clock=fixture;monkeypatch.setattr(dispatch,'supervise',mock_worker)
    result=dispatch.launch(b,{'synthetic_reviews':True})
    assert result['status']=='NARRATIVE_RESEARCH_FAIL' and result['charged_active_seconds']==20
    assert clock.charged()==20 and clock.terminal() is None
    assert json.loads((candidate/'research-report-v1.json').read_bytes())==result
    with pytest.raises(FileExistsError):dispatch.launch(b,{})


@pytest.mark.parametrize('fault',['supervisor','raw','reviews','pid','identity'])
def test_parent_rejects_fault_without_publishing_pass(fixture,monkeypatch,fault):
    b,candidate,clock=fixture
    def worker(*a,**kw):
        result=mock_worker(*a,**kw);output=kw['cwd']
        if fault=='supervisor':result['status']='STOP'
        if fault=='raw':write(output/'research-report-v1.json',{'forged':True})
        if fault=='reviews':write(output/'reviews.json',{'changed':True})
        if fault=='pid':
            path=output/'worker-started.json';v=json.loads(path.read_bytes());v['pid']=456;write(path,v)
        if fault=='identity':
            path=output/'research-report-v1.json';v=json.loads(path.read_bytes());v['identity']='other';write(path,v)
            path=output/'completion.json';v=json.loads(path.read_bytes());v['report_sha256']=dispatch.final_state.digest(output/'research-report-v1.json');write(path,v)
        return result
    monkeypatch.setattr(dispatch,'supervise',worker)
    with pytest.raises(ValueError):dispatch.launch(b,{})
    assert clock.terminal() and (candidate/'report-stop.json').exists()
    assert not (candidate/'research-report-v1.json').exists()
    with pytest.raises(FileExistsError):dispatch.launch(b,{})


def test_missing_reviews_do_not_consume_attempt(fixture):
    b,candidate,clock=fixture
    with pytest.raises(ValueError,match='reviews'):dispatch.launch(b,None)
    assert not (candidate/'report-run-v1').exists() and clock.charged()==10


def test_worker_preflight_binds_parent_and_one_use(fixture,monkeypatch):
    b,candidate,clock=fixture;monkeypatch.setattr(dispatch,'supervise',mock_worker)
    dispatch.launch(b,{})
    path=candidate/'report-ticket.json';t=json.loads(path.read_bytes());t['parent_pid']=os.getppid();write(path,t)
    marker=candidate/'report-run-v1/worker-started.json';marker.unlink()
    assert dispatch.preflight(path,dispatch.final_state.digest(path))['identity']==b['identity']
    with pytest.raises(FileExistsError):dispatch.preflight(path,dispatch.final_state.digest(path))
    with pytest.raises(ValueError,match='Changed report ticket'):dispatch.preflight(path,'b'*64)


@pytest.mark.skipif(sys.platform!='darwin',reason='macOS reporting custody')
def test_actual_reporting_custody_keeps_training_state_readonly(fixture):
    b,candidate,_=fixture;output=candidate/'report-run-v1';output.mkdir()
    profile=candidate/'report-worker.sb';profile.write_text(dispatch.profile(Path(b['project']),candidate,output))
    script='''import pathlib,sys,socket
candidate=pathlib.Path(sys.argv[1]);output=pathlib.Path(sys.argv[2])
assert (candidate/'parent-binding.json').read_bytes()
(output/'allowed').write_text('ok')
try:(candidate/'forbidden').write_text('bad')
except PermissionError:pass
else:raise AssertionError('Training state write allowed')
try:socket.socket().bind(('127.0.0.1',0))
except PermissionError:pass
else:raise AssertionError('Network allowed')
'''
    run=subprocess.run(dispatch.custody.command(profile,[sys.executable,'-S','-c',script,str(candidate),str(output)]),cwd=output,env={'PATH':'/usr/bin:/bin'},capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    assert not (candidate/'forbidden').exists() and (output/'allowed').read_text()=='ok'


@pytest.mark.parametrize('assessment_fails',[False,True])
def test_worker_assesses_readonly_state_without_model_execution(fixture,monkeypatch,assessment_fails):
    from types import SimpleNamespace
    from slm.restart import token_store,schedule,candidate_evaluation,development_loss,full_diagnostics,delivery
    b,candidate,clock=fixture;project=Path(b['project']);output=candidate/'report-run-v1';output.mkdir()
    ticket=dict(b,candidate=str(candidate),output=str(output))
    monkeypatch.setattr(dispatch,'preflight',lambda *a:ticket)
    write(project/'restart/approval-v1/policy.json',{'architecture':{}})
    write(candidate/'final-ticket.json',{'state_sha256':'b'*64})
    write(project/'restart/execution-v1/batch-schedule-draft-v3/updates.jsonl',{})
    write(output/'reviews.json',{'synthetic':True})
    monkeypatch.setattr(token_store,'TrainingTokens',lambda *a,**kw:SimpleNamespace(_index={}))
    monkeypatch.setattr(schedule,'Schedule',lambda *a,**kw:SimpleNamespace(sha256='schedule'))
    monkeypatch.setattr(delivery,'build',lambda *a,**kw:{'synthetic':True})
    closed=[]
    handles={name:SimpleNamespace(close=lambda name=name:closed.append(name)) for name in ('catalog','quality','pilot','ledger')}
    handles['pilot'].decision=lambda:{'synthetic':True}
    monkeypatch.setattr(dispatch.final_state,'open_state',lambda *a,**kw:handles)
    monkeypatch.setattr(candidate_evaluation,'inputs',lambda *a:{'config':None,'dev_store':object()})
    monkeypatch.setattr(candidate_evaluation,'_MLX',lambda *a:pytest.fail('Report must not execute a model'))
    monkeypatch.setattr(development_loss,'quality_verifier',lambda *a:object())
    monkeypatch.setattr(full_diagnostics,'copying_verifier',lambda **kw:object())
    def assess(*a,**kw):
        assert kw['catalog'] is handles['catalog'] and kw['reviews']=={'synthetic':True}
        assert kw['time_budget'].charged()==10
        kw['heartbeat']()
        if assessment_fails:raise ValueError('fixture assessment failure')
        return dict(status='NARRATIVE_RESEARCH_FAIL',final_research_pass=False)
    monkeypatch.setattr(dispatch.research_report,'assess',assess)
    if assessment_fails:
        with pytest.raises(ValueError,match='fixture'):dispatch.execute('unused','pin')
        assert (output/'worker-stop.json').exists() and not (output/'completion.json').exists()
    else:
        assert dispatch.execute('unused','pin')['status']=='NARRATIVE_RESEARCH_FAIL'
        done=json.loads((output/'completion.json').read_bytes())
        assert done['report_sha256']==dispatch.final_state.digest(output/'research-report-v1.json')
    assert set(closed)==set(handles) and clock.charged()==10
