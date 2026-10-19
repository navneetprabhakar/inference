"""A failed transfer stays charged; budget and cache errors stop the job."""
# Creator: Navneet Prabhakar
import pytest
from slm.data.intake_cache import IntakeCache
from slm.data.intake_ledger import IntakeLedger
from slm.data.intake_transport import once,Unavailable


def test_no_retry_and_global_budget_error_not_relabelled(tmp_path):
    l=IntakeLedger(tmp_path/'ledger',dict(limits=dict(requests=1,body_bytes=20,rows=1,output_bytes=20),wall_seconds=60));c=IntakeCache(tmp_path/'cache',l);calls=[]
    def fail():calls.append(1);raise ValueError('Response validation failed')
    with pytest.raises(Unavailable):once(c,'a',4,fail)
    assert calls==[1] and l.totals()['requests']==1
    with pytest.raises(ValueError,match='Uncertain'):once(c,'a',4,fail)
    with pytest.raises(ValueError,match='budget'):once(c,'b',4,fail)
    assert calls==[1];l.close()
