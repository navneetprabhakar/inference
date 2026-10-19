"""Complete compressed trees remain bounded, pinned and unapproved."""
# Creator: Navneet Prabhakar
import gzip
import hashlib
import io
import json
import pytest
from slm.data import tree_snapshot as module
from test_staging import setup


def fixture(tmp_path, monkeypatch, defect=None):
    setup(tmp_path)
    source = tmp_path/'source.json'
    descriptor = json.loads(source.read_text()); descriptor['source_id'] = 'OpenAssistant/oasst2'
    source.write_text(json.dumps(descriptor))
    child = dict(message_id='a', parent_id='u', role='assistant', text='Hello.', replies=[])
    root = dict(message_id='u', parent_id=None, role='prompter', text='Hi.', replies=[child])
    if defect == 'lineage':child['parent_id'] = 'missing'
    if defect == 'role':child['role'] = 'prompter'
    trees = [dict(message_tree_id='u', tree_state='ready_for_export', prompt=root)]
    if defect == 'duplicate':trees *= 2
    plain = b''.join(json.dumps(t).encode()+b'\n' for t in trees)
    payload = gzip.compress(plain)
    if defect == 'gzip':payload = payload[:-5]
    sha = hashlib.sha256(payload).hexdigest()
    if defect == 'hash':sha = '0'*64
    size = len(payload) if defect != 'oversize' else module.MAX_COMPRESSED+1
    info = [dict(type='file', path=module.FILENAME, size=size, lfs=dict(size=size, oid=sha))]
    monkeypatch.setattr(module, 'fetch', lambda *a, **k: (json.dumps(info).encode(), {}))
    monkeypatch.setattr(module, 'open_response', lambda *a, **k: io.BytesIO(payload))
    if defect == 'line_budget':monkeypatch.setattr(module, 'MAX_LINE', 30)
    if defect == 'decoded_budget':monkeypatch.setattr(module, 'MAX_DECODED', 30)
    return source, plain


def test_complete_ready_trees_preserve_raw_bytes_and_are_sample_only(tmp_path, monkeypatch):
    source, plain = fixture(tmp_path, monkeypatch)
    report = module.acquire(source, tmp_path/'out')
    assert report['trees'] == 1 and report['messages'] == 2
    assert (tmp_path/'out/trees.jsonl').read_bytes() == plain
    assert not report['training_eligible'] and not report['source_rights_approved']
    with pytest.raises(FileExistsError):module.acquire(source, tmp_path/'out')


@pytest.mark.parametrize('defect', ['hash', 'oversize', 'gzip', 'lineage', 'role', 'duplicate', 'line_budget', 'decoded_budget'])
def test_corrupt_or_over_budget_trees_are_never_published(tmp_path, monkeypatch, defect):
    source, _ = fixture(tmp_path, monkeypatch, defect)
    with pytest.raises((ValueError, OSError, EOFError)):
        module.acquire(source, tmp_path/'out')
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.tree-snapshot-*'))
