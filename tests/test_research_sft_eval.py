# Creator: Navneet Prabhakar
from copy import deepcopy
import numpy as np
import pytest
from slm.eval.research_sft import choose, paired, TRIALS


def metric(a,f):
    return dict(assistant_mean_nll=a,retention=dict(source_balanced_foundation_nll=f))


def test_selection_uses_retention_guard_before_primary():
    base=metric(6,5)
    assert choose({TRIALS[0]:metric(4,5.1),TRIALS[1]:metric(3,5.21)},base)==TRIALS[0]
    assert choose({t:metric(3,5.21) for t in TRIALS},base) is None
    assert choose({TRIALS[0]:metric(4,5),TRIALS[1]:metric(3,5)},base)==TRIALS[1]


def test_selection_tie_and_incomplete_nonfinite():
    base=metric(6,5)
    assert choose({TRIALS[0]:metric(3.009,5),TRIALS[1]:metric(3,5)},base)==TRIALS[0]
    with pytest.raises(ValueError): choose({TRIALS[0]:metric(3,5)},base)
    with pytest.raises(ValueError): choose({TRIALS[0]:metric(np.nan,5),TRIALS[1]:metric(3,5)},base)


def test_paired_smoke_not_capability():
    r=paired([5]*109,[4]*109)
    assert r['diagnostic_smoke_passed'] and not r['conversation_capability_proved']
    assert r['improvement_95_percentile_ci']==[1.,1.]
    assert not paired([5]*109,[5.01]*109)['diagnostic_smoke_passed']
    assert paired([5]*109,[4]*109)==r
    with pytest.raises(ValueError): paired([1],[1,2])
    with pytest.raises(ValueError): paired([np.nan],[1])


def test_interview_freeze_rejects_changed_protocol_or_wrapper(tmp_path, monkeypatch):
    import json
    from slm.data.tokenized import sha
    from slm.eval import research_sft_interview as interview
    monkeypatch.setattr(interview,'ROOT',tmp_path)
    protocol=tmp_path/'protocol.json'; protocol.write_text('{}\n')
    frozen=dict(implementation_sha256=sha(interview.__file__),protocol_sha256=sha(protocol))
    path=tmp_path/'interview-freeze.json'; path.write_text(json.dumps(frozen))
    interview.checked_implementation()
    protocol.write_text('{"changed":true}\n')
    with pytest.raises(ValueError): interview.checked_implementation()
    frozen.update(protocol_sha256=sha(protocol),implementation_sha256='0'*64)
    path.write_text(json.dumps(frozen))
    with pytest.raises(ValueError): interview.checked_implementation()
