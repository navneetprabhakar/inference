"""Parent sequencing/refusal tests; no numerical worker or model is launched."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from slm.restart import numerical_launch as launch


def test_existing_attempt_cannot_be_replaced(tmp_path,monkeypatch):
    project=tmp_path;output=project/'restart/execution-v1/numerical-run-v2';output.mkdir(parents=True)
    monkeypatch.setattr(launch.sys,'executable',str(project/'.venv/bin/python'))
    monkeypatch.setattr(launch.numerical_snapshot,'authority',lambda *a:100)
    monkeypatch.setattr(launch.numerical_prerequisites,'verify',lambda *a:pytest.fail('Must refuse before preparation'))
    with pytest.raises(FileExistsError):launch.prepare(project)


@pytest.mark.parametrize('stdout,returncode',[('1 failed',1),('2 passed, 1 skipped',0),('2 passed, 1 xfailed',0),('',0)])
def test_failed_or_incomplete_controls_never_reserve_attempt(tmp_path,monkeypatch,stdout,returncode):
    (tmp_path/'tests').mkdir();(tmp_path/'tests/test_restart_fixture.py').write_text('pass')
    monkeypatch.setattr(launch.sys,'executable',str(tmp_path/'.venv/bin/python'))
    monkeypatch.setattr(launch.numerical_snapshot,'authority',lambda *a:100)
    monkeypatch.setattr(launch.numerical_prerequisites,'verify',lambda *a:{})
    monkeypatch.setattr(launch.numerical_snapshot,'inventory',lambda *a:[])
    monkeypatch.setattr(launch.subprocess,'run',lambda *a,**kw:SimpleNamespace(stdout=stdout,stderr='',returncode=returncode))
    with pytest.raises(ValueError,match='Control suite'):launch.prepare(tmp_path)
    assert not (tmp_path/'restart/execution-v1/numerical-run-v2').exists()


def test_custody_failure_prevents_supervision_and_is_terminal(tmp_path,monkeypatch):
    ticket=dict(project=str(tmp_path),output=str(tmp_path),identity='fixture',deadline=100)
    monkeypatch.setattr(launch,'prepare',lambda *a:ticket)
    def fail(*a):raise ValueError('custody denied')
    monkeypatch.setattr(launch,'probe_custody',fail)
    monkeypatch.setattr(launch,'supervise',lambda *a,**kw:pytest.fail('Must not launch'))
    with pytest.raises(ValueError,match='custody denied'):launch.run(tmp_path)
    assert json.loads((tmp_path/'launch-stop.json').read_text())['status']=='STOP'
    clock=launch.TimeBudget(tmp_path/'time.sqlite',identity='fixture',seconds_cap=1800,deadline_utc=100)
    assert 'custody denied' in clock.terminal();clock.db.close()
