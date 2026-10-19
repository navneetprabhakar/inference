"""Real-run reservations persist through failure and prevent concurrent retries."""
# Creator: Navneet Prabhakar
import fcntl
import importlib.util
import json
from pathlib import Path
import sys
import pytest
from slm.data.schema import digest
from slm.data.tokenized import sha


def fixture(tmp_path,monkeypatch):
    script=Path('scripts/launch-iteration-two-screen.py').resolve()
    module_spec=importlib.util.spec_from_file_location('iteration_two_launch_fixture',script)
    module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path);root=tmp_path/'data/iteration-two-experiment-v1';root.mkdir(parents=True)
    reportdir=tmp_path/'reports';reportdir.mkdir()
    specs={}
    for trial in ('lr-0003','lr-0010'):
        p=root/(trial+'.json');p.write_text('{}');specs[trial]=dict(spec_file_sha256=sha(p))
    protocol=dict(groups=[],groups_sha256=digest([]),source_sha256={},specs=specs,plan_hashes={k:k for k in specs},invocation=dict(screen_soft_wall_seconds=1800))
    (root/'protocol.json').write_text(json.dumps(protocol))
    (reportdir/'milestone-forty-eight-experiment-freeze.json').write_text(json.dumps(dict(protocol_sha256=sha(root/'protocol.json'))))
    monkeypatch.setattr(module.subprocess,'check_output',lambda *a,**k:'synthetic-test-commit')
    monkeypatch.setattr(sys,'argv',['launch','--trial','lr-0003'])
    return module,root


def test_failure_consumes_reservation_and_retry_never_reaches_student(tmp_path,monkeypatch):
    module,root=fixture(tmp_path,monkeypatch);calls=[]
    def fail(*args,**kwargs):calls.append(kwargs);raise RuntimeError('Synthetic preflight failure')
    monkeypatch.setattr(module,'run',fail)
    with pytest.raises(RuntimeError):module.main()
    reservation=json.loads((root/'reservations/lr-0003.json').read_text());assert reservation['reserved_processed_positions']==262144
    with pytest.raises(FileExistsError):module.main()
    assert len(calls)==1 and calls[0]['max_new_updates']==256 and calls[0]['backend']=='mlx'


def test_execution_lock_and_first_trial_completion_are_required(tmp_path,monkeypatch):
    module,root=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(module,'run',lambda *a,**k:pytest.fail('Unexpected student allocation'))
    with (root/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):module.main()
    assert not (root/'reservations').exists()
    monkeypatch.setattr(sys,'argv',['launch','--trial','lr-0010'])
    with pytest.raises(ValueError,match='Complete first'):module.main()
    assert not (root/'reservations').exists()
