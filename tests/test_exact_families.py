# Creator: Navneet Prabhakar
import json
import pytest
from slm.data.exact_families import ExactFamilies


def row(name,text,families=(),fixed=None,blocked=False,candidate=True):
    return dict(id=name,texts=dict(content=text),families=list(families),fixed_partition=fixed,blocked=blocked,candidate=candidate,ingredient='general')


def test_transitive_seed_and_normalized_body_protect_witness_labels(tmp_path):
    store=ExactFamilies(tmp_path/'db',max_records=10,max_bytes=1048576)
    store.add(row('old','A complete original validation story.',fixed='validation',candidate=False))
    store.add(row('new','A COMPLETE original validation story!',families=['seed:one']))
    store.add(row('other','A different generated explanatory body.',families=['seed:one']))
    report=store.finish();assert report['components']==1 and report['candidates_with_heldout_family']==2
    original=json.loads(store.db.execute("SELECT data FROM records WHERE eid='old'").fetchone()[0]);assert original['fixed_partition']=='validation'
    assert store.db.execute('SELECT sum(fixed=1) FROM records').fetchone()[0]==1
    store.close()


def test_blocked_family_and_short_labels(tmp_path):
    store=ExactFamilies(tmp_path/'db',max_records=10,max_bytes=1048576)
    store.add(row('bad','An explicitly reviewed unsuitable source document.',families=['parent:one'],blocked=True,candidate=False))
    store.add(row('related','A differently written candidate source document.',families=['parent:one']))
    store.add(row('short','blue',fixed='test',candidate=False));store.add(row('short2','blue'))
    report=store.finish();assert report['candidates_with_blocked_family']==1 and report['candidates_with_heldout_family']==0
    store.close()


def test_duplicate_identity_cap_and_existing_database_refused(tmp_path):
    p=tmp_path/'db';store=ExactFamilies(p,max_records=1,max_bytes=1048576)
    store.add(row('one','A distinct complete source document.'))
    with pytest.raises(ValueError):store.add(row('two','Another complete source document.'))
    assert store.db.execute('SELECT complete FROM status').fetchone()[0]==0
    store.close()
    with pytest.raises(FileExistsError):ExactFamilies(p,max_records=2,max_bytes=1048576)


def test_mixed_heldout_component_keeps_each_original_partition(tmp_path):
    store=ExactFamilies(tmp_path/'db',max_records=10,max_bytes=1048576)
    store.add(row('validation','A preserved validation witness passage.',families=['shared'],fixed='validation',candidate=False))
    store.add(row('test','A preserved test witness passage.',families=['shared'],fixed='test',candidate=False))
    store.add(row('candidate','A new generated candidate passage.',families=['shared']))
    result=store.finish();assert result['candidates_with_heldout_family']==1
    assert store.db.execute('SELECT heldout_priority FROM components').fetchone()==(2,)
    assert store.db.execute('SELECT fixed FROM records ORDER BY sid').fetchall()==[(1,),(2,),(0,)]
    store.close()
