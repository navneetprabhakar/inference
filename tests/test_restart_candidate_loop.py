import json,sqlite3
from types import SimpleNamespace
import pytest
from slm.restart.candidate_loop import Loop
from slm.restart import pilot_evidence
from slm.restart.monitor import Monitor
from slm.restart.schedule import ScheduledUpdate
from slm.restart.supervisor import TimeBudget


@pytest.fixture
def harness(tmp_path,monkeypatch):
    events=[]
    updates=tuple(ScheduledUpdate(i,1,1000000,1000000*i,.001,(),()) for i in (1,2,3))
    schedule=SimpleNamespace(updates=updates,update_cursors=(0,1,2,3),target_cap=3000000,
                             resume_position=lambda **kw:None)
    db=sqlite3.connect(':memory:',isolation_level=None);db.execute('CREATE TABLE barrier(id INTEGER,terminal TEXT)');db.execute('INSERT INTO barrier VALUES (1,NULL)')
    quality=SimpleNamespace(position=lambda:0,require_monitor=lambda m:None,db=db)
    clock=TimeBudget(tmp_path/'time',identity='fixture',seconds_cap=129600,deadline_utc=9999999999)
    clock.reserve(10,1)
    charged={'count':0}
    ledger=SimpleNamespace(totals=lambda:{'updates_reserved':charged['count']})
    loop=Loop(project=tmp_path,output=tmp_path,identity='fixture',expected={},config=None,schedule=schedule,
        store=None,ledger=ledger,quality=quality,pilot=None,catalog=None,measurements=None,time_budget=clock,
        backend=None,params={},moments={},monitor=Monitor(),rng=None,step=0,targets=0,heartbeat=lambda:events.append('heartbeat'),experiment_start=1)
    def update(u,**kw):
        events.append(('update',u.cumulative_targets));charged['count']+=1
        return dict(params={},moments={},monitor=Monitor(),step=u.step,targets=u.cumulative_targets,metrics={'targets':u.targets})
    monkeypatch.setattr(pilot_evidence,'execute_measured',update)
    monkeypatch.setattr(loop,'evaluate_pending',lambda:events.append(('evaluate',loop.targets)))
    monkeypatch.setattr(loop,'decide_pilot',lambda:events.append('pilot_decision'))
    monkeypatch.setattr(loop,'finish',lambda status:{'status':status,'targets':loop.targets})
    yield loop,events,charged
    db.close();clock.db.close()


def test_initial_evaluation_precedes_updates_and_pilot_stops(harness):
    loop,e,c=harness;r=loop.run()
    assert r=={'status':'PILOT_PASS','targets':2000000} and c['count']==2
    assert e.index(('evaluate',0))<e.index(('update',1000000))
    assert e.index(('evaluate',2000000))<e.index('pilot_decision')
    assert ('update',3000000) not in e


def test_continuation_occurs_only_after_pilot_decision(harness):
    loop,e,c=harness;r=loop.run(stop_after_pilot=False)
    assert r['status']=='NORMAL_BUDGET_END'
    assert e.index('pilot_decision')<e.index(('update',3000000))


def test_failed_pilot_is_durable_and_never_continues(harness,monkeypatch):
    loop,e,c=harness
    def reject():raise ValueError('pilot rejection')
    monkeypatch.setattr(loop,'decide_pilot',reject)
    with pytest.raises(ValueError):loop.run(stop_after_pilot=False)
    assert c['count']==2 and loop.time_budget.terminal()
    assert loop.quality.db.execute('SELECT terminal FROM barrier').fetchone()[0]
    assert json.loads((loop.output/'worker-stop.json').read_text())['final_research_pass'] is False


def test_evaluation_failure_stops_before_first_update(harness,monkeypatch):
    loop,e,c=harness
    def fail():raise ValueError('invalid evaluator evidence')
    monkeypatch.setattr(loop,'evaluate_pending',fail)
    with pytest.raises(ValueError):loop.run()
    assert c['count']==0 and loop.time_budget.terminal()


def test_existing_pilot_rejection_cannot_be_reported_as_pass(harness):
    from slm.restart.pilot_gate import PilotRejected
    loop,_,_=harness
    loop.pilot=SimpleNamespace(decision=lambda:{'result':{'status':'PILOT_REJECTED'}})
    with pytest.raises(PilotRejected):Loop.decide_pilot(loop)


def test_pending_diagnostics_use_previously_accepted_checkpoint(harness,monkeypatch):
    from slm.restart import candidate_evaluation,state
    loop,events,_=harness
    checkpoint=loop.output/'existing-checkpoint';checkpoint.mkdir()
    (checkpoint/'manifest.json').write_text('{}');pin=state.digest(checkpoint/'manifest.json')
    loop.schedule.sha256='schedule'
    loop.quality.pending=lambda:('full_development_diagnostics',)
    loop.quality.accept=lambda event,path,**kw:events.append(('accepted',event,kw['checkpoint_sha256']))
    loop.quality.overlay=lambda monitor:monitor
    loop.catalog=SimpleNamespace(reconcile_scores=lambda barrier:None,evaluation_checkpoint=lambda barrier:checkpoint,prune=lambda:None)
    def forbidden_save():raise AssertionError('Must not publish replacement boundary checkpoint')
    monkeypatch.setattr(loop,'save',forbidden_save)
    monkeypatch.setattr(loop,'verifier',lambda event:None)
    def evaluate(project,path,**kw):
        assert path==checkpoint and kw['manifest_sha256']==pin and kw['quality'] is loop.quality
        return json.dumps({'context':kw['context']}).encode(),{'fixture':True}
    monkeypatch.setattr(candidate_evaluation,'evaluate',evaluate)
    Loop.evaluate_pending(loop)
    assert loop.checkpoint_path==checkpoint
    assert ('accepted','full_development_diagnostics',pin) in events


def test_verified_plateau_runs_copying_before_clean_completion(harness,monkeypatch):
    from slm.restart import candidate_evaluation,state
    from slm.restart.monitor import StopRun
    loop,events,charged=harness;loop.targets=3000000;loop.step=3
    path=loop.output/'plateau-checkpoint';path.mkdir();(path/'manifest.json').write_text('{}')
    pin=state.digest(path/'manifest.json');loop.checkpoint_path=path
    context=dict(identity=loop.identity,schedule_sha256='schedule',step=3,targets=3000000,
                 checkpoint_sha256=pin,event='dev_loss_checkpoint')
    loop.quality.clean_stop=lambda:{'context':context,'reason':'development plateau'}
    loop.quality.accept_terminal_copy=lambda path,**kw:events.append('copy_verified')
    loop.catalog=SimpleNamespace(score=lambda *a:events.append('score'),prune=lambda:events.append('prune'))
    def plateau():raise StopRun('development plateau')
    monkeypatch.setattr(loop,'evaluate_pending',plateau)
    monkeypatch.setattr(loop,'verifier',lambda event:None)
    def evaluate(project,checkpoint,**kw):
        assert checkpoint==path and kw['context']==dict(context,event='copying_probes')
        events.append('copy_evaluated');return b'{}',{}
    monkeypatch.setattr(candidate_evaluation,'evaluate',evaluate)
    result=loop.run(stop_after_pilot=False)
    assert result['status']=='PLATEAU_END' and charged['count']==0
    assert events.index('score')<events.index('copy_evaluated')<events.index('copy_verified')<events.index('prune')


def test_unverified_plateau_is_terminal_failure(harness,monkeypatch):
    from slm.restart.monitor import StopRun
    loop,_,charged=harness
    loop.quality.clean_stop=lambda:None
    def plateau():raise StopRun('development plateau')
    monkeypatch.setattr(loop,'evaluate_pending',plateau)
    with pytest.raises(StopRun):loop.run(stop_after_pilot=False)
    assert charged['count']==0 and loop.time_budget.terminal()
    assert 'Missing post-pilot' in loop.time_budget.terminal()


@pytest.mark.parametrize('targets,status',[(0,'PILOT_BUDGET_END'),(3000000,'WORK_BUDGET_END')])
def test_work_budget_refusal_saves_before_stopping_and_copying(harness,monkeypatch,targets,status):
    loop,events,_=harness;loop.targets=targets
    proof={'fixture':'uncharged refusal'}
    loop.ledger.verify_exhaustion=lambda value:events.append(('verified',value))
    path=loop.output/'budget-checkpoint';path.mkdir();(path/'manifest.json').write_text('{}')
    def save():events.append('save');loop.checkpoint_path=path;return path
    monkeypatch.setattr(loop,'save',save)
    loop.quality.stop_work_budget=lambda *a,**kw:events.append('terminal')
    monkeypatch.setattr(loop,'finish_stopped_copy',lambda status:events.append(('copy',status)) or status)
    assert loop.finish_work_budget(proof)==status
    assert events==[('verified',proof),'save','terminal',('copy',status)]
