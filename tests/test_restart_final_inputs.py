import hashlib,json
import pytest
from slm.restart import final_inputs


def make(project,monkeypatch,suite,*,wrong=False):
    root=project/'restart/execution-v1/evaluation-frozen-v1';(root/'final').mkdir(parents=True)
    key='pair_id' if suite=='copy' else 'id';count=200 if suite=='grammar' else 100
    rows=[{key:('development:' if wrong else 'final:')+str(i),'split':'final'} for i in range(count)]
    raw=''.join(json.dumps(row)+'\n' for row in rows).encode();(root/'final'/f'{suite}.jsonl').write_bytes(raw)
    manifest=json.dumps({'files_sha256':{f'final/{suite}.jsonl':hashlib.sha256(raw).hexdigest()}}).encode()
    (root/'manifest.json').write_bytes(manifest)
    monkeypatch.setattr(final_inputs,'MANIFEST_SHA256',hashlib.sha256(manifest).hexdigest())
    return root,rows


@pytest.mark.parametrize('suite',['grammar','grounded','narrative','copy'])
def test_final_suite_pins_and_denominators(tmp_path,monkeypatch,suite):
    root,rows=make(tmp_path,monkeypatch,suite)
    assert final_inputs.load(tmp_path,suite)==rows
    (root/'final'/f'{suite}.jsonl').write_text('{}')
    with pytest.raises(ValueError):final_inputs.load(tmp_path,suite)


def test_development_records_cannot_be_used_as_final(tmp_path,monkeypatch):
    make(tmp_path,monkeypatch,'grammar',wrong=True)
    with pytest.raises(ValueError):final_inputs.load(tmp_path,'grammar')
