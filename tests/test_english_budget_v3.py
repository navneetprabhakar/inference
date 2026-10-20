# Creator: Navneet Prabhakar
import pytest
from slm.english_learning import Meter as RawMeter
from slm.english_budget_v3 import Meter
from slm.data.stream_hash import sha


def test_multiple_raw_ledgers_count_once_and_keep_global_and_phase_caps(tmp_path):
    priors=[]
    for name,positions in [('failed',4),('corrected',6)]:
        path=tmp_path/(name+'.sqlite');m=RawMeter(path,name);m.reserve('common',0,positions);m.close()
        priors.append(dict(path=str(path),sha256=sha(path),positions=positions,preliminary_positions=positions))
    m=Meter(tmp_path/'main.sqlite','main',maximum=18,phase_maximum=6,priors=priors)
    assert m.total()==10
    m.reserve('language',0,6)
    assert m.total()==16
    with pytest.raises(ValueError):m.reserve('language',1,1)
    with pytest.raises(ValueError):m.reserve('other',0,3)
    m.close()
    with pytest.raises(ValueError,match='Distinct'):Meter(tmp_path/'dup.sqlite','dup',priors=[priors[0],priors[0]])
    with (tmp_path/'failed.sqlite').open('ab') as f:f.write(b'changed')
    with pytest.raises(ValueError,match='changed'):Meter(tmp_path/'changed.sqlite','changed',priors=priors)
