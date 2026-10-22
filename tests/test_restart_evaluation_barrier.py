import json
from types import SimpleNamespace
import pytest
from slm.restart.evaluation_barrier import EvaluationBarrier, EvaluationPending
from slm.restart.schedule import ScheduledUpdate


@pytest.fixture
def fixture(tmp_path):
    updates=tuple(ScheduledUpdate(i,1,500000,i*500000,.0002,('dev_loss_checkpoint',),()) for i in (1,2))
    schedule=SimpleNamespace(updates=updates,sha256='fixed-schedule')
    b=EvaluationBarrier(tmp_path/'events.sqlite',identity='run',schedule=schedule)
    yield b,schedule,tmp_path
    b.close()


def evidence(b,root,event='dev_loss_checkpoint',**changes):
    step=b.position()
    context=dict(identity='run',schedule_sha256='fixed-schedule',step=step,
                 targets=step*500000,event=event,checkpoint_sha256='a'*64)
    context.update(changes)
    path=root/'raw.json';path.write_text(json.dumps(dict(context=context,metrics={'nll':2.})))
    return path


def accept(b,root,event='dev_loss_checkpoint'):
    b.accept(event,evidence(b,root,event),checkpoint_sha256='a'*64,
             verify=lambda raw,context:json.loads(raw)['metrics']['nll']==2.)


def test_initial_and_every_boundary_survive_reopen(fixture):
    b,s,p=fixture
    with pytest.raises(EvaluationPending):b.require_update(s.updates[0])
    accept(b,p);b.require_update(s.updates[0]);b.completed_update(s.updates[0])
    reopened=EvaluationBarrier(p/'events.sqlite',identity='run',schedule=s)
    try:
        with pytest.raises(EvaluationPending):reopened.require_update(s.updates[1])
        with pytest.raises(EvaluationPending):reopened.require_update(s.updates[0])
        accept(reopened,p);reopened.completed_update(s.updates[1])
        assert reopened.pending()==('dev_loss_checkpoint','copying_probes')
        accept(reopened,p);accept(reopened,p,'copying_probes')
        assert reopened.pending()==()
        with pytest.raises(EvaluationPending):reopened.require_update(s.updates[1])
    finally:reopened.close()


@pytest.mark.parametrize('fault',['identity','schedule_sha256','step','targets','checkpoint_sha256','event','reject','missing','exception'])
def test_bad_evidence_stops_and_cannot_be_replaced(fixture,fault):
    b,s,p=fixture
    changes={fault:'wrong'} if fault in ('identity','schedule_sha256','step','targets','checkpoint_sha256','event') else {}
    path=evidence(b,p,**changes)
    if fault=='missing':path.unlink()
    def verify(raw,context):
        if fault=='exception':raise ValueError('raw scores fail')
        return fault!='reject'
    with pytest.raises((ValueError,FileNotFoundError)):
        b.accept('dev_loss_checkpoint',path,checkpoint_sha256='a'*64,verify=verify)
    with pytest.raises(EvaluationPending):b.require_update(s.updates[0])
    with pytest.raises(EvaluationPending):b.position()
    assert b.db.execute('SELECT count(*) FROM evidence').fetchone()[0]==0


def test_changed_contract_and_corrupt_evidence_fail(fixture):
    b,s,p=fixture;accept(b,p)
    with pytest.raises(ValueError):EvaluationBarrier(p/'events.sqlite',identity='another-run',schedule=s)
    b.db.execute("UPDATE evidence SET raw=?",(b'{}',))
    with pytest.raises(ValueError):b.require_update(s.updates[0])


def test_boundary_evaluations_cannot_mix_checkpoints(fixture):
    b,s,p=fixture
    accept(b,p);b.completed_update(s.updates[0]);accept(b,p);b.completed_update(s.updates[1])
    accept(b,p)
    path=evidence(b,p,'copying_probes',checkpoint_sha256='b'*64)
    with pytest.raises(ValueError,match='same checkpoint'):
        b.accept('copying_probes',path,checkpoint_sha256='b'*64,verify=lambda raw,context:True)
    with pytest.raises(EvaluationPending):b.position()


def test_boolean_cannot_impersonate_zero_step(fixture):
    b,s,p=fixture
    path=evidence(b,p,step=False)
    with pytest.raises(ValueError,match='Unbound'):
        b.accept('dev_loss_checkpoint',path,checkpoint_sha256='a'*64,verify=lambda raw,context:True)
    with pytest.raises(EvaluationPending):b.require_update(s.updates[0])
