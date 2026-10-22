import json
from types import SimpleNamespace
import sqlite3
import pytest
from slm.restart.evaluation_quality import EvaluationQualityBarrier
from slm.restart.evaluation_barrier import EvaluationPending
from slm.restart.monitor import Monitor,StopRun
from slm.restart.schedule import ScheduledUpdate


@pytest.fixture
def fixture(tmp_path):
    updates=tuple(ScheduledUpdate(i,1,500000,2000000+i*500000,.0001,('dev_loss_checkpoint',),()) for i in (1,2,3))
    s=SimpleNamespace(sha256='schedule',updates=updates)
    b=EvaluationQualityBarrier(tmp_path/'db',identity='run',schedule=s)
    yield b,s,tmp_path
    b.close()


def accept(b,p,nll):
    step=b.position();targets=0 if step==0 else b.schedule.updates[step-1].cumulative_targets
    context=dict(identity='run',schedule_sha256='schedule',step=step,targets=targets,event='dev_loss_checkpoint',checkpoint_sha256='a'*64)
    path=p/'raw.json';path.write_text(json.dumps({'context':context,'raw_nll':nll}))
    b.accept('dev_loss_checkpoint',path,checkpoint_sha256='a'*64,
             verify=lambda raw,context:{'nll':json.loads(raw)['raw_nll']})


def test_reopen_and_checkpoint_overlay_preserve_quality_and_update_histories(fixture):
    b,s,p=fixture;accept(b,p,2.)
    with pytest.raises(EvaluationPending):b.require_monitor(Monitor())
    old=Monitor(losses=[1.],gradients=[.2],loss_streak=1)
    restored=b.overlay(old)
    assert old.dev==[] and restored.dev==[2.] and restored.losses==[1.] and restored.loss_streak==1
    reopened=EvaluationQualityBarrier(p/'db',identity='run',schedule=s)
    try:reopened.require_monitor(restored)
    finally:reopened.close()


def test_regression_stop_survives_checkpoint_and_reopen(fixture):
    b,s,p=fixture;accept(b,p,2.);b.completed_update(s.updates[0]);accept(b,p,2.2)
    assert b.evaluation_state()['dev_streak']==1
    b.completed_update(s.updates[1])
    with pytest.raises(StopRun,match='development regression'):accept(b,p,2.2)
    with pytest.raises(EvaluationPending):b.overlay(Monitor())
    reopened=EvaluationQualityBarrier(p/'db',identity='run',schedule=s)
    try:
        with pytest.raises(EvaluationPending):reopened.require_update(s.updates[2])
    finally:reopened.close()


def test_evidence_insert_failure_rolls_back_monitor_transition(fixture):
    b,s,p=fixture
    before=b.db.execute('SELECT state FROM quality').fetchone()[0]
    b.db.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON evidence BEGIN SELECT RAISE(ABORT,'simulated publication failure'); END")
    with pytest.raises(sqlite3.IntegrityError):accept(b,p,2.)
    assert b.db.execute('SELECT state FROM quality').fetchone()[0]==before
    assert b.db.execute('SELECT count(*) FROM evidence').fetchone()[0]==0
    with pytest.raises(EvaluationPending):b.require_update(s.updates[0])


def test_boolean_verifier_cannot_skip_monitor_transition(fixture):
    b,s,p=fixture
    path=p/'raw.json';path.write_text(json.dumps({'context':dict(identity='run',schedule_sha256='schedule',step=0,targets=0,event='dev_loss_checkpoint',checkpoint_sha256='a'*64)}))
    with pytest.raises(ValueError,match='Recomputed'):
        b.accept('dev_loss_checkpoint',path,checkpoint_sha256='a'*64,verify=lambda raw,context:True)
    with pytest.raises(EvaluationPending):b.position()


@pytest.fixture
def plateau(tmp_path):
    updates=tuple(ScheduledUpdate(i,1,500000,i*500000,.0001,('dev_loss_checkpoint',),()) for i in range(1,7))
    s=SimpleNamespace(sha256='schedule',updates=updates)
    b=EvaluationQualityBarrier(tmp_path/'plateau-db',identity='run',schedule=s)
    accept(b,tmp_path,2.)
    for update in updates[:-1]:
        b.completed_update(update);accept(b,tmp_path,2.)
    b.completed_update(updates[-1])
    yield b,s,tmp_path
    b.close()


def test_plateau_commits_evidence_and_terminal_state_atomically(plateau):
    b,s,p=plateau
    with pytest.raises(StopRun,match='plateau'):accept(b,p,2.)
    stop=b.clean_stop()
    assert stop['context']['targets']==3000000
    assert b.db.execute('SELECT count(*) FROM evidence').fetchone()[0]==7
    assert len(json.loads(b.db.execute('SELECT state FROM quality').fetchone()[0])['dev'])==7
    reopened=EvaluationQualityBarrier(p/'plateau-db',identity='run',schedule=s)
    try:
        assert reopened.clean_stop()==stop
        with pytest.raises(EvaluationPending):reopened.position()
        with pytest.raises(EvaluationPending):reopened.overlay(Monitor())
    finally:reopened.close()


def test_plateau_publication_failure_does_not_leave_clean_stop(plateau):
    b,_,p=plateau
    b.db.execute("CREATE TRIGGER fail_plateau BEFORE INSERT ON evidence BEGIN SELECT RAISE(ABORT,'disk fixture'); END")
    with pytest.raises(sqlite3.IntegrityError):accept(b,p,2.)
    assert b.clean_stop() is None
    assert b.db.execute('SELECT count(*) FROM evidence').fetchone()[0]==6
    with pytest.raises(EvaluationPending):b.position()


def copying(b,p,train=0,heldout=0,context_change=None):
    context=dict(b.clean_stop()['context'],event='copying_probes')
    if context_change:context.update(context_change)
    path=p/'terminal-copy.json'
    path.write_text(json.dumps({'context':context,'metrics':{'train_copies':train,'heldout_copies':heldout}}))
    b.accept_terminal_copy(path,verify=lambda raw,context:json.loads(raw)['metrics'])


def test_plateau_copying_does_not_revive_training(plateau):
    b,_,p=plateau
    with pytest.raises(StopRun):accept(b,p,2.)
    copying(b,p)
    assert b.db.execute('SELECT copy_pin FROM clean_stop').fetchone()[0]
    assert b.clean_stop()['reason']=='development plateau'
    with pytest.raises(EvaluationPending):b.require_update(b.schedule.updates[-1])
    with pytest.raises(ValueError,match='already recorded'):copying(b,p)


@pytest.mark.parametrize('fault',['copying','context','corrupt_evidence'])
def test_termination_copying_failure_cannot_become_clean_end(plateau,fault):
    b,_,p=plateau
    with pytest.raises(StopRun):accept(b,p,2.)
    if fault=='corrupt_evidence':
        b.db.execute("UPDATE evidence SET sha256='changed' WHERE step=6")
        with pytest.raises(ValueError):b.clean_stop()
    else:
        with pytest.raises((StopRun,ValueError)):
            copying(b,p,train=20 if fault=='copying' else 0,context_change={'targets':4000000} if fault=='context' else None)
        with pytest.raises(ValueError):b.clean_stop()
    with pytest.raises(EvaluationPending):b.position()


@pytest.fixture
def work_exhaustion(tmp_path):
    from slm.restart.ledger import Ledger,WorkBudgetExhausted
    update=ScheduledUpdate(1,1,1,1,.001,(),((('doc',0,1),),))
    schedule=SimpleNamespace(sha256='schedule',updates=(update,))
    b=EvaluationQualityBarrier(tmp_path/'work-quality',identity='run',schedule=schedule)
    accept(b,tmp_path,2.)
    ledger=Ledger(tmp_path/'work-ledger','run',target_cap=1,update_cap=3,presentation_cap=3,deadline=100)
    ledger.reserve('crashed',[('doc',0,1)],now=1)
    with pytest.raises(WorkBudgetExhausted) as caught:ledger.reserve('replay',[('doc',0,1)],now=2)
    yield b,ledger,caught.value.proof,tmp_path
    b.close();ledger.close()


def test_work_exhaustion_stop_preserves_ledger_and_requires_copying(work_exhaustion):
    b,ledger,proof,p=work_exhaustion;before=ledger.snapshot()
    stop=b.stop_work_budget(ledger,proof,checkpoint_sha256='a'*64)
    assert stop['reason']=='work budget exhausted' and b.clean_stop()==stop
    assert ledger.snapshot()==before
    with pytest.raises(EvaluationPending):b.position()
    copying(b,p)
    assert b.db.execute('SELECT copy_pin FROM clean_stop').fetchone()[0]
    assert ledger.snapshot()==before


@pytest.mark.parametrize('fault',['schedule','ledger','checkpoint','pending'])
def test_work_stop_rejects_unbound_or_changed_refusal(work_exhaustion,fault):
    b,ledger,proof,p=work_exhaustion
    if fault=='schedule':proof['spans']=[['other',0,1]]
    if fault=='ledger':ledger.complete('crashed')
    if fault=='pending':b.db.execute('DELETE FROM evidence')
    with pytest.raises(ValueError):b.stop_work_budget(ledger,proof,checkpoint_sha256='invalid' if fault=='checkpoint' else 'a'*64)
    assert b.clean_stop() is None and b.position()==0
