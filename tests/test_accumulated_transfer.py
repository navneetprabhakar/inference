import json
import pytest
from slm.common.config import Config
from slm.common.training import Trainer
from slm.eval.accumulated_transfer import create,continue_
from slm.eval.portability import get_batches
from slm.eval.state_transfer import audit


def test_finite_continuation_counts_microbatches_and_keeps_state_portable(tmp_path):
    c=Config();root=tmp_path/'fixture'
    origin=create(root,c,'torch')
    assert origin['first_update']['step']==1 and origin['first_update']['cursor']==2
    r=continue_(root,root/'initial',tmp_path/'next','torch','cpu',2)
    assert r['source_counters']['tokens']==48 and r['final_counters']=={'step':3,'cursor':6,'tokens':112,'supervised_tokens':73}
    assert r['all_final_values_finite'] and r['values_checked']==3*c.parameter_count
    exact=audit(tmp_path/'next/checkpoint',root,tmp_path/'import.json','torch')
    assert exact['passed'] and exact['updates_performed']==0
    tail=continue_(root,tmp_path/'next/checkpoint',tmp_path/'tail','torch','cpu',1)
    assert tail['final_counters']=={'step':4,'cursor':7,'tokens':122,'supervised_tokens':79}
    assert tail['history'][0]['microbatches']==1
    state=json.loads((tmp_path/'tail/checkpoint/state.json').read_text())
    assert state['version']==2 and state['accumulation']['pending_microbatches']==0
    with pytest.raises(ValueError,match='remaining'):continue_(root,tmp_path/'tail/checkpoint',tmp_path/'over','torch','cpu',1)
    with pytest.raises(FileExistsError):continue_(root,root/'initial',tmp_path/'next','torch','cpu',1)
    with pytest.raises(ValueError,match='Bounded'):continue_(root,root/'initial',tmp_path/'invalid','torch','cpu',4)
