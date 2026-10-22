from pathlib import Path
from types import SimpleNamespace
import hashlib
import numpy as np
import pytest
from slm.restart import checkpoint_binding,state
from slm.restart.evaluation_checkpoint import prepare,BoundLogits
from slm.restart.ledger import Ledger
from slm.restart.monitor import Monitor


@pytest.fixture
def fixture(tmp_path):
    class Schedule:
        sha256='schedule';update_cursors=(0,1);cursor_targets=(0,3)
        def resume_position(self,*,step,cursor,targets):
            if (step,cursor,targets)!=(0,0,0):raise ValueError('position')
            return None
    schedule=Schedule();ledger=Ledger(tmp_path/'ledger','run',target_cap=3,update_cap=1,presentation_cap=1,deadline=100)
    class Backend:
        @staticmethod
        def export(p):return {k:np.array(v,copy=True) for k,v in p.items()}
    expected=dict(tokenizer_hash='tokenizer',code_hash='code',config_hash='config')
    root=(tmp_path/'states').resolve()
    path=checkpoint_binding.save(root,'initial',params={'fixture':np.array([[1.,2.]],np.float32)},moments={},backend=Backend,
        monitor=Monitor(),rng=np.random.default_rng(42),step=0,targets=0,schedule=schedule,ledger=ledger,identity='run',expected=expected)
    pin=state.digest(path/'manifest.json')
    context=dict(identity='run',schedule_sha256='schedule',step=0,targets=0,event='dev_loss_checkpoint',checkpoint_sha256=pin)
    args=dict(checkpoint_root=root,manifest_sha256=pin,identity='run',expected=expected,shapes={'fixture':(1,2)},schedule=schedule,ledger=ledger,context=context)
    yield path,args
    ledger.close()


def test_verified_parameters_are_immutable_and_no_backend_is_loaded(fixture):
    path,args=fixture;p=prepare(path,**args)
    assert p['context']==args['context']
    with pytest.raises(ValueError):p['params']['fixture'][0,0]=2.


@pytest.mark.parametrize('fault',['pin','identity','step','bool','event','code','tail','file','root','alias'])
def test_changed_or_stale_checkpoint_refused(fixture,fault,tmp_path):
    path,a=fixture
    if fault=='pin':a['manifest_sha256']='a'*64
    if fault=='identity':a['identity']='other'
    if fault=='step':a['context']['step']=1
    if fault=='bool':a['context']['step']=False
    if fault=='event':a['context']['event']='final_test'
    if fault=='code':a['expected']['code_hash']='changed'
    if fault=='tail':a['ledger'].reserve('inflight',[('doc',0,1)],now=0)
    if fault=='file':(path/'state.json').write_text('{}')
    if fault=='root':a['checkpoint_root']=tmp_path.resolve()
    if fault=='alias':
        alias=tmp_path/'alias';alias.symlink_to(path,target_is_directory=True);path=alias
    with pytest.raises(ValueError):prepare(path,**a)


def test_backend_parameter_mismatch_or_forward_mutation_rejected(fixture):
    path,args=fixture;prepared=prepare(path,**args)
    class Backend:
        def __init__(self):self.params={k:v.copy() for k,v in prepared['params'].items()};self.mutate=False
        def export_parameters(self):return self.params
        def forward_numpy(self,x,p):
            if self.mutate:self.params['fixture'][0,0]+=1
            return np.zeros((*x.shape,16),np.float32)
    backend=Backend();bound=BoundLogits(prepared,backend);x=np.array([[10]],np.int32)
    bound(x,x>0);assert bound.calls==1
    backend.mutate=True
    with pytest.raises(ValueError):bound(x,x>0)
    assert bound.calls==1
    with pytest.raises(ValueError):BoundLogits(prepared,backend)
