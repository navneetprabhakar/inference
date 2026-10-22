import hashlib,json
from types import SimpleNamespace
import numpy as np
import pytest
from slm.common.config import Config
from slm.restart import final_evaluation as final
from slm.restart.evaluation_checkpoint import fingerprint


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    config=Config();path=tmp_path/'checkpoint';path.mkdir();(path/'manifest.json').write_text('{}')
    pin=hashlib.sha256(b'{}').hexdigest();params={'fixture':np.ones((1,2),np.float32)}
    context=dict(identity='run',schedule_sha256='schedule',step=1,targets=2000000,event='final_research_evaluation',checkpoint_sha256=pin)
    prepared=dict(params=params,context=context,parameter_sha256=fingerprint(params),checkpoint_path=str(path),checkpoint_sha256=pin,
        selection={'path':str(path)},termination={'status':'NORMAL_BUDGET_END'},retained_ledger_snapshot={'digest':'ledger'})
    expected={'config_hash':hashlib.sha256(json.dumps(config.to_dict(),sort_keys=True).encode()).hexdigest(),
              'tokenizer_hash':final.PINS['tokenizer-8192/manifest.json']}
    catalog=SimpleNamespace(args={'expected':expected,'ledger':SimpleNamespace(snapshot=lambda:{'digest':'ledger'})})
    clock=SimpleNamespace(deadline=9999999999,cap=129600,charged=lambda:10,terminal=lambda:None)
    kwargs=dict(catalog=catalog,quality=None,pilot=None,time_budget=clock,dev_verify=None,copy_verify=None,heartbeat=lambda:None)
    monkeypatch.setattr(final.numerical_snapshot,'authority',lambda *a:clock.deadline)
    monkeypatch.setattr(final.final_checkpoint,'prepare',lambda *a,**kw:prepared)
    monkeypatch.setattr(final,'inputs',lambda project:{'config':config})
    class Backend:
        def __init__(self,p,c):self.params={k:v.copy() for k,v in p['params'].items()}
        def export_parameters(self):return self.params
        def forward_numpy(self,x,p):return np.zeros((*x.shape,16),np.float32)
    monkeypatch.setattr(final,'_MLX',Backend)
    def execute(**kw):
        kw['heartbeat']();kw['logits'](np.array([[10]],np.int32),np.array([[True]]))
        return {'context':kw['context'],'fixture':True}
    monkeypatch.setattr(final.final_diagnostics,'execute',execute)
    monkeypatch.setattr(final.final_diagnostics,'assess',lambda *a,**kw:{'status':'NARRATIVE_REVIEW_REQUIRED'})
    return tmp_path,kwargs,prepared


def test_native_orchestration_binds_receipt_and_keeps_review_pending(fixture):
    project,kwargs,prepared=fixture
    raw,receipt,assessment=final.evaluate(project,{},**kwargs)
    assert json.loads(raw)['context']==prepared['context']
    assert receipt['result_sha256']==hashlib.sha256(raw).hexdigest()
    assert receipt['forward_calls']==1 and receipt['final_research_pass'] is False
    assert assessment['status']=='NARRATIVE_REVIEW_REQUIRED'


def test_termination_validation_precedes_any_holdout_read(fixture,monkeypatch):
    project,kwargs,_=fixture
    def refuse(*a,**kw):raise ValueError('invalid training end')
    monkeypatch.setattr(final.final_checkpoint,'prepare',refuse)
    monkeypatch.setattr(final,'inputs',lambda *a:pytest.fail('Holdout must remain closed'))
    with pytest.raises(ValueError,match='training end'):final.evaluate(project,{},**kwargs)


@pytest.mark.parametrize('fault',['config','clock','ledger','checkpoint'])
def test_changed_final_execution_state_is_refused(fixture,monkeypatch,fault):
    project,kwargs,prepared=fixture
    if fault=='config':kwargs['catalog'].args['expected']['config_hash']='changed'
    if fault=='clock':kwargs['time_budget'].terminal=lambda:'resource failure'
    if fault=='ledger':kwargs['catalog'].args['ledger'].snapshot=lambda:{'digest':'changed'}
    if fault=='checkpoint':(project/'checkpoint/manifest.json').write_text('changed')
    with pytest.raises(ValueError):final.evaluate(project,{},**kwargs)


def test_ticket_selection_mismatch_keeps_holdout_closed(fixture,monkeypatch):
    project,kwargs,_=fixture
    monkeypatch.setattr(final,'inputs',lambda *a:pytest.fail('Changed selection must not open holdout'))
    with pytest.raises(ValueError,match='selection'):
        final.evaluate(project,{},selection={'path':'other-checkpoint'},**kwargs)
