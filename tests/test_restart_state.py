import json
from pathlib import Path
import numpy as np
import pytest
from slm.restart.state import publish,read


def meta():return dict(step=1,targets=8,data_cursor=1,rng={'seed':42},monitor={'losses':[1.]},ledger_digest='ledger',tokenizer_hash='tokenizer',code_hash='code',config_hash='config')

def test_exact_state_roundtrip_and_contract(tmp_path):
    arrays={'fixture':np.arange(10,dtype=np.float32)}
    p=publish(tmp_path,'0001',arrays,meta(),identity='fresh')
    loaded,state=read(p,identity='fresh',expected={'tokenizer_hash':'tokenizer','code_hash':'code'})
    np.testing.assert_array_equal(loaded['fixture'],arrays['fixture']);assert state==meta()
    with pytest.raises(ValueError):read(p,identity='legacy',expected={})
    with pytest.raises(ValueError):read(p,identity='fresh',expected={'code_hash':'changed'})
    with pytest.raises(FileExistsError):publish(tmp_path,'0001',arrays,meta(),identity='fresh')
    (p/'arrays.safetensors').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='Corrupt'):read(p,identity='fresh',expected={})

def test_partial_nonfinite_and_storage_fail_closed(tmp_path):
    p=tmp_path/'.partial-dead';p.mkdir();(p/'state.json').write_text('{}')
    with pytest.raises(ValueError):read(p,identity='fresh',expected={})
    with pytest.raises(ValueError):publish(tmp_path,'bad',{'x':np.array([np.nan],dtype=np.float32)},meta(),identity='fresh')
    with pytest.raises(ValueError):publish(tmp_path,'too-big',{'x':np.ones(2,dtype=np.float32)},meta(),identity='fresh',storage_cap=1)
    assert not (tmp_path/'bad').exists() and not (tmp_path/'too-big').exists()

def test_publication_failure_does_not_expose_checkpoint(tmp_path,monkeypatch):
    import slm.restart.state as state
    original=state.atomic_json
    def fail(path,value):
        if Path(path).name=='manifest.json':raise OSError('injected interrupted publication')
        return original(path,value)
    monkeypatch.setattr(state,'atomic_json',fail)
    with pytest.raises(OSError):publish(tmp_path,'0001',{'x':np.ones(2,dtype=np.float32)},meta(),identity='fresh')
    assert not list(tmp_path.iterdir())
