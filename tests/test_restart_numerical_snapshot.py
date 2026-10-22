"""Frozen code/recipe/authority refusal tests, without neural allocation."""
import datetime,shutil
from pathlib import Path
import pytest
from slm.restart import numerical_snapshot as snapshot
ROOT=Path(__file__).resolve().parents[1]
NOW=datetime.datetime.fromisoformat('2026-10-21T05:00:00+00:00').timestamp()


@pytest.fixture
def bound(tmp_path):
    project=tmp_path/'project'
    for relative in snapshot.inventory(ROOT):
        dest=project/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,dest)
    manifest=tmp_path/'frozen.json'
    pin=snapshot.freeze(project,manifest,now=NOW)
    return project,manifest,pin


def test_frozen_inventory_verified_without_execution_authority(bound):
    project,manifest,pin=bound
    result=snapshot.verify(project,manifest,expected_sha256=pin,now=NOW)
    assert not result['training_authorized_by_this_check']
    with pytest.raises(FileExistsError):snapshot.freeze(project,manifest,now=NOW)


@pytest.mark.parametrize('fault',['code','new_code','removed_code','fixture','approval','plan','policy','revision','revision_approval','manifest','environment','expired','symlink'])
def test_changed_bound_inputs_refused(bound,fault,monkeypatch):
    project,manifest,pin=bound;now=NOW
    if fault=='environment':monkeypatch.setattr(snapshot,'environment',lambda:{'changed':True})
    elif fault=='expired':now=NOW+259200
    elif fault=='manifest':manifest.write_text('{}')
    elif fault=='new_code':(project/'src/slm/new_unbound.py').write_text('pass\n')
    elif fault=='removed_code':(project/'src/slm/restart/numerical_runner.py').unlink()
    elif fault=='symlink':
        path=project/'src/slm/restart/numerical_runner.py';content=path.read_bytes();path.unlink()
        target=project.parent/'redirected.py';target.write_bytes(content);path.symlink_to(target)
    else:
        relative={'code':'src/slm/restart/numerical_runner.py','fixture':snapshot.FIXTURE_ROOT+'batches.json',
                  'approval':snapshot.BASE+'authorization.json','plan':'restart/approval-v1/PLAN.md',
                  'policy':'restart/approval-v1/policy.json','revision':snapshot.REVISION_ROOT+'proposal.json','revision_approval':snapshot.REVISION_ROOT+'authorization.json'}[fault]
        path=project/relative;path.write_bytes(path.read_bytes()+b' ')
        if fault=='approval':path.write_text('{}')
    with pytest.raises((ValueError,FileNotFoundError)):
        snapshot.verify(project,manifest,expected_sha256=pin,now=now)
