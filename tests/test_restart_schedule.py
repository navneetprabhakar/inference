import hashlib,json
from pathlib import Path
import pytest
from slm.restart.schedule import Schedule
R=Path(__file__).resolve().parents[1]/'restart/execution-v1'

@pytest.fixture(scope='module')
def source():
    raw=(R/'batch-schedule-draft-v3/updates.jsonl').read_bytes()
    expected={r['audit_id']:r['targets'] for r in map(json.loads,(R/'data-train/index.jsonl').read_text().splitlines())}
    return raw,expected


def load(raw,expected):return Schedule(raw,expected_sha256=hashlib.sha256(raw).hexdigest(),document_targets=expected)


def test_actual_schedule_binds_every_resume_position(source):
    raw,expected=source;s=load(raw,expected)
    assert len(s.updates)==5383 and s.target_cap==43409847
    for step,cursor in enumerate(s.update_cursors):
        result=s.resume_position(step=step,cursor=cursor,targets=s.cursor_targets[cursor])
        assert result==(s.updates[step] if step<len(s.updates) else None)
    assert s.updates[247].cumulative_targets==2000000
    with pytest.raises(ValueError):s.resume_position(step=0,cursor=1,targets=s.cursor_targets[1])
    with pytest.raises(ValueError):s.resume_position(step=1,cursor=s.update_cursors[1],targets=0)


@pytest.mark.parametrize('fault',['hash','step','pass','event','lr','duplicate','missing_tail'])
def test_tampered_or_rehashed_invalid_schedule_rejected(source,fault):
    raw,expected=source
    if fault=='hash':
        with pytest.raises(ValueError):Schedule(raw+b'\n',expected_sha256=hashlib.sha256(raw).hexdigest(),document_targets=expected)
        return
    rows=raw.splitlines();first=json.loads(rows[0])
    if fault=='step':first['step']=2
    if fault=='pass':first['pass']=2
    if fault=='event':first['events_after_update']=['pilot_continuation_gate']
    if fault=='lr':first['lr']=0.1
    if fault=='duplicate':first['microbatches'].append(first['microbatches'][0])
    rows[0]=json.dumps(first).encode()
    if fault=='missing_tail':rows.pop()
    with pytest.raises(ValueError):load(b'\n'.join(rows)+b'\n',expected)
