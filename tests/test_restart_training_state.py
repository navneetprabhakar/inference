from dataclasses import asdict
from slm.restart.monitor import Monitor
import copy
import numpy as np
import pytest
from slm.restart.training_state import validate

SHAPES={'fixture_matrix':(2,2),'fixture_vector':(2,)}
EXPECTED={'tokenizer_hash':'tokenizer-v1','code_hash':'code-v1','config_hash':'config-v1'}

def fixture():
    arrays={f'{p}:{k}':np.full(s,.25,np.float32) for p in ['parameter','first_moment','second_moment'] for k,s in SHAPES.items()}
    rng=np.random.Generator(np.random.PCG64(42));rng.integers(0,100,size=13)
    state=dict(step=1,targets=8,data_cursor=2,rng=copy.deepcopy(rng.bit_generator.state),monitor=asdict(Monitor(losses=[2.],gradients=[.1])),ledger_digest='ledger-v1',**EXPECTED)
    return arrays,state,rng

def check(arrays,state):return validate(arrays,state,shapes=SHAPES,expected=EXPECTED,cursor_targets=[0,3,8,12],update_cursors=[0,2,3])

def test_exact_rng_state_reproduces_next_draws_without_reseeding():
    arrays,state,rng=fixture();restored=np.random.Generator(check(arrays,state))
    np.testing.assert_array_equal(restored.integers(0,100000,size=100),rng.integers(0,100000,size=100))

@pytest.mark.parametrize('damage',['missing_m','extra','shape','negative_v','nan','seed_only','targets','cursor','step','terminal','nonfinite_monitor','changed_contract'])
def test_semantically_invalid_bundle_rejected(damage):
    arrays,state,_=fixture()
    if damage=='missing_m':arrays.pop('first_moment:fixture_matrix')
    elif damage=='extra':arrays['other']=np.ones(1,np.float32)
    elif damage=='shape':arrays['parameter:fixture_matrix']=np.ones(4,np.float32)
    elif damage=='negative_v':arrays['second_moment:fixture_matrix'][0,0]=-.1
    elif damage=='nan':arrays['parameter:fixture_matrix'][0,0]=np.nan
    elif damage=='seed_only':state['rng']={'seed':42}
    elif damage=='targets':state['targets']=7
    elif damage=='cursor':state['data_cursor']=99
    elif damage=='step':state['step']=3
    elif damage=='terminal':state['monitor']['terminal']='loss spike'
    elif damage=='nonfinite_monitor':state['monitor']['losses']=[float('inf')]
    elif damage=='changed_contract':state['code_hash']='another'
    with pytest.raises(ValueError):check(arrays,state)

def test_step_zero_requires_no_optimizer_state():
    arrays,state,_=fixture();state.update(step=0,targets=0,data_cursor=0,monitor=asdict(Monitor()))
    with pytest.raises(ValueError):check(arrays,state)
    arrays={k:v for k,v in arrays.items() if k.startswith('parameter:')}
    check(arrays,state)


def test_semantic_validation_applies_on_publish_and_read(tmp_path):
    from slm.restart import training_state as checked
    from slm.restart import state as storage
    arrays,state,_=fixture()
    args=dict(identity='fixture-only',shapes=SHAPES,expected=EXPECTED,cursor_targets=[0,3,8,12],update_cursors=[0,2,3])
    path=checked.publish(tmp_path,'valid',arrays,state,**args)
    loaded,meta=checked.read(path,**args)
    assert meta==state
    for k in arrays:np.testing.assert_array_equal(loaded[k],arrays[k])
    arrays.pop('second_moment:fixture_vector')
    with pytest.raises(ValueError):checked.publish(tmp_path,'invalid',arrays,state,**args)
    assert not (tmp_path/'invalid').exists()
    # A cryptographically intact generic bundle still fails semantic validation.
    incomplete=storage.publish(tmp_path,'hash-valid-but-incomplete',arrays,state,identity='fixture-only')
    with pytest.raises(ValueError):checked.read(incomplete,**args)


def test_step_must_be_an_exact_frozen_accumulation_boundary():
    arrays,state,_=fixture();state.update(data_cursor=1,targets=3)
    with pytest.raises(ValueError,match='frozen update boundary'):check(arrays,state)


def test_monitor_history_cannot_be_reset_on_resume():
    arrays,state,_=fixture();state['monitor']['losses']=[]
    with pytest.raises(ValueError,match='history inconsistent'):check(arrays,state)
