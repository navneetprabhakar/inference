"""Do not repeat network/row work or trust changed completed payloads."""
# Creator: Navneet Prabhakar
import pytest
from slm.data.intake_cache import IntakeCache
from slm.data.intake_ledger import IntakeLedger
from slm.data.schema import digest


def make(tmp_path):
    ledger=IntakeLedger(tmp_path/'ledger',dict(limits=dict(requests=4,body_bytes=100,rows=10,output_bytes=1000),wall_seconds=60))
    return ledger,IntakeCache(tmp_path/'cache',ledger)


def test_complete_fetch_is_reused_without_network_or_extra_charge(tmp_path):
    ledger,cache=make(tmp_path);assert cache.fetch('a',3,lambda:b'abc')==b'abc';before=ledger.totals()
    def forbidden():raise AssertionError('Network repeated')
    assert cache.fetch('a',3,forbidden)==b'abc' and ledger.totals()==before;ledger.close()


def test_cache_cannot_satisfy_a_changed_requested_length(tmp_path):
    ledger,cache=make(tmp_path);cache.fetch('a',3,lambda:b'abc')
    with pytest.raises(ValueError,match='length'):cache.fetch('a',4,lambda:b'abcd')
    assert ledger.totals()['requests']==1;ledger.close()


def test_pending_failed_producer_cannot_repeat(tmp_path):
    ledger,cache=make(tmp_path)
    def fail():raise OSError('transport failure')
    with pytest.raises(OSError):cache.fetch('a',3,fail)
    with pytest.raises(ValueError,match='Uncertain'):cache.fetch('a',3,lambda:b'abc')
    assert ledger.totals()['requests']==1;ledger.close()


def test_completed_row_output_survives_reopen_and_detects_mutation(tmp_path):
    ledger,cache=make(tmp_path);cache.publish('rows',b'row\n',rows=2);contract=ledger.contract;ledger.close()
    ledger=IntakeLedger(tmp_path/'ledger',contract);cache=IntakeCache(tmp_path/'cache',ledger)
    assert cache.existing('rows')==b'row\n' and ledger.totals()['rows']==2
    (cache.root/(digest('rows')+'.bin')).write_bytes(b'bad')
    with pytest.raises(ValueError,match='changed'):cache.existing('rows')
    ledger.close()


def test_completed_missing_payload_and_oversized_response_are_refused(tmp_path):
    ledger,cache=make(tmp_path)
    with pytest.raises(ValueError,match='length'):cache.fetch('bad',2,lambda:b'abc')
    assert ledger.totals()['body_bytes']==3
    cache.fetch('ok',2,lambda:b'ab');(cache.root/(digest('ok')+'.bin')).unlink()
    with pytest.raises(ValueError,match='missing'):cache.existing('ok')
    ledger.close()
