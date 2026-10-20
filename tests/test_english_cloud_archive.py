# Creator: Navneet Prabhakar
import hashlib
import importlib.util
import io
import json
import tarfile
import pytest


def verifier():
    spec=importlib.util.spec_from_file_location('test_archive_verifier','scripts/verify-english-cloud-archive.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def archive(path, extra=None, wrong_payload=False):
    manifest=dict(plan_sha256='a'*64, files={'src/fixture.txt':hashlib.sha256(b'original').hexdigest()}, wheels={})
    with tarfile.open(path,'w:gz') as tar:
        for name,data in [('manifest.json',json.dumps(manifest).encode()),('project/src/fixture.txt',b'tampered' if wrong_payload else b'original')]+([] if extra is None else [extra]):
            info=tarfile.TarInfo(name);info.size=len(data);tar.addfile(info,io.BytesIO(data))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_exact_offline_payloads_and_no_overwrite(tmp_path):
    m=verifier();path=tmp_path/'inputs.tar.gz';h=archive(path);out=tmp_path/'extracted'
    r=m.unpack(path,h,out)
    assert r['complete'] and (out/'project/src/fixture.txt').read_bytes()==b'original'
    with pytest.raises(FileExistsError):m.unpack(path,h,out)


@pytest.mark.parametrize('defect',['archive_hash','payload_hash','unlisted_path','duplicate'])
def test_modified_unlisted_duplicate_archives_refused(tmp_path,defect):
    m=verifier();path=tmp_path/'inputs.tar.gz';extra=None
    if defect=='unlisted_path':extra=('../escape',b'unexpected')
    if defect=='duplicate':extra=('project/src/fixture.txt',b'original')
    h=archive(path,extra,defect=='payload_hash')
    if defect=='archive_hash':h='0'*64
    with pytest.raises(ValueError):m.unpack(path,h,tmp_path/'out')
    assert not (tmp_path/'escape').exists()
