"""Finalizer evidence binding, with arithmetic state and a real supervised child.

The 34 worker verdicts are fixture inputs, not neural-suite results.
"""
import json,os,sys,time
from pathlib import Path
import numpy as np
import pytest
from slm.restart.numerical_finalize import finalize
from slm.restart.numerical_budget import NumericalBudget
from slm.restart.supervisor import TimeBudget,supervise,atomic_json
from slm.restart.state import publish


def setup(tmp_path):
    output=tmp_path/'out';output.mkdir()
    design=json.loads((Path(__file__).resolve().parents[1]/'restart/execution-v1/numerical-suite-design-v1.json').read_text())
    ids=[c['id'] for c in design['cases']]
    worker={c['id']:{'passed':True} for c in design['cases'] if c['group']!='fit_and_integrity'}
    work=NumericalBudget(tmp_path/'work',identity='finalizer-fixture',deadline=time.time()+100)
    clock=TimeBudget(tmp_path/'time',identity='finalizer-fixture',seconds_cap=1800,deadline_utc=time.time()+100)
    for backend in ('mlx','torch'):
        for i in range(9):
            key=f'{backend}:{i}'
            work.reserve(key,backend=backend,kind='optimizer',positions=32,now=time.time());work.complete(key)
    metadata=dict(step=0,targets=0,data_cursor=0,rng={'fixture':True},monitor={},ledger_digest='fixture',tokenizer_hash='fixture',code_hash='fixture',config_hash='fixture')
    checkpoint=publish(output/'mlx/checkpoints','complete',{'fixture':np.ones(2,np.float32)},metadata,identity='fixture')
    inputs=dict(fit_losses={b:{'initial':4.,'after_eight_updates':2.} for b in ('mlx','torch')},work_events=work.events(),complete_checkpoint=str(checkpoint),checkpoint_identity='fixture',checkpoint_expected={'code_hash':'fixture'})
    captures={b:dict(fit=inputs['fit_losses'][b],checkpoint_path=str(checkpoint),checkpoint_identity='fixture',checkpoint_expected=inputs['checkpoint_expected']) for b in ('mlx','torch')}
    atomic_json(output/'trajectory-evidence.json',captures)
    atomic_json(output/'integrity-inputs.json',inputs)
    atomic_json(output/'progress.json',dict(status='WORKER_CHECKS_COMPLETE_SUPERVISOR_INTEGRITY_PENDING',required_cases=40,reported_cases=34,cases=worker))
    receipt=tmp_path/'supervisor.json'
    result=supervise([sys.executable,'-c','pass'],cwd=tmp_path,env=dict(os.environ),heartbeat=tmp_path/'heartbeat',budget=clock,receipt=receipt,tick=.2,baseline_reader=lambda:0)
    return output,dict(expected_ids=ids,work_budget=work,time_budget=clock,supervisor_result=result,supervisor_receipt=receipt)


def close(kwargs):
    kwargs['work_budget'].close();kwargs['time_budget'].db.close()


def test_real_supervisor_and_ledgers_finalize_all_case_ids(tmp_path):
    output,kwargs=setup(tmp_path)
    try:
        result=finalize(output,**kwargs)
        assert result['status']=='NUMERICAL_CASE_RESULTS_PASS' and result['passed_cases']==40
        assert not result['training_authorized_by_this_check']
        assert len(result['evidence_sha256'])==4
        with pytest.raises(FileExistsError):finalize(output,**kwargs)
    finally:close(kwargs)


@pytest.mark.parametrize('fault',['receipt','time','work','fit','path','worker'])
def test_changed_evidence_stops_finalization(tmp_path,fault):
    output,kwargs=setup(tmp_path)
    try:
        if fault=='receipt':atomic_json(kwargs['supervisor_receipt'],{'status':'PASS'})
        elif fault=='time':kwargs['time_budget'].stop('resource stop')
        elif fault=='work':kwargs['work_budget'].reserve('unfinished',backend='mlx',kind='forward',positions=1,now=time.time())
        else:
            path=output/('progress.json' if fault=='worker' else 'integrity-inputs.json')
            data=json.loads(path.read_text())
            if fault=='fit':data['fit_losses']['mlx']['initial']=8.
            if fault=='path':data['complete_checkpoint']=str(tmp_path)
            if fault=='worker':data['status']='RUNNING'
            atomic_json(path,data)
        with pytest.raises((ValueError,RuntimeError)):finalize(output,**kwargs)
        assert json.loads((output/'result.json').read_text())['status']=='NUMERICAL_CASE_RESULTS_FAIL'
        assert kwargs['time_budget'].terminal() is not None
    finally:close(kwargs)


def test_consistent_but_failed_fit_is_terminal(tmp_path):
    output,kwargs=setup(tmp_path)
    try:
        for filename in ('integrity-inputs.json','trajectory-evidence.json'):
            path=output/filename;data=json.loads(path.read_text())
            loss=data['fit_losses']['mlx'] if filename=='integrity-inputs.json' else data['mlx']['fit']
            loss['after_eight_updates']=3.
            atomic_json(path,data)
        result=finalize(output,**kwargs)
        assert result['status']=='NUMERICAL_CASE_RESULTS_FAIL'
        assert result['failed']==['fit_and_integrity:toy_fit_loss_drop_50_percent']
        assert kwargs['time_budget'].terminal() is not None
    finally:close(kwargs)
