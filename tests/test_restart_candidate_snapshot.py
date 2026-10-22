import copy,hashlib,json
from pathlib import Path
import pytest
from slm.restart import candidate_snapshot as snapshot


@pytest.fixture
def bound(tmp_path,monkeypatch):
    project=tmp_path/'project';project.mkdir();(project/'code.py').write_text('approved code')
    environment={'runtime':'fixed'}
    receipt={'original_deadline':1000,'environment':environment,'numerical_result_sha256':snapshot.NUMERICAL_RESULT,'schedule_sha256':snapshot.SCHEDULE}
    monkeypatch.setattr(snapshot,'preflight',lambda *a,**kw:copy.deepcopy(receipt))
    monkeypatch.setattr(snapshot.numerical_snapshot,'authority',lambda *a:1000)
    monkeypatch.setattr(snapshot.numerical_snapshot,'environment',lambda:environment)
    monkeypatch.setattr(snapshot,'inventory',lambda p:sorted(x.name for x in p.glob('*.py')))
    path=tmp_path/'snapshot.json';pin=snapshot.freeze(project,path,now=100)
    return project,path,pin


def test_exclusive_freeze_and_exact_verification(bound):
    project,path,pin=bound
    assert snapshot.verify(project,path,expected_sha256=pin,now=100)['original_deadline']==1000
    with pytest.raises(FileExistsError):snapshot.freeze(project,path,now=100)


@pytest.mark.parametrize('fault',['code','new_code','manifest','environment','symlink','pin'])
def test_changed_worker_inputs_fail_closed(bound,monkeypatch,fault,tmp_path):
    project,path,pin=bound
    if fault=='code':(project/'code.py').write_text('changed')
    if fault=='new_code':(project/'extra.py').write_text('new')
    if fault=='manifest':path.write_text('{}')
    if fault=='environment':monkeypatch.setattr(snapshot.numerical_snapshot,'environment',lambda:{'runtime':'changed'})
    if fault=='symlink':
        (project/'code.py').unlink();outside=tmp_path/'outside';outside.write_text('approved code');(project/'code.py').symlink_to(outside)
    if fault=='pin':pin='a'*64
    with pytest.raises(ValueError):snapshot.verify(project,path,expected_sha256=pin,now=100)


def test_worker_inventory_does_not_require_final_or_source_cache_reads():
    root=Path(__file__).resolve().parents[1];files=snapshot.inventory(root)
    assert 'restart/execution-v1/data-dev/tokens.u16' in files
    assert not any('/data-final/' in p or '/final/' in p or '/evaluation-draft/' in p for p in files)
    assert not any(p.endswith('audit.sqlite') or 'accepted-manifest.csv' in p for p in files)
