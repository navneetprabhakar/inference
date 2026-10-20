# Creator: Navneet Prabhakar
import importlib.util
import pytest
from slm.data.stream_hash import sha


def controller():
    spec = importlib.util.spec_from_file_location('test_local_handoff', 'scripts/continue-english-local.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_full_authoritative_grouping_is_required_before_handoff():
    m = controller(); report = dict(complete=True, full_population=True, source_records=235779)
    assert m.ready(dict(complete=True, returncode=0), report)
    assert not m.ready(dict(complete=False, returncode=-9), report)
    for key, value in [('complete', False), ('full_population', False), ('source_records', 235778)]:
        assert not m.ready(dict(complete=True, returncode=0), {**report, key:value})
    assert not m.ready({}, {})


def test_handoff_pins_input_and_keeps_failed_child_evidence(tmp_path, monkeypatch):
    m = controller(); source = tmp_path/'input'; source.write_text('original')
    plan = dict(inputs={str(source):sha(source)}, deadline_unix=__import__('time').time()+60)
    m.check_inputs(plan); source.write_text('tampered')
    with pytest.raises(ValueError, match='differs'):m.check_inputs(plan)
    plan['inputs'][str(source)] = sha(source)
    monkeypatch.setattr(m, 'OUT', tmp_path)
    monkeypatch.setattr(m.shutil, 'disk_usage', lambda _:type('Disk', (), {'free':100*1024**3})())
    with pytest.raises(RuntimeError, match='failed'):
        m.run_step('intentional-failure', ['-c', 'raise SystemExit(7)'], 30, plan)
    import json
    assert json.loads((tmp_path/'intentional-failure-terminal.json').read_text()) == dict(complete=False, returncode=7)
