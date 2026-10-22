import json
from types import SimpleNamespace
import numpy as np
import pytest
from slm.restart import checkpoint_binding,state,final_checkpoint
from slm.restart.checkpoint_catalog import Catalog
from slm.restart.evaluation_quality import EvaluationQualityBarrier
from slm.restart.ledger import Ledger
from slm.restart.monitor import Monitor
from slm.restart.schedule import ScheduledUpdate
from slm.restart.supervisor import TimeBudget


@pytest.fixture
def fixture(tmp_path):
    class Schedule:
        sha256='schedule';target_cap=3000000;update_cursors=(0,1,2);cursor_targets=(0,2000000,3000000)
        updates=(ScheduledUpdate(1,1,2000000,2000000,.001,('dev_loss_checkpoint',),()),
                 ScheduledUpdate(2,1,1000000,3000000,.001,('dev_loss_checkpoint',),()))
        def resume_position(self,*,step,cursor,targets):
            if self.update_cursors[step]!=cursor or self.cursor_targets[cursor]!=targets:raise ValueError('position')
    class Backend:
        @staticmethod
        def export(p):return {k:np.array(v,copy=True) for k,v in p.items()}
    schedule=Schedule();root=tmp_path/'checkpoints';root.mkdir()
    ledger=Ledger(tmp_path/'ledger','run',target_cap=3000000,update_cap=2,presentation_cap=1,deadline=1000)
    quality=EvaluationQualityBarrier(tmp_path/'quality',identity='run',schedule=schedule)
    expected=dict(code_hash='code',config_hash='config',tokenizer_hash='tokenizer')
    catalog=Catalog(tmp_path/'catalog',root=root,identity='run',expected=expected,shapes={'fixture':(1,2)},schedule=schedule,ledger=ledger)
    clock=TimeBudget(tmp_path/'time',identity='run',seconds_cap=100,deadline_utc=1000);clock.reserve(10,100)
    dev_verify=lambda raw,context:{'nll':json.loads(raw)['metrics']['nll']}
    copy_verify=lambda raw,context:json.loads(raw)['metrics']
    paths=[]
    for step,nll in enumerate((3.,2.,2.01)):
        if step:
            update=schedule.updates[step-1]
            ledger.reserve(str(step),[('doc'+str(step),0,update.targets)],now=100);ledger.complete(str(step));quality.completed_update(update)
        params={'fixture':np.array([[float(step),2.]],np.float32)}
        moments={} if step==0 else {'fixture':(np.zeros((1,2),np.float32),np.zeros((1,2),np.float32))}
        monitor=quality.overlay(Monitor(losses=[1.]*step,gradients=[.1]*step))
        path=checkpoint_binding.save(root,'state-'+str(step),params=params,moments=moments,backend=Backend,monitor=monitor,
            rng=np.random.default_rng(42),step=step,targets=schedule.cursor_targets[step],schedule=schedule,ledger=ledger,identity='run',expected=expected)
        pin=catalog.register(path.name);paths.append(path)
        context=dict(identity='run',schedule_sha256='schedule',step=step,targets=schedule.cursor_targets[step],checkpoint_sha256=pin,event='dev_loss_checkpoint')
        raw=tmp_path/'evaluation.json';raw.write_text(json.dumps({'context':context,'metrics':{'nll':nll}}))
        quality.accept('dev_loss_checkpoint',raw,checkpoint_sha256=pin,verify=dev_verify);catalog.score(path.name,quality)
    context['event']='copying_probes';raw.write_text(json.dumps({'context':context,'metrics':{'train_copies':0,'heldout_copies':0}}))
    quality.accept('copying_probes',raw,checkpoint_sha256=pin,verify=copy_verify)
    completion=dict(status='NORMAL_BUDGET_END',step=2,targets=3000000,checkpoint=str(paths[2]),best=catalog.best())
    args=dict(catalog=catalog,quality=quality,pilot=SimpleNamespace(decision=lambda:{'result':{'status':'PILOT_METRIC_RULES_PASS'}}),
              time_budget=clock,dev_verify=dev_verify,copy_verify=copy_verify,now=200)
    yield completion,args,paths
    catalog.close();quality.close();ledger.close();clock.db.close()


def test_best_earlier_checkpoint_selected_without_refunding_later_work(fixture):
    completion,args,paths=fixture;ledger=args['catalog'].args['ledger'];before=ledger.snapshot()
    prepared=final_checkpoint.prepare(completion,**args)
    assert prepared['checkpoint_path']==str(paths[1])
    assert prepared['context']['step']==1 and prepared['context']['targets']==2000000
    assert prepared['termination']['step']==2
    assert prepared['charged_work_after_selected_checkpoint']['later_targets_reserved']==1000000
    assert ledger.snapshot()==before and prepared['retained_ledger_snapshot']==before
    with pytest.raises(ValueError):prepared['params']['fixture'][0,0]=9.


@pytest.mark.parametrize('fault',['selected','score','evidence','copy','terminal','pilot','expired','active','checkpoint','progress','failed'])
def test_invalid_selection_or_training_end_cannot_open_final(fixture,fault):
    completion,args,paths=fixture;quality=args['quality'];catalog=args['catalog']
    if fault=='selected':completion['best']['path']=str(paths[2])
    if fault=='score':catalog.db.execute("UPDATE checkpoints SET nll=.5 WHERE name='state-2'")
    if fault=='evidence':quality.db.execute("UPDATE evidence SET sha256='bad' WHERE step=1")
    if fault=='copy':quality.db.execute("DELETE FROM evidence WHERE event='copying_probes'")
    if fault=='terminal':quality.db.execute("UPDATE barrier SET terminal='development regression'")
    if fault=='pilot':args['pilot']=SimpleNamespace(decision=lambda:None)
    if fault=='expired':args['now']=1000
    if fault=='active':args['time_budget'].settle_elapsed(100)
    if fault=='checkpoint':(paths[1]/'state.json').write_text('{}')
    if fault=='progress':completion['step']=True
    if fault=='failed':completion['status']='FAILED'
    with pytest.raises((ValueError,RuntimeError)):final_checkpoint.prepare(completion,**args)
