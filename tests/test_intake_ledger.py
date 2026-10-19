"""Exercise crash/reopen and shared limits across separate intake operations."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import shutil
import pytest
from slm.data.intake_ledger import IntakeLedger


def contract():
    return dict(limits=dict(requests=3,body_bytes=20,rows=10,output_bytes=100),wall_seconds=60)


def test_pending_and_failed_charges_survive_reopen(tmp_path):
    root=tmp_path/'job';a=IntakeLedger(root,contract(),clock=lambda:100)
    a.reserve('header',requests=1,body_bytes=5);a.reserve('footer',requests=1,body_bytes=10)
    a.finish('footer');a.close()
    b=IntakeLedger(root,contract(),clock=lambda:110)
    assert b.totals()['body_bytes']==15
    assert [r['state'] for r in b.snapshot()['attempts']]==['pending','failed']
    with pytest.raises(ValueError,match='replay'):b.reserve('header',requests=1)
    with pytest.raises(ValueError,match='budget'):b.reserve('payload',body_bytes=6)
    assert b.totals()['requests']==2;b.close()


def test_global_limits_across_files_and_success_does_not_refund(tmp_path):
    a=IntakeLedger(tmp_path/'job',contract())
    a.reserve('file-a',requests=2,body_bytes=15);a.finish('file-a',raw=b'abc')
    a.reserve('file-b',requests=1,body_bytes=5)
    with pytest.raises(ValueError,match='budget'):a.reserve('file-c',requests=1)
    assert a.totals()['body_bytes']==20;a.close()


def test_deadline_and_exact_contract_location_persist(tmp_path):
    root=tmp_path/'job';a=IntakeLedger(root,contract(),clock=lambda:100);a.close()
    with pytest.raises(ValueError,match='deadline'):IntakeLedger(root,contract(),clock=lambda:160)
    c=contract();c['wall_seconds']=100
    with pytest.raises(ValueError,match='contract'):IntakeLedger(root,c,clock=lambda:110)
    shutil.copytree(root,tmp_path/'copy')
    with pytest.raises(ValueError,match='location'):IntakeLedger(tmp_path/'copy',contract(),clock=lambda:110)


def test_rows_output_and_one_pending_completion(tmp_path):
    a=IntakeLedger(tmp_path/'job',contract());a.reserve('group',rows=10,output_bytes=100)
    with pytest.raises(ValueError,match='budget'):a.reserve('other-group',rows=1)
    with pytest.raises(ValueError,match='budget'):a.reserve('other-output',output_bytes=1)
    with pytest.raises(ValueError,match='exceed'):a.finish('group',raw=b'a')
    a.finish('group')
    with pytest.raises(ValueError,match='Pending'):a.finish('group')
    a.close()


def test_concurrent_owner_and_bad_charges(tmp_path):
    a=IntakeLedger(tmp_path/'job',contract())
    with pytest.raises(BlockingIOError):IntakeLedger(tmp_path/'job',contract())
    for charge in [dict(requests=-1),dict(body_bytes=True),dict(unknown=1),{}]:
        with pytest.raises(ValueError):a.reserve('bad',**charge)
    assert a.snapshot()['attempts']==[];a.close()


def test_reopen_detects_contract_mutation_and_symlink(tmp_path):
    root=tmp_path/'job';a=IntakeLedger(root,contract());a.close()
    c=deepcopy(contract());c['limits']['rows']+=1
    with pytest.raises(ValueError):IntakeLedger(root,c)
    target=root/'ledger.sqlite';target.rename(root/'real.sqlite');target.symlink_to(root/'real.sqlite')
    with pytest.raises(ValueError,match='Symlink'):IntakeLedger(root,contract())


def test_lost_database_cannot_reset_budget(tmp_path):
    root=tmp_path/'job';a=IntakeLedger(root,contract());a.reserve('spent',requests=3);a.close()
    (root/'ledger.sqlite').unlink()
    with pytest.raises(ValueError,match='reset'):IntakeLedger(root,contract())


def test_mutating_callers_contract_cannot_increase_allowance(tmp_path):
    c=contract();a=IntakeLedger(tmp_path/'job',c);c['limits']['requests']=100
    with pytest.raises(ValueError,match='budget'):a.reserve('large',requests=4)
    a.close()
