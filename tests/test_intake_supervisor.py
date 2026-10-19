"""Exercise the actual supervisor timeout without network or dataset work."""
# Creator: Navneet Prabhakar
import importlib.util
import json
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import pytest


@pytest.mark.parametrize('resume_deadline',[False,True])
def test_owned_worker_is_reaped_at_wall_or_original_resume_deadline(tmp_path,monkeypatch,resume_deadline):
    spec=importlib.util.spec_from_file_location('intake_supervisor',Path('scripts/intake-cosmopedia-candidates-v2.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    root=tmp_path/'job';root.mkdir();original=tmp_path/'original.json';original.write_text('{"version":1}')
    (root/'plan.json').write_text(original.read_text())
    plan=tmp_path/'continuation.json';plan.write_text(json.dumps(dict(original_plan=str(original),ledger_contract=dict(wall_seconds=10 if resume_deadline else 1))))
    if resume_deadline:
        (root/'charges').mkdir();db=sqlite3.connect(root/'charges/ledger.sqlite');db.execute('CREATE TABLE job (deadline REAL)');db.execute('INSERT INTO job VALUES (?)',(time.time()+.2,));db.commit();db.close()
    monkeypatch.setattr(mod,'ROOT',root);monkeypatch.setattr(mod,'PLAN',plan)
    monkeypatch.setattr(sys,'argv',['supervisor','--resume'])
    real_popen=subprocess.Popen;children=[]
    def owned_dummy(*args,**kwargs):
        assert kwargs['start_new_session'] is True
        child=real_popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
        children.append(child);return child
    monkeypatch.setattr(mod.subprocess,'Popen',owned_dummy)
    started=time.monotonic()
    with pytest.raises(SystemExit,match='Finite supervisor'):mod.main()
    assert time.monotonic()-started<3
    assert len(children)==1 and children[0].returncode==-signal.SIGKILL
    assert json.loads((root/'supervisor-timeout.json').read_text())['independent_wall_stop'] is True
