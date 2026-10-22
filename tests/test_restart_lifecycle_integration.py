"""Lifecycle integration with real stores/barriers/checkpoints and synthetic math.

No neural forward or optimizer executes. Fixtures stand in for expensive scored
outputs; numerical and raw-output verifiers have their own controls.
"""
import copy,json,time,hashlib
from types import SimpleNamespace
import numpy as np
import pytest
from slm.restart import candidate_evaluation,checkpoint_binding,evaluation_checkpoint,final_checkpoint,update_step
from slm.restart.candidate_loop import Loop
from slm.restart.checkpoint_catalog import Catalog
from slm.restart.evaluation_quality import EvaluationQualityBarrier
from slm.restart.ledger import Ledger
from slm.restart.monitor import Monitor
from slm.restart.pilot_barrier import PilotBarrier
from slm.restart.pilot_evidence import Measurements
from slm.restart.schedule import ScheduledUpdate
from slm.restart.supervisor import TimeBudget
from slm.restart.evaluation_snapshot import MANIFEST_SHA256


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    class Schedule:
        sha256='lifecycle';target_cap=3000000
        update_cursors=tuple(range(7));cursor_targets=tuple(i*500000 for i in range(7))
        updates=tuple(ScheduledUpdate(i,1,500000,i*500000,.001,
            ('dev_loss_checkpoint','full_development_diagnostics','pilot_continuation_gate') if i==4 else ('dev_loss_checkpoint',),
            (((f'doc-{i}',0,500000),),)) for i in range(1,7))
        def resume_position(self,*,step,cursor,targets):
            if cursor!=step or self.cursor_targets[cursor]!=targets:raise ValueError('fixture cursor mismatch')
            return self.updates[step] if step<len(self.updates) else None
    class Backend:
        @staticmethod
        def export(params):return {k:np.array(v,copy=True) for k,v in params.items()}
    schedule=Schedule();root=tmp_path/'checkpoints';root.mkdir()
    expected=dict(code_hash='code',config_hash='config',tokenizer_hash='tokenizer')
    ledger=Ledger(tmp_path/'ledger','run',target_cap=schedule.target_cap,update_cap=6000,presentation_cap=3,deadline=9999999999)
    quality=EvaluationQualityBarrier(tmp_path/'quality',identity='run',schedule=schedule)
    pilot=PilotBarrier(tmp_path/'pilot',run_identity='run',schedule_hash=schedule.sha256,evaluation_hash=MANIFEST_SHA256)
    measurements=Measurements(tmp_path/'measurements',identity='run',schedule=schedule)
    catalog=Catalog(tmp_path/'catalog',root=root,identity='run',expected=expected,shapes={'fixture':(1,2)},schedule=schedule,ledger=ledger)
    clock=TimeBudget(tmp_path/'clock',identity='run',seconds_cap=129600,deadline_utc=9999999999);clock.reserve(10,100)
    events=[]
    def computation(update,**kw):
        events.append(('compute',update.step));quality.require_update(update);quality.require_monitor(kw['monitor'])
        pilot.require_update(start_targets=update.cumulative_targets-update.targets,end_targets=update.cumulative_targets)
        ledger.reserve(kw['reservation_id'],[span for micro in update.microbatches for span in micro],now=100)
        monitor=copy.deepcopy(kw['monitor']);monitor.update(loss=1.,gradient_norm=.1,update_ratio=.001,targets=update.cumulative_targets,all_state_finite=True)
        ledger.complete(kw['reservation_id']);quality.completed_update(update);clock.settle_elapsed(update.step*200)
        return dict(params={'fixture':np.array([[float(update.step),2.]],np.float32)},
            moments={'fixture':(np.zeros((1,2),np.float32),np.zeros((1,2),np.float32))},monitor=monitor,
            step=update.step,targets=update.cumulative_targets,metrics={'synthetic_control':True})
    monkeypatch.setattr(update_step,'execute',computation)
    nll=[3.,2.9,2.8,2.7,2.6,2.65,2.66]
    def evaluate(project,path,**kw):
        context=kw['context'];event=context['event'];step=context['step'];events.append(('evaluate',step,event))
        prepared=evaluation_checkpoint.prepare(path,checkpoint_root=kw['checkpoint_root'],manifest_sha256=kw['manifest_sha256'],
            identity=kw['identity'],expected=kw['expected'],shapes={'fixture':(1,2)},schedule=schedule,ledger=ledger,context=context,quality=quality)
        metrics={'nll':nll[step]} if event=='dev_loss_checkpoint' else (
            {'train_nll':2.5,'dev_nll':nll[step],'grammar':.9,'grounded':.8,'degenerate_outputs':0} if event=='full_development_diagnostics'
            else {'train_copies':0,'heldout_copies':0})
        payload=dict(context=context,metrics=metrics)
        if event=='dev_loss_checkpoint':payload['metrics']=dict(metrics,targets=200000)
        if event=='full_development_diagnostics':
            payload.update(grammar={'outputs':[{}]*200},grounded={'outputs':[{}]*100},narratives={'outputs':[{}]*100})
        raw=json.dumps(payload).encode()
        return raw,{'checkpoint_sha256':kw['manifest_sha256'],'result_sha256':hashlib.sha256(raw).hexdigest(),
            'parameter_sha256':prepared['parameter_sha256'],'metrics':metrics,'forward_calls':1,'evaluation_seconds':0.}
    monkeypatch.setattr(candidate_evaluation,'evaluate',evaluate)
    def verifier(event):
        def verify(raw,context):
            p=json.loads(raw)
            if p['context']!=context:raise ValueError('fixture mixed context')
            return {k:v for k,v in p['metrics'].items() if k!='targets'}
        return verify
    common=dict(project=tmp_path,output=tmp_path,identity='run',expected=expected,config=None,schedule=schedule,store=None,
        ledger=ledger,quality=quality,pilot=pilot,catalog=catalog,measurements=measurements,time_budget=clock,backend=Backend,
        heartbeat=lambda:None,experiment_start=time.time()-2000)
    def make(restored=None):
        if restored is None:progress=dict(params={'fixture':np.ones((1,2),np.float32)},moments={},monitor=Monitor(),rng=np.random.default_rng(42),step=0,targets=0)
        else:
            a=restored['arrays'];progress=dict(params={'fixture':a['parameter:fixture']},
                moments={} if restored['metadata']['step']==0 else {'fixture':(a['first_moment:fixture'],a['second_moment:fixture'])},monitor=quality.overlay(restored['monitor']),
                rng=restored['rng'],step=restored['metadata']['step'],targets=restored['metadata']['targets'])
        loop=Loop(**common,**progress);monkeypatch.setattr(loop,'verifier',verifier);return loop
    yield make,common,events,verifier
    for h in (ledger,quality,pilot,catalog,measurements):h.close()
    clock.db.close()


def test_pilot_continuation_and_final_selection_share_durable_state(fixture):
    make,c,events,verify=fixture;pilot_loop=make();pilot_result=pilot_loop.run()
    assert pilot_result['status']=='PILOT_PASS' and pilot_result['targets']==2000000
    assert c['pilot'].decision()['result']['status']=='PILOT_METRIC_RULES_PASS'
    assert not any(event==('compute',5) for event in events)
    restored=checkpoint_binding.restore(pilot_result['checkpoint'],**c['catalog'].args)
    continued=make(restored);continued.checkpoint_path=pilot_loop.checkpoint_path
    result=continued.run(stop_after_pilot=False)
    assert result['status']=='NORMAL_BUDGET_END' and result['targets']==3000000
    assert c['ledger'].totals()=={'updates_reserved':6,'targets_reserved':3000000,'updates_completed':6}
    prepared=final_checkpoint.prepare(result,catalog=c['catalog'],quality=c['quality'],pilot=c['pilot'],time_budget=c['time_budget'],
        dev_verify=verify('dev_loss_checkpoint'),copy_verify=verify('copying_probes'))
    assert prepared['context']['step']==4 and prepared['termination']['step']==6
    assert prepared['charged_work_after_selected_checkpoint']['later_targets_reserved']==1000000
    assert events.index(('evaluate',0,'dev_loss_checkpoint'))<events.index(('compute',1))
    assert events.index(('evaluate',4,'full_development_diagnostics'))<events.index(('compute',5))


def recover_fixture(c,path):
    from slm.restart.interruption_recovery import register,recover
    register(c['quality'],boot_reader=lambda:{'host':'fixture','boot_seconds':1,'boot_microseconds':0})
    return recover(c['quality'],checkpoint=path,checkpoint_root=c['catalog'].root,
        manifest_sha256=__import__('slm.restart.state',fromlist=['digest']).digest(path/'manifest.json'),
        **c['catalog'].args,time_budget=c['time_budget'],
        boot_reader=lambda:{'host':'fixture','boot_seconds':2,'boot_microseconds':0})[0]


def test_recovery_reconciles_accepted_dev_score_without_new_evaluation(fixture,monkeypatch):
    make,c,events,verify=fixture;loop=make();original=c['catalog'].score
    def interrupted(*a):raise OSError('simulated reboot after evidence commit')
    monkeypatch.setattr(c['catalog'],'score',interrupted)
    with pytest.raises(OSError):loop.evaluate_pending()
    assert c['quality'].pending()==()
    assert c['catalog'].db.execute('SELECT nll FROM checkpoints').fetchone()[0] is None
    monkeypatch.setattr(c['catalog'],'score',original)
    resumed=make(recover_fixture(c,loop.checkpoint_path));resumed.checkpoint_path=loop.checkpoint_path
    resumed.evaluate_pending()
    assert c['catalog'].best()['dev_nll']==3.
    assert events.count(('evaluate',0,'dev_loss_checkpoint'))==1
    result=resumed.run(stop_after_pilot=False)
    assert final_checkpoint.prepare(result,catalog=c['catalog'],quality=c['quality'],pilot=c['pilot'],time_budget=c['time_budget'],
        dev_verify=verify('dev_loss_checkpoint'),copy_verify=verify('copying_probes'))['context']['step']==4


@pytest.mark.parametrize('fault',[None,'missing_receipt','changed_raw'])
def test_recovery_reuses_complete_unaccepted_outputs_without_regeneration(fixture,monkeypatch,fault):
    make,c,events,_=fixture;loop=make();original=c['quality'].accept
    def interrupted(*a,**kw):raise OSError('simulated reboot after output publication')
    monkeypatch.setattr(c['quality'],'accept',interrupted)
    with pytest.raises(OSError):loop.evaluate_pending()
    path=loop.checkpoint_path;stem=path.name+'-dev_loss_checkpoint'
    if fault=='missing_receipt':(loop.output/(stem+'-receipt.json')).unlink()
    if fault=='changed_raw':
        target=loop.output/(stem+'.json');payload=json.loads(target.read_bytes());payload['metrics']['nll']=.1;target.write_text(json.dumps(payload))
    monkeypatch.setattr(c['quality'],'accept',original)
    resumed=make(recover_fixture(c,path));resumed.checkpoint_path=path
    if fault is None:
        resumed.evaluate_pending()
        assert c['quality'].pending()==() and c['catalog'].best()['dev_nll']==3.
    else:
        with pytest.raises(ValueError):resumed.evaluate_pending()
        assert c['quality'].pending()==('dev_loss_checkpoint',)
    assert events.count(('evaluate',0,'dev_loss_checkpoint'))==1
    assert c['catalog'].db.execute('SELECT count(*) FROM checkpoints').fetchone()[0]==1
