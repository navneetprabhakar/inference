import json,sqlite3
from types import SimpleNamespace
import pytest
from slm.restart import final_state
from slm.restart.ledger import Ledger
from slm.restart.evaluation_quality import EvaluationQualityBarrier
from slm.restart.pilot_barrier import PilotBarrier
from slm.restart.checkpoint_catalog import Catalog
from slm.restart.supervisor import TimeBudget
from slm.restart.schedule import ScheduledUpdate
from slm.restart.evaluation_snapshot import MANIFEST_SHA256


@pytest.fixture
def fixture(tmp_path):
    schedule=SimpleNamespace(sha256='schedule',target_cap=3,updates=(ScheduledUpdate(1,1,3,3,.001,(),()),))
    checkpoint=tmp_path/'checkpoints';checkpoint.mkdir();expected={'code_hash':'code'}
    ledger=Ledger(tmp_path/'ledger','run',target_cap=3,update_cap=6000,presentation_cap=3,deadline=1000)
    quality=EvaluationQualityBarrier(tmp_path/'quality',identity='run',schedule=schedule)
    pilot=PilotBarrier(tmp_path/'pilot',run_identity='run',schedule_hash='schedule',evaluation_hash=MANIFEST_SHA256)
    catalog=Catalog(tmp_path/'catalog',root=checkpoint,identity='run',expected=expected,shapes={'fixture':(1,2)},schedule=schedule,ledger=ledger)
    handles=dict(ledger=ledger,quality=quality,pilot=pilot,catalog=catalog)
    ledger.reserve('wal-visible',[('doc',0,1)],now=100)
    root=tmp_path/'frozen';pin=final_state.freeze(root,**handles)
    kwargs=dict(manifest_sha256=pin,identity='run',schedule=schedule,expected=expected,checkpoint_root=checkpoint,deadline=1000)
    yield root,kwargs,handles
    for handle in handles.values():handle.close()


def test_snapshot_includes_committed_wal_and_all_handles_reject_writes(fixture):
    root,kwargs,original=fixture;opened=final_state.open_state(root,**kwargs)
    try:
        assert opened['ledger'].snapshot()==original['ledger'].snapshot()
        assert opened['ledger'].totals()['targets_reserved']==1
        assert opened['quality'].position()==0 and opened['pilot'].decision() is None
        for handle in opened.values():
            with pytest.raises(sqlite3.OperationalError):handle.db.execute('CREATE TABLE forbidden(x)')
        with pytest.raises(sqlite3.OperationalError):opened['ledger'].reserve('forbidden',[('doc',1,2)],now=100)
        assert original['ledger'].totals()['targets_reserved']==1
    finally:
        for handle in opened.values():handle.close()


@pytest.mark.parametrize('fault',['database','manifest','identity','deadline','config','checkpoint_root'])
def test_changed_or_unbound_final_state_rejected(fixture,fault):
    root,kwargs,_=fixture
    if fault=='database':(root/'ledger.sqlite').write_bytes(b'changed')
    if fault=='manifest':kwargs['manifest_sha256']='a'*64
    if fault=='identity':kwargs['identity']='other'
    if fault=='deadline':kwargs['deadline']=2000
    if fault=='config':kwargs['expected']={'code_hash':'changed'}
    if fault=='checkpoint_root':kwargs['checkpoint_root']=root
    with pytest.raises(ValueError):final_state.open_state(root,**kwargs)


def test_final_clock_observes_supervisor_charges_but_cannot_mutate(tmp_path):
    parent=TimeBudget(tmp_path/'time',identity='run',seconds_cap=129600,deadline_utc=1000)
    child=final_state.open_clock(tmp_path/'time',identity='run',deadline=1000)
    try:
        parent.reserve(10,100);assert child.charged()==10
        parent.reserve(10,100);assert child.charged()==20
        with pytest.raises(sqlite3.OperationalError):child.reserve(10,100)
        with pytest.raises(sqlite3.OperationalError):child.stop('must not mutate')
        assert parent.terminal() is None and parent.charged()==20
    finally:child.db.close();parent.db.close()


def test_source_change_during_backup_never_publishes_snapshot(fixture):
    root,_,handles=fixture;original=handles['ledger'].db
    class ChangingConnection:
        def __getattr__(self,name):return getattr(original,name)
        def backup(self,target):
            original.backup(target)
            handles['quality'].db.execute("UPDATE barrier SET terminal='concurrent stop'")
    handles['ledger'].db=ChangingConnection()
    destination=root.parent/'concurrent-snapshot'
    try:
        with pytest.raises(ValueError,match='changed'):final_state.freeze(destination,**handles)
        assert not (destination/'manifest.json').exists()
    finally:handles['ledger'].db=original
