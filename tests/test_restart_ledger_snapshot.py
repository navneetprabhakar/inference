import pytest
from slm.restart.ledger import Ledger,BudgetError

def make(path):return Ledger(path,'fixture',target_cap=30,update_cap=5,presentation_cap=3,deadline=100.)

def test_checkpoint_prefix_survives_new_charges_without_refund(tmp_path):
    path=tmp_path/'ledger.sqlite';ledger=make(path)
    empty=ledger.snapshot();assert empty['targets_reserved']==0
    ledger.reserve('first',[('document',0,5)],now=1);ledger.complete('first')
    checkpoint=ledger.snapshot()
    ledger.reserve('crashed',[('document',5,9)],now=2)
    ledger.close();ledger=make(path)
    assert ledger.verify_snapshot(checkpoint)==dict(later_updates_reserved=1,later_targets_reserved=4,refunds=0)
    assert ledger.totals()['targets_reserved']==9
    ledger.reserve('replay',[('document',5,9)],now=3)
    assert ledger.totals()['targets_reserved']==13
    assert ledger.verify_snapshot(empty)['later_targets_reserved']==13
    ledger.close()

@pytest.mark.parametrize('mutation',[
 "UPDATE exposures SET last=4 WHERE reservation='first'",
 "UPDATE reservations SET completed=0 WHERE id='first'",
 "DELETE FROM reservations WHERE id='first'",
])
def test_modified_checkpoint_prefix_is_rejected(tmp_path,mutation):
    ledger=make(tmp_path/'ledger.sqlite');ledger.reserve('first',[('document',0,5)],now=1);ledger.complete('first')
    checkpoint=ledger.snapshot();ledger.db.execute(mutation)
    with pytest.raises(BudgetError):ledger.verify_snapshot(checkpoint)
    ledger.close()
