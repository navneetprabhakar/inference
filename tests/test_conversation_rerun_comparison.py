"""A changed or incomplete rerun must never inherit old quality grades."""
# Creator: Navneet Prabhakar
import importlib.util
import json
from pathlib import Path
import shutil
import pytest


def module():
    spec=importlib.util.spec_from_file_location('rerun_comparison','scripts/compare-conversation-rerun.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_live_or_missing_attempt_refused_before_grading(tmp_path):
    m=module();m.NEW=tmp_path
    with pytest.raises(ValueError,match='not terminal'):m.main()


@pytest.mark.skipif(not Path('data/current-model-100-conversations-rerun-v1/rerun-receipt.json').exists(),reason='Actual local rerun artifacts required')
@pytest.mark.parametrize('change',['text','tokens','history','incomplete'])
def test_actual_rerun_negative_controls_refuse_grade_transfer(tmp_path,change):
    m=module();copy=tmp_path/'attempt';shutil.copytree(m.NEW,copy);m.NEW=copy
    p=copy/'turns.jsonl';rows=[json.loads(line) for line in p.read_text().splitlines()]
    if change=='text':rows[0]['response']['text']='Changed reply without independent review.'
    elif change=='tokens':rows[0]['response']['token_ids'][0]+=1
    elif change=='history':rows[0]['context_sha256']='0'*64
    else:rows.pop()
    p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    with pytest.raises(ValueError,match='transfer refused|300-turn'):m.main()
