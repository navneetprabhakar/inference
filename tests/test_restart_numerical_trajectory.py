"""Eight-step/replay orchestration with fixed gradients; no decoder forward."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from slm.restart.numerical_backend import NumericalBackend
from slm.restart.numerical_budget import NumericalBudget
from slm.restart.numerical_trajectory import run
from slm.restart.numerical_checkpoint import run as compare
B=json.loads((Path(__file__).resolve().parents[1]/'restart/execution-v1/numerical-fixtures-v1/batches.json').read_text())['fit']


def test_actual_storage_and_optimizer_capture_with_arithmetic_gradients(tmp_path,monkeypatch):
    budget=NumericalBudget(tmp_path/'work',identity='arithmetic-trajectories',deadline=100)
    captured={}
    for name in ('mlx','torch'):
        adapter=NumericalBackend(name,{},SimpleNamespace(),budget,clock=lambda:1)
        adapter.params={'fixture':adapter._array(np.array([[1.,2.]],np.float32))}
        # Real budgeted gradient adapter, but patched arithmetic callback.
        def gradient(*args,_a=adapter,**kwargs):
            return _a._array(np.array(2.,np.float32)),{'fixture':_a._array(np.array([[.1,.2]],np.float32))}
        monkeypatch.setattr(adapter.impl,'value_and_grad',gradient)
        result=run(adapter,B,tmp_path/name,expected={'tokenizer_hash':'fixture','code_hash':'fixture','config_hash':'fixture'})
        assert len(result['trajectory'])==8
        # Continuing the restored monitor must not mutate its checkpoint evidence.
        assert len(result['checkpoint']['restored_metadata']['monitor']['losses'])==7
        assert result['checkpoint']['ledger_after_replay']['targets_reserved']==288
        captured[name]=result['checkpoint']
        with pytest.raises(FileExistsError):run(adapter,B,tmp_path/name,expected={})
    comparison=compare(captured)
    assert all(v['passed'] for v in comparison['cases'].values()), comparison
    events=budget.events();assert sum(e['optimizer_updates'] for e in events)==18
    assert len([e for e in events if e['kind']=='gradient'])==22
    assert sum(e['positions'] for e in events)==1280
    budget.close()
