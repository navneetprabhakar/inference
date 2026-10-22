import json
from pathlib import Path
import numpy as np
import pytest
from slm.restart.numerical_integrity import run
from slm.restart.numerical_results import aggregate
from slm.restart.state import publish


def setup(tmp_path):
    metadata=dict(step=0,targets=0,data_cursor=0,rng={'fixture':True},monitor={},ledger_digest='fixture',tokenizer_hash='fixture',code_hash='fixture',config_hash='fixture')
    checkpoint=publish(tmp_path/'state','complete',{'fixture':np.ones(2,np.float32)},metadata,identity='arithmetic-fixture')
    events=[dict(id=f'{b}:{i}',backend=b,kind='optimizer',positions=32,optimizer_updates=1) for b in ('mlx','torch') for i in range(9)]
    return dict(fit_losses={b:{'initial':4.,'after_eight_updates':2.} for b in ('mlx','torch')},work_events=events,supervisor={'status':'PASS','observed_seconds':1.,'charged_active_seconds':10.},complete_checkpoint=checkpoint,checkpoint_identity='arithmetic-fixture',checkpoint_expected={'code_hash':'fixture'},output_root=tmp_path)


def test_six_integrity_case_ids_with_actual_storage_and_monitor(tmp_path):
    result=run(**setup(tmp_path));assert all(v['passed'] for v in result['cases'].values())
    design=json.loads((Path(__file__).resolve().parents[1]/'restart/execution-v1/numerical-suite-design-v1.json').read_text())
    assert set(result['cases'])=={c['id'] for c in design['cases'] if c['group']=='fit_and_integrity'}


@pytest.mark.parametrize('fault,case',[('fit','toy_fit_loss_drop_50_percent'),('updates','aggregate_toy_update_cap'),('positions','aggregate_toy_target_cap'),('time','aggregate_toy_walltime_cap')])
def test_bad_fit_or_budget_fails(tmp_path,fault,case):
    e=setup(tmp_path)
    if fault=='fit':e['fit_losses']['torch']['after_eight_updates']=2.01
    if fault=='updates':e['work_events'].pop()
    if fault=='positions':e['work_events'][0]['positions']=100001
    if fault=='time':e['supervisor']['observed_seconds']=1800.1
    assert not run(**e)['cases']['fit_and_integrity:'+case]['passed']


def test_duplicate_reservation_is_invalid(tmp_path):
    e=setup(tmp_path);e['work_events'].append(e['work_events'][0])
    with pytest.raises(ValueError):run(**e)


def test_aggregation_requires_every_case_and_rejects_duplicates():
    ids=[str(i) for i in range(40)];group={'cases':{i:{'passed':True} for i in ids}}
    assert aggregate(ids,[group])['status']=='NUMERICAL_CASE_RESULTS_PASS'
    group['cases'].pop('39');assert aggregate(ids,[group])['missing']==['39']
    group['cases']['0']['passed']=False;assert aggregate(ids,[group])['failed']==['0']
    with pytest.raises(ValueError):aggregate(ids,[group,group])
    group['cases']['unknown']={'passed':True}
    with pytest.raises(ValueError):aggregate(ids,[group])
