import pytest
from slm.restart.ledger import Ledger,BudgetError

def make(path,**kw):
    return Ledger(path,'run-code-data-tokenizer-hash',**(dict(target_cap=10,update_cap=3,presentation_cap=2,deadline=100)|kw))

def test_crash_reservation_survives_and_replay_is_charged(tmp_path):
    p=tmp_path/'ledger.sqlite'; x=make(p)
    x.reserve('a',[('doc',0,3)],now=1);x.close()
    x=make(p)
    assert x.totals()==dict(updates_reserved=1,targets_reserved=3,updates_completed=0)
    with pytest.raises(BudgetError):x.reserve('a',[('doc',0,3)],now=2)
    x.reserve('retry',[('doc',0,3)],now=2)
    with pytest.raises(BudgetError):x.reserve('third',[('doc',0,1)],now=3)
    assert x.totals()['targets_reserved']==6

def test_atomic_rejection_and_shared_connections(tmp_path):
    p=tmp_path/'ledger.sqlite';a=make(p);b=make(p)
    a.reserve('a',[('d',0,6)],now=1)
    with pytest.raises(BudgetError):b.reserve('b',[('d',6,11)],now=2)
    assert b.totals()['targets_reserved']==6
    b.reserve('c',[('e',0,4)],now=3)
    with pytest.raises(BudgetError):a.reserve('d',[('f',0,1)],now=4)
    assert a.totals()['targets_reserved']==10

def test_changed_contract_and_deadline(tmp_path):
    p=tmp_path/'ledger.sqlite';a=make(p)
    with pytest.raises(BudgetError):make(p,target_cap=11)
    with pytest.raises(BudgetError):a.reserve('late',[('d',0,1)],now=100)
    assert a.totals()['updates_reserved']==0

def test_update_limit_duplicate_spans_and_completion(tmp_path):
    a=make(tmp_path/'ledger',update_cap=1)
    with pytest.raises(ValueError):a.reserve('dup',[('d',0,2),('d',1,3)],now=1)
    a.reserve('a',[('d',0,1)],now=1);a.complete('a')
    with pytest.raises(BudgetError):a.complete('a')
    with pytest.raises(BudgetError):a.reserve('b',[('e',0,1)],now=2)
    assert a.totals()['updates_completed']==1

@pytest.mark.parametrize('spans',[[],[('d',-1,2)],[('d',1,1)],[('',0,1)],[('d',False,1)]])
def test_invalid_spans(tmp_path,spans):
    a=make(tmp_path/'ledger')
    with pytest.raises(ValueError):a.reserve('a',spans,now=1)
    assert a.totals()['targets_reserved']==0

def test_partial_overlap_and_adjacent_ranges(tmp_path):
    a=make(tmp_path/'ledger',target_cap=100,update_cap=10)
    a.reserve('a',[('d',0,5),('d',5,10)],now=1)
    a.reserve('b',[('d',3,7)],now=2)
    with pytest.raises(BudgetError):a.reserve('c',[('d',2,4)],now=3)
    a.reserve('d',[('d',0,3),('d',7,10)],now=3)
    assert a.totals()['targets_reserved']==20


@pytest.mark.parametrize('limit',['targets','updates','presentations'])
def test_exhaustion_proof_retains_charges_and_excludes_failed_work(tmp_path,limit):
    from slm.restart.ledger import WorkBudgetExhausted
    caps={'target_cap':3} if limit=='targets' else {'update_cap':1} if limit=='updates' else {'presentation_cap':1}
    ledger=make(tmp_path/'ledger',**caps);ledger.reserve('old',[('doc',0,3)],now=1)
    before=ledger.snapshot()
    with pytest.raises(WorkBudgetExhausted) as caught:ledger.reserve('refused',[('doc',0,1)],now=2)
    proof=caught.value.proof
    assert ledger.verify_exhaustion(proof) and ledger.snapshot()==before
    assert ledger.db.execute("SELECT 1 FROM reservations WHERE id='refused'").fetchone() is None
    proof['reason']='invented'
    with pytest.raises(ValueError):ledger.verify_exhaustion(proof)


def test_duplicate_and_expired_work_are_not_clean_work_exhaustion(tmp_path):
    from slm.restart.ledger import WorkBudgetExhausted
    ledger=make(tmp_path/'ledger',target_cap=1);ledger.reserve('old',[('doc',0,1)],now=1)
    for identity,now in [('old',2),('new',100)]:
        with pytest.raises(BudgetError) as caught:ledger.reserve(identity,[('doc',0,1)],now=now)
        assert not isinstance(caught.value,WorkBudgetExhausted)
