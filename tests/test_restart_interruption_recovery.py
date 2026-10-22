import json
from types import SimpleNamespace
import pytest
from slm.restart.interruption_recovery import register,recover
from slm.restart.evaluation_quality import EvaluationQualityBarrier
from slm.restart.evaluation_barrier import EvaluationPending
from slm.restart.schedule import ScheduledUpdate
from slm.restart.supervisor import TimeBudget
from test_restart_evaluation_checkpoint import fixture as checkpoint_fixture

OLD={'host':'fixture','boot_seconds':10,'boot_microseconds':0}
NEW={'host':'fixture','boot_seconds':150,'boot_microseconds':0}

@pytest.fixture
def harness(checkpoint_fixture,tmp_path):
    path,args=checkpoint_fixture;schedule=args['schedule']
    update=ScheduledUpdate(1,1,3,3,.001,(),());schedule.updates=(update,)
    barrier=EvaluationQualityBarrier(tmp_path/'quality',identity='run',schedule=schedule)
    register(barrier,boot_reader=lambda:OLD)
    context=dict(args['context']);f=tmp_path/'initial.json';f.write_text(json.dumps({'context':context}))
    barrier.accept('dev_loss_checkpoint',f,checkpoint_sha256=args['manifest_sha256'],verify=lambda raw,context:{'nll':2.})
    args['ledger'].reserve('crashed-work',[('doc',0,3)],now=0)
    # Simulate committed cursor followed by reboot before the next checkpoint.
    barrier.completed_update(update)
    clock=TimeBudget(tmp_path/'time',identity='run',seconds_cap=100,deadline_utc=1000);clock.reserve(10,100)
    kw={k:v for k,v in args.items() if k!='context'}
    kw.update(checkpoint=path,time_budget=clock,boot_reader=lambda:NEW,now=200)
    yield barrier,kw
    barrier.close();clock.db.close()


def test_reboot_recovery_once_without_refunds(harness):
    b,k=harness;before=k['ledger'].totals();charged=k['time_budget'].charged()
    restored,receipt=recover(b,**k)
    assert b.position()==0 and restored['monitor'].dev==[2.]
    assert receipt['work_after_checkpoint']['later_targets_reserved']==3
    assert k['ledger'].totals()==before and k['time_budget'].charged()==charged
    assert receipt['remaining_automatic_resumes']==0
    with pytest.raises(ValueError,match='consumed'):recover(b,**k)
    with pytest.raises(EvaluationPending):b.position()


@pytest.mark.parametrize('fault',['same_boot','host','future_boot','time_stop','exhausted','expired','quality_stop','checkpoint','past_evaluation'])
def test_ambiguous_or_terminal_interruptions_cannot_resume(harness,fault):
    b,k=harness
    if fault=='same_boot':k['boot_reader']=lambda:OLD
    if fault=='host':k['boot_reader']=lambda:dict(NEW,host='other')
    if fault=='future_boot':k['boot_reader']=lambda:dict(NEW,boot_seconds=201)
    if fault=='time_stop':k['time_budget'].stop('resource failure')
    if fault=='exhausted':k['time_budget'].settle_elapsed(100)
    if fault=='expired':k['now']=1001
    if fault=='quality_stop':b.db.execute("UPDATE barrier SET terminal='copying concern'")
    if fault=='checkpoint':k['manifest_sha256']='a'*64
    if fault=='past_evaluation':b.db.execute("INSERT INTO evidence VALUES (1,'some-event',?,?)",(b'{}','pin'))
    before=k['ledger'].totals()
    with pytest.raises((ValueError,EvaluationPending)):recover(b,**k)
    assert k['ledger'].totals()==before
    with pytest.raises(EvaluationPending):b.position()


def test_only_historical_interrupted_work_is_allowed_after_recovery(harness):
    from slm.restart.interruption_recovery import validate_abandoned_work
    b,k=harness;recover(b,**k)
    ledger=k['ledger'];before=ledger.totals()
    assert validate_abandoned_work(ledger,b,checkpoint_step=0)=={'historical_unfinished_reservations':1,'refunds':0}
    assert ledger.totals()==before
    # New work is separately charged, never included in the historical exception.
    ledger.target_cap=6;ledger.update_cap=2;ledger.presentation_cap=2
    ledger.reserve('new-inflight',[('new-doc',0,1)],now=0)
    with pytest.raises(ValueError,match='New or unaccounted'):
        validate_abandoned_work(ledger,b,checkpoint_step=0)


def test_abandoned_charges_cannot_be_later_marked_complete(harness):
    from slm.restart.interruption_recovery import validate_abandoned_work
    from slm.restart.ledger import BudgetError
    b,k=harness;recover(b,**k)
    k['ledger'].complete('crashed-work')
    with pytest.raises(BudgetError):validate_abandoned_work(k['ledger'],b,checkpoint_step=0)


def test_recovered_checkpoint_evaluation_retains_interrupted_charges(harness):
    import numpy as np
    from slm.restart import checkpoint_binding,state
    from slm.restart.evaluation_checkpoint import prepare
    b,k=harness;restored,_=recover(b,**k);ledger=k['ledger'];before=ledger.totals()
    class Backend:
        @staticmethod
        def export(params):return {name:value.copy() for name,value in params.items()}
    params={name.split(':',1)[1]:value for name,value in restored['arrays'].items() if name.startswith('parameter:')}
    path=checkpoint_binding.save(k['checkpoint_root'],'recovered',params=params,moments={},backend=Backend,
        monitor=restored['monitor'],rng=restored['rng'],step=0,targets=0,schedule=k['schedule'],
        ledger=ledger,identity=k['identity'],expected=k['expected'])
    pin=state.digest(path/'manifest.json')
    context=dict(identity='run',schedule_sha256='schedule',step=0,targets=0,event='dev_loss_checkpoint',checkpoint_sha256=pin)
    args={key:k[key] for key in ('checkpoint_root','identity','expected','shapes','schedule','ledger')}
    args.update(manifest_sha256=pin,context=context)
    with pytest.raises(ValueError,match='quality cursor'):prepare(path,**args)
    prepared=prepare(path,quality=b,**args)
    np.testing.assert_array_equal(prepared['params']['fixture'],params['fixture'])
    assert ledger.totals()==before


def test_worker_restore_progress_consumes_reboot_without_initialization(harness):
    from slm.restart.candidate_worker import restore_progress
    b,k=harness
    root=k['checkpoint_root'];new_root=root.parent/'checkpoints';root.rename(new_root)
    checkpoint=new_root/k['checkpoint'].name
    ticket=dict(phase='pilot-recovery',checkpoint=str(checkpoint),checkpoint_sha256=k['manifest_sha256'],
                identity=k['identity'],output=str(root.parent))
    before=k['ledger'].totals()
    result=restore_progress(ticket,quality=b,pilot=SimpleNamespace(decision=lambda:None),
        config=SimpleNamespace(shapes=lambda:k['shapes']),schedule=k['schedule'],ledger=k['ledger'],expected=k['expected'],
        clock=k['time_budget'],boot_reader=lambda:NEW,now=200)
    assert result['metadata']['step']==0 and b.position()==0 and result['monitor'].dev==[2.]
    assert k['ledger'].totals()==before
    receipt=json.loads((root.parent/'recovery-consumed.json').read_bytes())
    assert receipt['refunds']==0 and receipt['remaining_automatic_resumes']==0
    assert not (root.parent/'initialization-started.json').exists()


def test_recovery_cannot_skip_pilot_acceptance(harness):
    from slm.restart.candidate_worker import restore_progress
    b,k=harness
    with pytest.raises(ValueError,match='pilot acceptance'):
        restore_progress({'phase':'continuation-recovery'},quality=b,pilot=SimpleNamespace(decision=lambda:None),
            config=None,schedule=k['schedule'],ledger=k['ledger'],expected=k['expected'],clock=k['time_budget'])
    assert b.position()==1
    assert b.db.execute('SELECT recovery FROM interruption').fetchone()[0] is None
