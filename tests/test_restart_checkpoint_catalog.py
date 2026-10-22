import json,shutil
from pathlib import Path
import pytest
from slm.restart.checkpoint_catalog import Catalog
from slm.restart.evaluation_quality import EvaluationQualityBarrier
from slm.restart.schedule import ScheduledUpdate
from test_restart_evaluation_checkpoint import fixture as checkpoint_fixture

@pytest.fixture
def catalog(checkpoint_fixture,tmp_path):
    initial,a=checkpoint_fixture
    args={k:a[k] for k in ('identity','expected','shapes','schedule','ledger')}
    c=Catalog(tmp_path/'catalog',root=initial.parent,**args)
    c.register(initial.name)
    a['schedule'].updates=(ScheduledUpdate(1,1,3,3,.001,(),()),)
    b=EvaluationQualityBarrier(tmp_path/'barrier',identity='run',schedule=a['schedule'])
    raw=tmp_path/'eval.json';raw.write_text(json.dumps({'context':a['context'],'metrics':{'nll':2.}}))
    b.accept('dev_loss_checkpoint',raw,checkpoint_sha256=a['manifest_sha256'],verify=lambda raw,context:{'nll':json.loads(raw)['metrics']['nll']})
    c.score(initial.name,b)
    yield c,initial,b
    c.close();b.close()


def add(c,initial,name):
    path=initial.parent/name;shutil.copytree(initial,path);c.register(name);return path


def test_latest_two_and_best_retained_with_history(catalog):
    c,initial,_=catalog
    for name in ('second','third','fourth'):add(c,initial,name)
    assert c.prune()=={'initial','third','fourth'}
    assert not (initial.parent/'second').exists()
    assert c.db.execute("SELECT status FROM checkpoints WHERE name='second'").fetchone()[0]=='pruned'
    assert c.best()['path']==str(initial)
    assert c.prune()=={'initial','third','fourth'}


def test_failed_delete_is_resumable_without_touching_retained_states(catalog,monkeypatch):
    c,initial,_=catalog
    for name in ('second','third','fourth'):add(c,initial,name)
    original=shutil.rmtree
    def fail(*a,**kw):raise OSError('simulated interruption')
    monkeypatch.setattr(shutil,'rmtree',fail)
    with pytest.raises(OSError):c.prune()
    assert initial.exists() and (initial.parent/'third').exists() and (initial.parent/'fourth').exists()
    assert c.db.execute("SELECT status FROM checkpoints WHERE name='second'").fetchone()[0]=='retiring'
    monkeypatch.setattr(shutil,'rmtree',original)
    assert c.prune()=={'initial','third','fourth'}


def test_corrupt_checkpoint_never_pruned_or_selected(catalog):
    c,initial,_=catalog
    path=add(c,initial,'second');add(c,initial,'third');add(c,initial,'fourth')
    (path/'manifest.json').write_text('{}')
    with pytest.raises(ValueError):c.prune()
    assert path.exists()
    (initial/'state.json').write_text('{}')
    with pytest.raises(ValueError):c.best()


def test_partial_and_duplicate_registration_refused(catalog):
    import sqlite3
    c,initial,_=catalog
    partial=initial.parent/'.partial-other';shutil.copytree(initial,partial)
    with pytest.raises(ValueError):c.register(partial.name)
    with pytest.raises(sqlite3.IntegrityError):c.register(initial.name)


def test_missing_dev_evidence_cannot_make_a_checkpoint_best(catalog):
    c,initial,b=catalog;add(c,initial,'second')
    b.db.execute('DELETE FROM evidence')
    with pytest.raises(ValueError):c.score('second',b)
    assert c.best()['path']==str(initial)


def test_boundary_reuses_checkpoint_and_repairs_interrupted_score(catalog):
    c,initial,b=catalog
    c.db.execute('UPDATE checkpoints SET nll=NULL,evidence_pin=NULL')
    assert c.evaluation_checkpoint(b)==initial
    assert c.best()['dev_nll']==2.
    # Repeated reconciliation verifies the exact evidence without new rows.
    assert c.evaluation_checkpoint(b)==initial
    assert c.db.execute('SELECT count(*) FROM checkpoints').fetchone()[0]==1


@pytest.mark.parametrize('fault',['evidence','checkpoint','tail','score','missing','identity'])
def test_boundary_recovery_refuses_changed_or_unavailable_state(catalog,fault):
    import hashlib
    c,initial,b=catalog
    if fault=='evidence':b.db.execute("UPDATE evidence SET raw='{}'")
    if fault=='checkpoint':(initial/'manifest.json').write_text('{}')
    if fault=='tail':c.args['ledger'].reserve('later',[('doc',0,1)],now=0)
    if fault=='score':c.db.execute('UPDATE checkpoints SET nll=1.')
    if fault=='missing':c.db.execute("UPDATE checkpoints SET status='pruned'")
    if fault=='identity':
        payload=json.loads(b.db.execute('SELECT raw FROM evidence').fetchone()[0]);payload['context']['identity']='other'
        raw=json.dumps(payload).encode();b.db.execute('UPDATE evidence SET raw=?,sha256=?',(raw,hashlib.sha256(raw).hexdigest()))
    with pytest.raises((ValueError,TypeError)):c.evaluation_checkpoint(b)


def test_no_accepted_boundary_allows_fresh_publication(catalog):
    c,_,b=catalog;b.db.execute('DELETE FROM evidence')
    assert c.evaluation_checkpoint(b) is None
