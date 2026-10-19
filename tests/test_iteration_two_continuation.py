"""The selected continuation consumes its own durable remaining-work reservation."""
# Creator: Navneet Prabhakar
import importlib.util
import json
from pathlib import Path
import pytest
from slm.data.tokenized import sha
from test_iteration_two_launch import fixture


def test_continuation_failure_cannot_relaunch_or_erase_discarded_work(tmp_path,monkeypatch):
    script=Path('scripts/continue-iteration-two.py').resolve()
    _,root=fixture(tmp_path,monkeypatch)
    loader=importlib.util.spec_from_file_location('continuation_fixture',script);module=importlib.util.module_from_spec(loader);loader.loader.exec_module(module)
    protocol=json.loads((root/'protocol.json').read_text());protocol['invocation']['continuation_soft_wall_seconds']=21600
    (root/'protocol.json').write_text(json.dumps(protocol))
    selection=dict(selected_trial='lr-0010',protocol_sha256=sha(root/'protocol.json'),continuation_reserved_positions=9961347,
        selected=dict(checkpoint='synthetic-selected-checkpoint'),physical_positions_already_executed=524288)
    (tmp_path/'reports/milestone-forty-nine-optimizer-selection.json').write_text(json.dumps(selection))
    (root/'reservations').mkdir()
    for trial in ('lr-0003','lr-0010'):
        (root/'reservations'/(trial+'.json')).write_text(json.dumps(dict(reserved_processed_positions=262144,
            protocol_sha256=selection['protocol_sha256'],plan_hash=protocol['plan_hashes'][trial])))
    monkeypatch.setattr(module,'select_from_results',lambda *args:selection)
    monkeypatch.setattr(module.subprocess,'check_output',lambda *args,**kw:'synthetic-test-commit')
    calls=[]
    def fail(*args,**kw):calls.append(kw);raise RuntimeError('Synthetic failure before updates')
    monkeypatch.setattr(module,'run',fail)
    with pytest.raises(RuntimeError):module.main()
    reservation=json.loads((root/'reservations/continuation.json').read_text())
    assert reservation['reserved_processed_positions']+selection['physical_positions_already_executed']==10485635
    assert calls[0]['resume']=='synthetic-selected-checkpoint' and calls[0]['wall_seconds']==21600
    with pytest.raises(FileExistsError):module.main()
    assert len(calls)==1
