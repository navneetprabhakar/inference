"""Comparison harness sensitivity; actual storage integration tested separately."""
import copy,json
from pathlib import Path
import numpy as np
import pytest
from slm.restart.numerical_checkpoint import run


def captures():
    arrays={p+':fixture':np.array([.1,.2],np.float32) for p in ('parameter','first_moment','second_moment')}
    rng=np.random.default_rng(42);state=copy.deepcopy(rng.bit_generator.state);draws=rng.integers(0,1000,50)
    meta=dict(step=7,targets=224,data_cursor=7,monitor={'losses':[2.]*7,'gradients':[.5]*7},rng=state,tokenizer_hash='fixture',code_hash='fixture',config_hash='fixture',schedule_hash='fixture',ledger_digest='fixture',ledger_snapshot={'fixture':True})
    c=dict(saved_arrays=arrays,restored_arrays=copy.deepcopy(arrays),saved_metadata=meta,restored_metadata=copy.deepcopy(meta),expected_rng_draws=draws,restored_rng_draws=draws.copy(),next_update_step=8,
        ledger_before_restore={'updates_reserved':8,'targets_reserved':256,'updates_completed':8},ledger_after_restore={'updates_reserved':8,'targets_reserved':256,'updates_completed':8},ledger_after_replay={'updates_reserved':9,'targets_reserved':288,'updates_completed':9},charged_work_after_checkpoint={'later_updates_reserved':1,'later_targets_reserved':32,'refunds':0},replay_targets=32,
        reference_next_arrays=copy.deepcopy(arrays),replayed_next_arrays=copy.deepcopy(arrays),reference_next_metadata=copy.deepcopy(meta)|{'step':8,'targets':256,'data_cursor':8},replayed_next_metadata=copy.deepcopy(meta)|{'step':8,'targets':256,'data_cursor':8})
    return {k:copy.deepcopy(c) for k in ('mlx','torch')}


def test_six_comparison_ids_match_contract():
    r=run(captures());assert all(c['passed'] for c in r['cases'].values())
    p=Path(__file__).resolve().parents[1]/'restart/execution-v1/numerical-suite-design-v1.json'
    assert set(r['cases'])=={x['id'] for x in json.loads(p.read_text())['cases'] if x['group']=='checkpoint_resume'}


@pytest.mark.parametrize('fault,case',[('parameter','parameter_roundtrip'),('moment','moment_roundtrip'),('rng','data_rng_roundtrip'),('cursor','monitor_schedule_roundtrip'),('refund','ledger_prefix_no_refund'),('replay','resumed_next_update_equivalence')])
def test_faults_cannot_pass(fault,case):
    c=captures();r=c['mlx']
    if fault=='parameter':r['restored_arrays']['parameter:fixture'][0]+=.1
    if fault=='moment':r['restored_arrays']['second_moment:fixture'][0]+=.1
    if fault=='rng':r['restored_rng_draws'][0]+=1
    if fault=='cursor':r['restored_metadata']['data_cursor']=0
    if fault=='refund':r['ledger_after_restore']['targets_reserved']-=32
    if fault=='replay':r['replayed_next_arrays']['parameter:fixture'][0]+=.1
    assert not run(c)['cases']['checkpoint_resume:'+case]['passed']


def test_missing_optimizer_tensor_fails_closed():
    c=captures();del c['mlx']['restored_arrays']['first_moment:fixture']
    with pytest.raises(ValueError):run(c)


def test_replay_ledger_digest_can_change_without_changing_semantic_state():
    c=captures();c['mlx']['replayed_next_metadata']['ledger_digest']='new-charged-prefix'
    assert run(c)['cases']['checkpoint_resume:resumed_next_update_equivalence']['passed']
    c['mlx']['replayed_next_metadata']['targets']=257
    assert not run(c)['cases']['checkpoint_resume:resumed_next_update_equivalence']['passed']


def test_tolerance_only_applies_to_replay_history():
    c=captures();c['mlx']['replayed_next_metadata']['monitor']['gradients'][-1]+=2e-10
    assert run(c)['cases']['checkpoint_resume:resumed_next_update_equivalence']['passed']
    c['mlx']['restored_metadata']['monitor']['gradients'][-1]+=2e-10
    assert not run(c)['cases']['checkpoint_resume:monitor_schedule_roundtrip']['passed']


def test_replay_discrete_monitor_state_remains_type_exact():
    c=captures()
    for x in c.values():
        x['reference_next_metadata']['monitor']['loss_streak']=0
        x['replayed_next_metadata']['monitor']['loss_streak']=0
    c['mlx']['replayed_next_metadata']['monitor']['loss_streak']=False
    assert not run(c)['cases']['checkpoint_resume:resumed_next_update_equivalence']['passed']
