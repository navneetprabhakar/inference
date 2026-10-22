"""Transaction tests use fixed scalar gradients, no neural forward or initialization."""
import numpy as np
import json
from types import SimpleNamespace
from slm.restart.evaluation_barrier import EvaluationPending
from slm.restart.evaluation_quality import EvaluationQualityBarrier as EvaluationBarrier
import pytest
from slm.restart.ledger import Ledger,BudgetError
from slm.restart.monitor import Monitor,StopRun
from slm.restart.schedule import ScheduledUpdate
from slm.restart.update_step import execute
from slm.restart.pilot_barrier import PilotBarrier

@pytest.fixture(params=['mlx','torch'])
def setup(request,tmp_path):
    name=request.param
    if name=='mlx':
        import mlx.core as mx
        from slm.backends import mlx_backend as real
        array=lambda v:mx.array(v,dtype=mx.float32)
    else:
        import torch
        from slm.backends import torch_backend as real
        array=lambda v:torch.tensor(v,dtype=torch.float32)
    ledger=Ledger(tmp_path/'ledger.sqlite','fixed-arithmetic-only',target_cap=3,update_cap=1,presentation_cap=1,deadline=100)
    barrier=PilotBarrier(tmp_path/'pilot.sqlite',run_identity='fixture',schedule_hash='fixture',evaluation_hash='fixture')
    calls=[]
    class Store:
        def microbatch(self,spans):
            assert ledger.totals()['targets_reserved']==3
            calls.append('read');n=spans[0][2]-spans[0][1]
            return np.zeros((1,n),np.int32),np.ones((1,n),np.int32),np.ones((1,n),np.float32),np.ones((1,n),bool),list(spans)
    class Backend:
        STABLE_LOSS_IMPLEMENTATION=real.STABLE_LOSS_IMPLEMENTATION
        export=staticmethod(real.export)
        adamw=staticmethod(real.adamw)
        @staticmethod
        def value_and_grad(*args,**kwargs):
            assert ledger.totals()['targets_reserved']==3
            calls.append('gradient')
            return array(2.),{'fixture':array([[.1,.2]])}
    params={'fixture':array([[1.,2.]])}
    update=ScheduledUpdate(1,1,3,3,2e-4,(),((('a',0,1),),(('b',0,2),)))
    evaluations=EvaluationBarrier(tmp_path/'evaluations.sqlite',identity='fixture',schedule=SimpleNamespace(updates=(update,),sha256='fixture'))
    raw=tmp_path/'initial.json'
    raw.write_text(json.dumps({'context':{'identity':'fixture','schedule_sha256':'fixture','step':0,'targets':0,'event':'dev_loss_checkpoint','checkpoint_sha256':'a'*64}}))
    evaluations.accept('dev_loss_checkpoint',raw,checkpoint_sha256='a'*64,verify=lambda raw,context:{"nll":2.})
    kwargs=dict(store=Store(),ledger=ledger,monitor=evaluations.overlay(Monitor()),params=params,moments={},backend=Backend,
                backend_name=name,config=None,reservation_id='1',now=0,pilot_barrier=barrier,evaluation_barrier=evaluations)
    yield update,kwargs,calls,array
    ledger.close();barrier.close();evaluations.close()


def test_real_optimizer_transaction_commits_after_reservation(setup):
    update,k,calls,_=setup;before=k['backend'].export(k['params'])
    result=execute(update,**k)
    assert calls==['read','gradient','read','gradient']
    assert result['step']==1 and result['targets']==3
    assert result['metrics']['supervised_targets']==3 and result['metrics']['microbatches']==2
    assert len(result['monitor'].losses)==1 and k['monitor'].losses==[]
    np.testing.assert_array_equal(k['backend'].export(k['params'])['fixture'],before['fixture'])
    assert k['ledger'].totals()=={'updates_reserved':1,'targets_reserved':3,'updates_completed':1}


def test_computation_failure_retains_charge_and_blocks_retry(setup):
    update,k,calls,array=setup
    k['backend'].value_and_grad=staticmethod(lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('fixture failure')))
    with pytest.raises(RuntimeError,match='fixture failure'):execute(update,**k)
    assert k['ledger'].totals()=={'updates_reserved':1,'targets_reserved':3,'updates_completed':0}
    with pytest.raises(StopRun):execute(update,**k)
    assert calls==['read']


def test_budget_rejection_occurs_before_data_or_computation(setup):
    update,k,calls,_=setup;k['ledger'].reserve('already-charged',[('z',0,3)],now=0)
    with pytest.raises(BudgetError):execute(update,**k)
    assert calls==[]


def test_nonfinite_candidate_never_marked_complete(setup):
    update,k,calls,array=setup
    k['backend'].adamw=staticmethod(lambda *a,**kw:({'fixture':array([[float('nan'),2.]])},{'fixture':(array([[0.,0.]]),array([[0.,0.]]))}))
    with pytest.raises(ValueError,match='Invalid proposed'):execute(update,**k)
    assert k['ledger'].totals()['updates_completed']==0 and k['monitor'].terminal


def test_quality_stop_rejects_finite_candidate_without_completion(setup):
    update,k,calls,array=setup;k['monitor'].update_streak=2
    before=k['backend'].export(k['params'])
    k['backend'].adamw=staticmethod(lambda *a,**kw:({'fixture':array([[2.,4.]])},{'fixture':(array([[0.,0.]]),array([[0.,0.]]))}))
    with pytest.raises(StopRun,match='parameter update spike'):execute(update,**k)
    assert k['ledger'].totals()['updates_completed']==0 and k['monitor'].terminal
    np.testing.assert_array_equal(k['backend'].export(k['params'])['fixture'],before['fixture'])


def test_persistent_pilot_failure_blocks_before_reservation(setup):
    from test_restart_pilot_gate import evidence
    from slm.restart.pilot_gate import PilotRejected
    update,k,calls,_=setup;e=evidence();e['dev_records'][-1]['nll']=4.
    k['pilot_barrier'].decide(e,checkpoint_sha256='a'*64)
    with pytest.raises(PilotRejected):execute(update,**k)
    assert calls==[] and k['ledger'].totals()['updates_reserved']==0


def test_missing_evaluation_blocks_before_reservation(setup):
    update,k,calls,_=setup
    k['evaluation_barrier'].db.execute('DELETE FROM evidence')
    with pytest.raises(EvaluationPending):execute(update,**k)
    assert calls==[] and k['ledger'].totals()['updates_reserved']==0
