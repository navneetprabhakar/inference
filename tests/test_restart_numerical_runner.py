"""Runner control-flow fault tests; no backend invocation or model allocation."""
import json
from types import SimpleNamespace
import pytest
from slm.restart.numerical_budget import NumericalBudget,NumericalBudgetError
from slm.restart.numerical_runner import Runner,NumericalCheckFailure
from slm.restart import numerical_runner


def setup(tmp_path):
    budget=NumericalBudget(tmp_path/'work',identity='runner-fixture',deadline=100)
    adapters={k:SimpleNamespace(budget=budget) for k in ('mlx','torch')}
    runner=Runner(adapters,None,{'batches':{'padded':{}}},budget=budget,output=tmp_path/'out',expected_ids=[str(i) for i in range(40)])
    return runner,budget


def test_failed_group_persists_and_stops_before_later_calls(tmp_path,monkeypatch):
    runner,budget=setup(tmp_path)
    monkeypatch.setattr(numerical_runner.numerical_forward,'run',lambda *a:{'cases':{'0':{'passed':False}},'forward_input_positions':0})
    def forbidden(*a):raise AssertionError('Later group must not run')
    monkeypatch.setattr(numerical_runner.numerical_gradients,'run',forbidden)
    with pytest.raises(NumericalCheckFailure,match='Failed numerical'):runner.pretrajectory()
    progress=json.loads((tmp_path/'out/progress.json').read_text())
    assert progress['status']=='FAILED' and progress['cases']['0']['passed'] is False
    with pytest.raises(NumericalBudgetError):budget.reserve('retry',backend='mlx',kind='forward',positions=1,now=1)
    with pytest.raises(NumericalCheckFailure):runner.pretrajectory()
    budget.close()


def test_unreconciled_work_fails_before_accepting_group(tmp_path,monkeypatch):
    runner,budget=setup(tmp_path)
    monkeypatch.setattr(numerical_runner.numerical_forward,'run',lambda *a:{'cases':{'0':{'passed':True}},'forward_input_positions':1})
    with pytest.raises(NumericalCheckFailure,match='reconciliation'):runner.pretrajectory()
    assert not runner.cases;budget.close()


def test_existing_result_directory_cannot_restart_attempt(tmp_path):
    runner,budget=setup(tmp_path);runner._persist('RUNNING')
    with pytest.raises(FileExistsError):Runner(runner.adapters,None,runner.fixtures,budget=budget,output=tmp_path/'out',expected_ids=list(runner.expected))
    budget.close()


def test_duplicate_or_unknown_case_cannot_be_accepted(tmp_path):
    runner,budget=setup(tmp_path);runner.accept({'cases':{'0':{'passed':True}}})
    with pytest.raises((NumericalCheckFailure,ValueError)):runner.accept({'cases':{'0':{'passed':True}}})
    with pytest.raises((NumericalCheckFailure,ValueError)):runner.accept({'cases':{'unknown':{'passed':True}}})
    budget.close()


def test_contradictory_numeric_pass_is_rejected(tmp_path):
    runner,budget=setup(tmp_path)
    with pytest.raises(ValueError):runner.accept({'cases':{'0':{'passed':True,'maximum_absolute_error':.1,'absolute_tolerance':1e-5,'relative_tolerance':0}}})
    assert not runner.cases;budget.close()


def trajectory_setup(tmp_path,monkeypatch):
    runner,budget=setup(tmp_path)
    runner.pretrajectory_complete=True
    runner.fixtures['batches']['fit']={}
    runner.accept({'cases':{str(i):{'passed':True} for i in range(25)}})
    calls=[]
    def capture(adapter,batch,root,**kwargs):
        calls.append(root.name)
        return dict(trajectory=[],checkpoint={},fit={'initial':2.,'after_eight_updates':.5},
                    checkpoint_path=str(root/'checkpoint'),checkpoint_identity=root.name,checkpoint_expected=kwargs['expected'])
    monkeypatch.setattr(numerical_runner.numerical_trajectory,'run',capture)
    monkeypatch.setattr(numerical_runner.numerical_optimizer,'trajectory_cases',lambda x:{str(i):{'passed':True} for i in range(25,28)})
    monkeypatch.setattr(numerical_runner.numerical_checkpoint,'run',lambda x:{'cases':{str(i):{'passed':True} for i in range(28,34)}})
    return runner,budget,calls


def test_trajectory_phase_preserves_pending_supervisor_boundary(tmp_path,monkeypatch):
    runner,budget,calls=trajectory_setup(tmp_path,monkeypatch)
    result=runner.trajectories(expected={'code_hash':'fixture'})
    assert calls==['mlx','torch'] and set(result['fit_losses'])=={'mlx','torch'}
    progress=json.loads((runner.output/'progress.json').read_text())
    assert progress['reported_cases']==34
    assert progress['status']=='WORKER_CHECKS_COMPLETE_SUPERVISOR_INTEGRITY_PENDING'
    assert (runner.output/'trajectory-evidence.json').exists()
    assert (runner.output/'integrity-inputs.json').exists()
    with pytest.raises(NumericalCheckFailure):runner.trajectories(expected={})
    assert calls==['mlx','torch']
    budget.close()


def test_trajectory_failure_stops_without_integrity_inputs(tmp_path,monkeypatch):
    runner,budget,calls=trajectory_setup(tmp_path,monkeypatch)
    def fail(*a,**kw):raise ValueError('capture failed')
    monkeypatch.setattr(numerical_runner.numerical_trajectory,'run',fail)
    with pytest.raises(ValueError,match='capture failed'):runner.trajectories(expected={})
    assert not (runner.output/'integrity-inputs.json').exists()
    assert json.loads((runner.output/'progress.json').read_text())['status']=='FAILED'
    with pytest.raises(NumericalBudgetError):budget.reserve('retry',backend='mlx',kind='forward',positions=1,now=1)
    budget.close()


def test_trajectory_cannot_skip_prechecks(tmp_path):
    runner,budget=setup(tmp_path)
    with pytest.raises(NumericalCheckFailure):runner.trajectories(expected={})
    assert not budget.events()
    budget.close()
