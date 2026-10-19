"""Pinned small complete-file acquisition: byte/hash binding and no partial publish."""
import io
import json
import pytest
from slm.data.snapshot import acquire,MAX_BYTES
from slm.data.tokenized import sha
from test_staging import setup


def fixture(tmp_path,monkeypatch,data=b'{"text":"fixture"}\n',size=None,digest=None):
    import slm.data.snapshot as module
    setup(tmp_path)
    source=tmp_path/'source.json';s=json.loads(source.read_text());s['source_id']='fixture/source';source.write_text(json.dumps(s))
    tree=[dict(type='file',path='data.jsonl',size=len(data) if size is None else size,lfs=dict(oid=sha_bytes(data) if digest is None else digest,size=len(data) if size is None else size))]
    monkeypatch.setattr(module,'fetch',lambda *a,**k:(json.dumps(tree).encode(),{}))
    monkeypatch.setattr(module,'open_response',lambda *a,**k:io.BytesIO(data))
    return source,tree


def sha_bytes(value):
    import hashlib
    return hashlib.sha256(value).hexdigest()


def test_small_complete_file_is_pinned_and_sample_only(tmp_path,monkeypatch):
    source,tree=fixture(tmp_path,monkeypatch);out=tmp_path/'out';r=acquire(source,'data.jsonl',out,max_bytes=100)
    assert r['training_eligible'] is False and r['source_rights_approved'] is False and r['release']=='sample_only'
    assert sha(out/'rows.jsonl')==tree[0]['lfs']['oid'] and (out/'card.txt').is_file()
    with pytest.raises(FileExistsError):acquire(source,'data.jsonl',out,max_bytes=100)


@pytest.mark.parametrize('kind',['hash','size','over','no_lfs','metadata_missing','unsafe','budget'])
def test_bad_metadata_or_payload_does_not_publish(tmp_path,monkeypatch,kind):
    import slm.data.snapshot as module
    source,tree=fixture(tmp_path,monkeypatch,digest='0'*64 if kind=='hash' else None)
    if kind=='size':tree[0]['size']+=1;tree[0]['lfs']['size']+=1
    if kind=='no_lfs':tree[0].pop('lfs')
    if kind=='metadata_missing':tree.clear()
    out=tmp_path/'out'
    with pytest.raises(ValueError):acquire(source,'../data.jsonl' if kind=='unsafe' else 'data.jsonl',out,max_bytes=MAX_BYTES+1 if kind=='budget' else 1 if kind=='over' else 100)
    assert not out.exists() and not list(tmp_path.glob('.source-snapshot-*'))


def test_excluded_source_cannot_be_downloaded(tmp_path,monkeypatch):
    source,tree=fixture(tmp_path,monkeypatch);s=json.loads(source.read_text());s['review_status']='excluded';source.write_text(json.dumps(s))
    with pytest.raises(ValueError,match='non-excluded'):acquire(source,'data.jsonl',tmp_path/'out',max_bytes=100)


def test_interrupted_stream_never_publishes(tmp_path,monkeypatch):
    import slm.data.snapshot as module
    source,tree=fixture(tmp_path,monkeypatch)
    class Broken(io.BytesIO):
        def read(self,*args):raise OSError('Synthetic interrupted source stream')
    monkeypatch.setattr(module,'open_response',lambda *a,**k:Broken(b'partial'))
    with pytest.raises(OSError):acquire(source,'data.jsonl',tmp_path/'out',max_bytes=100)
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.source-snapshot-*'))


def test_evidence_mutation_is_not_published(tmp_path,monkeypatch):
    import slm.data.snapshot as module
    source,tree=fixture(tmp_path,monkeypatch)
    def mutate(*args,**kw):
        (tmp_path/'card').write_text('changed after source validation')
        return json.dumps(tree).encode(),{}
    monkeypatch.setattr(module,'fetch',mutate)
    with pytest.raises(ValueError):acquire(source,'data.jsonl',tmp_path/'out',max_bytes=100)
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.source-snapshot-*'))
