"""Portable synthetic v3 fixtures retain stage and optimizer state across hosts."""
import json
import shutil
import pytest
pytest.importorskip('tokenizers')
from slm.common.config import Config
from slm.eval.curriculum_transfer import create,continue_,open_data


def test_v3_three_stage_bundle_relocates_and_continues_without_reset(tmp_path):
    report=create(tmp_path/'origin',Config(vocab_size=512),'torch')
    assert report['parameters']==34976 and report['first_update']['step']==1
    shutil.copytree(tmp_path/'origin',tmp_path/'relocated')
    mid=continue_(tmp_path/'relocated',tmp_path/'relocated/initial',tmp_path/'middle','torch','cpu')
    assert mid['exact_import']['passed'] and mid['update']['stage']=='conversation' and mid['update']['step']==2
    final=continue_(tmp_path/'relocated',tmp_path/'middle/checkpoint',tmp_path/'end','torch','cpu')
    assert final['after']['next_stage'] is None and final['update']['stage']=='replay' and final['update']['step']==3
    assert final['update']['tokens']==report['plan']['processed_positions']
    state=json.loads((tmp_path/'end/checkpoint/state.json').read_text())
    assert state['version']==3 and state['recipe']['embedding_implementation']=='dense-onehot-v1'
    with pytest.raises(StopIteration):continue_(tmp_path/'relocated',tmp_path/'end/checkpoint',tmp_path/'exhausted','torch','cpu')
    assert not (tmp_path/'exhausted').exists()


def test_v3_transfer_refuses_corrupt_fixture_before_import(tmp_path):
    create(tmp_path/'origin',Config(vocab_size=512),'torch')
    (tmp_path/'origin/fixture.json').write_text('{}')
    with pytest.raises(ValueError,match='checksum'):
        with open_data(tmp_path/'origin'):pass
