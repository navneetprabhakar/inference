"""Actual pinned fixture and fail-closed tamper checks; never modifies original files."""
import json
import shutil
from pathlib import Path
import pytest
from slm.restart.evaluation_snapshot import verify

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def snapshot(tmp_path):
    source = ROOT/'restart/execution-v1/evaluation-frozen-v1'
    manifest = json.loads((source/'manifest.json').read_text())
    paths = {'restart/execution-v1/evaluation-frozen-v1/manifest.json',
             'restart/execution-v1/evaluation-frozen-v1/custody-verification.json',
             'restart/execution-v1/evaluation-frozen-v1/training-custody-test.sb',
             'restart/execution-v1/evaluation-draft/combined-audit.json',
             'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv',
             'src/slm/restart/custody.py'}
    paths.update(manifest['scoring_code_sha256'])
    paths.update('restart/execution-v1/evaluation-frozen-v1/'+x for x in manifest['files_sha256'])
    audit=json.loads((ROOT/'restart/execution-v1/evaluation-draft/combined-audit.json').read_text())
    for field in ('files_sha256','evidence_sha256'):
        paths.update('restart/execution-v1/evaluation-draft/'+x for x in audit[field])
    for relative in paths:
        p=tmp_path/relative;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,p)
    return tmp_path


def test_pinned_snapshot_verifies_without_authorizing_training(snapshot):
    result=verify(snapshot)
    assert len(result['development_files'])==len(result['final_files'])==4
    assert len(set(result['smoke_ids']))==20
    assert result['training_authorized_by_this_check'] is False


@pytest.mark.parametrize('relative',[
 'restart/execution-v1/evaluation-frozen-v1/manifest.json',
 'restart/execution-v1/evaluation-frozen-v1/final/grammar.jsonl',
 'restart/execution-v1/evaluation-frozen-v1/development/copy.jsonl',
 'restart/execution-v1/evaluation-frozen-v1/custody-verification.json',
 'src/slm/restart/generation_metrics.py',
 'src/slm/restart/custody.py',
 'restart/execution-v1/evaluation-draft/combined-audit.json',
 'restart/execution-v1/evaluation-draft/grammar-v2-screen.json',
 'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv'])
def test_changed_bound_file_rejected(snapshot,relative):
    p=snapshot/relative;p.write_bytes(p.read_bytes()+b'\n')
    with pytest.raises(ValueError):verify(snapshot)


def test_same_content_symlink_rejected(snapshot):
    p=snapshot/'restart/execution-v1/evaluation-frozen-v1/final/narrative.jsonl'
    other=snapshot/'redirected.jsonl';p.rename(other);p.symlink_to(other)
    with pytest.raises(ValueError,match='redirected'):verify(snapshot)


def test_missing_final_file_rejected(snapshot):
    (snapshot/'restart/execution-v1/evaluation-frozen-v1/final/copy.jsonl').unlink()
    with pytest.raises(FileNotFoundError):verify(snapshot)
