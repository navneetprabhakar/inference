"""Fixed-gradient optimizer resume integration; no neural model/forward."""
import hashlib
import numpy as np
import pytest
from slm.restart import checkpoint_binding as checkpoint
from slm.restart.ledger import Ledger,BudgetError
from slm.restart.monitor import Monitor
from slm.restart.schedule import ScheduledUpdate
from slm.restart.update_step import execute
from slm.restart.pilot_barrier import PilotBarrier

@pytest.mark.parametrize('name',['mlx','torch'])
def test_resume_next_update_and_later_charges_are_preserved(tmp_path,name):
    if name=='mlx':
        import mlx.core as mx
        from slm.backends import mlx_backend as real
        array=lambda x:mx.array(np.asarray(x,dtype=np.float32))
    else:
        import torch
        from slm.backends import torch_backend as real
        array=lambda x:torch.tensor(x,dtype=torch.float32)
    class Backend:
        export=staticmethod(real.export);adamw=staticmethod(real.adamw)
        STABLE_LOSS_IMPLEMENTATION=real.STABLE_LOSS_IMPLEMENTATION
        @staticmethod
        def value_and_grad(*args,**kwargs):return array(2.),{'fixture':array([[.1,.2]])}
    class Store:
        def microbatch(self,spans):
            n=sum(b-a for _,a,b in spans)
            return np.zeros((1,n),np.int32),np.ones((1,n),np.int32),np.ones((1,n),np.float32),np.ones((1,n),bool),list(spans)
    updates=tuple(ScheduledUpdate(i,1,3,3*i,2e-4,(),((('a',0,3),),)) for i in (1,2))
    class Schedule:
        sha256=hashlib.sha256(b'fixed arithmetic fixture schedule').hexdigest()
        update_cursors=(0,1,2);cursor_targets=(0,3,6)
        def resume_position(self,*,step,cursor,targets):
            if self.update_cursors[step]!=cursor or self.cursor_targets[cursor]!=targets:raise ValueError('cursor')
            return updates[step] if step<2 else None
    schedule=Schedule();expected=dict(tokenizer_hash='fixture',code_hash='fixture-code',config_hash='scalar-only')
    ledger=Ledger(tmp_path/'ledger.sqlite','fixture-only',target_cap=9,update_cap=3,presentation_cap=3,deadline=100)
    params={'fixture':array([[1.,2.]])};rng=np.random.default_rng(42);rng.integers(0,100,size=11)
    barrier=PilotBarrier(tmp_path/'pilot.sqlite',run_identity='fixture',schedule_hash='fixture',evaluation_hash='fixture')
    # Isolate checkpoint arithmetic and exposure accounting here. The real
    # EvaluationBarrier independently refuses this unapproved replay; automatic
    # interruption recovery is not implemented or authorized by this fixture.
    class CheckpointArithmeticOnly:
        def require_update(self, update):pass
        def require_monitor(self, monitor):pass
        def completed_update(self, update):pass
    common=dict(evaluation_barrier=CheckpointArithmeticOnly(),pilot_barrier=barrier,store=Store(),ledger=ledger,backend=Backend,backend_name=name,config=None,now=0)
    first=execute(updates[0],params=params,moments={},monitor=Monitor(),reservation_id='first',**common)
    path=checkpoint.save(tmp_path/'states','step1',params=first['params'],moments=first['moments'],backend=Backend,
        monitor=first['monitor'],rng=rng,step=1,targets=3,schedule=schedule,ledger=ledger,identity='fixture',expected=expected)
    reference=execute(updates[1],params=first['params'],moments=first['moments'],monitor=first['monitor'],reservation_id='reference-next',**common)
    restored=checkpoint.restore(path,shapes={'fixture':(1,2)},schedule=schedule,ledger=ledger,identity='fixture',expected=expected)
    assert restored['charged_work_after_checkpoint']=={'later_updates_reserved':1,'later_targets_reserved':3,'refunds':0}
    np.testing.assert_array_equal(rng.integers(0,10000,size=50),restored['rng'].integers(0,10000,size=50))
    a=restored['arrays'];p={'fixture':array(a['parameter:fixture'])};m={'fixture':(array(a['first_moment:fixture']),array(a['second_moment:fixture']))}
    resumed=execute(restored['next_update'],params=p,moments=m,monitor=restored['monitor'],reservation_id='charged-replay',**common)
    for key,v in Backend.export(reference['params']).items():np.testing.assert_array_equal(v,Backend.export(resumed['params'])[key])
    for ix in (0,1):
        np.testing.assert_array_equal(Backend.export({'x':reference['moments']['fixture'][ix]})['x'],Backend.export({'x':resumed['moments']['fixture'][ix]})['x'])
    assert resumed['metrics']==reference['metrics'] and resumed['monitor']==reference['monitor']
    assert ledger.totals()=={'updates_reserved':3,'targets_reserved':9,'updates_completed':3}
    with pytest.raises(BudgetError):ledger.reserve('extra',[('a',0,1)],now=0)
    # Corrupt logical ledger history even though checkpoint files remain intact.
    ledger.db.execute("UPDATE exposures SET last=2 WHERE reservation='first'")
    with pytest.raises(BudgetError):checkpoint.restore(path,shapes={'fixture':(1,2)},schedule=schedule,ledger=ledger,identity='fixture',expected=expected)
    ledger.close();barrier.close()
