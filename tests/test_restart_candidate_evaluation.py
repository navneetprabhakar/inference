import hashlib,json,time
from pathlib import Path
import numpy as np
import pytest
from slm.restart import candidate_evaluation as evaluator
from slm.restart.evaluation_checkpoint import fingerprint
from slm.restart.numerical_prerequisites import PINS
from test_restart_development_loss import fixture as loss_fixture


@pytest.fixture
def harness(loss_fixture,monkeypatch):
    store,context,root=loss_fixture
    real=evaluator.inputs(Path(__file__).resolve().parents[1],'dev_loss_checkpoint')
    config=real['config'];params={'fixture':np.array([[1.]],np.float32)};calls=[]
    monkeypatch.setattr(evaluator.numerical_snapshot,'authority',lambda *a:time.time()+100)
    monkeypatch.setattr(evaluator,'inputs',lambda *a:{'config':config,'tokenizer':None,'dev_store':store})
    def prepare(*args,**kwargs):
        calls.append('checkpoint')
        return {'params':params,'parameter_sha256':fingerprint(params),'context':context}
    monkeypatch.setattr(evaluator,'prepare',prepare)
    class Backend:
        def __init__(self,*args):calls.append('backend')
        def export_parameters(self):return params
        def forward_numpy(self,x,p):calls.append('forward');return np.zeros((*x.shape,16),np.float32)
    monkeypatch.setattr(evaluator,'_MLX',Backend)
    args=dict(checkpoint_root=root,manifest_sha256='a'*64,identity='fixture',expected={
        'config_hash':hashlib.sha256(json.dumps(config.to_dict(),sort_keys=True).encode()).hexdigest(),
        'tokenizer_hash':PINS['tokenizer-8192/manifest.json']},schedule=None,ledger=None,context=context,
        deadline=time.time()+50,heartbeat=lambda:None)
    return root,args,calls


def test_raw_result_receipt_is_bound_to_validated_checkpoint(harness):
    root,args,calls=harness
    raw,receipt=evaluator.evaluate(root,root/'fixture',**args)
    assert calls[:2]==['checkpoint','backend'] and calls.count('forward')==3
    assert receipt['result_sha256']==hashlib.sha256(raw).hexdigest()
    assert receipt['forward_calls']==3 and receipt['metrics']['nll']==pytest.approx(np.log(16))


@pytest.mark.parametrize('fault',['deadline','config','tokenizer','checkpoint'])
def test_refusal_precedes_backend_allocation(harness,monkeypatch,fault):
    root,args,calls=harness
    if fault=='deadline':args['deadline']=time.time()-1
    if fault=='config':args['expected']['config_hash']='bad'
    if fault=='tokenizer':args['expected']['tokenizer_hash']='bad'
    if fault=='checkpoint':
        def fail(*a,**kw):raise ValueError('bad checkpoint')
        monkeypatch.setattr(evaluator,'prepare',fail)
    with pytest.raises(ValueError):evaluator.evaluate(root,root/'fixture',**args)
    assert 'backend' not in calls and 'forward' not in calls


def test_native_constructor_rejects_wrong_shapes_before_loading_mlx():
    from slm.common.config import Config
    with pytest.raises(ValueError):evaluator._MLX({'params':{}},Config())
