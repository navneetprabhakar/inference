"""Source-stratified paired bootstrap preserves failures and frozen group counts."""
# Creator: Navneet Prabhakar
import numpy as np
import pytest
import json
from contextlib import contextmanager
from types import SimpleNamespace
from slm.eval.iteration_two import SOURCES
from slm.eval.iteration_two_results import paired_summary
from slm.eval import iteration_two_results as results
from slm.data.schema import digest
from slm.data.tokenized import sha


def test_source_stratified_bootstrap_matches_independent_sampling():
    groups=[dict(source=s) for s in SOURCES for _ in range(32)]
    delta=np.linspace(-.2,.8,64);a=np.linspace(8,10,64)
    initial={k+'_group_nll':a.tolist() for k in ('foundation','assistant')}
    final={k+'_group_nll':(a-delta).tolist() for k in ('foundation','assistant')}
    result=paired_summary(groups,initial,final);rng=np.random.default_rng(20261019)
    expected=np.mean([delta[:32][rng.integers(0,32,(10000,32))].mean(1),delta[32:][rng.integers(0,32,(10000,32))].mean(1)],axis=0)
    np.testing.assert_allclose(result['foundation']['improvement_95_percentile_ci'],np.percentile(expected,[2.5,97.5]))
    assert result['foundation_smoke_passed'] and not result['conversation_capability_proved']
    worse={k+'_group_nll':(a+.2).tolist() for k in ('foundation','assistant')}
    assert not paired_summary(groups,initial,worse)['foundation_smoke_passed']


def test_wrong_or_nonfinite_groups_cannot_be_scored():
    groups=[dict(source=SOURCES[0])]*64;values={k+'_group_nll':[8.]*64 for k in ('foundation','assistant')}
    with pytest.raises(ValueError,match='32 groups'):paired_summary(groups,values,values)
    with pytest.raises(ValueError,match='64 frozen'):paired_summary(groups[:32],values,values)


@pytest.mark.parametrize('defect',['incomplete','wrong_plan','resume','event_gap','checkpoint_counters'])
def test_incomplete_or_mismatched_actual_screen_is_refused_before_model_scoring(tmp_path,monkeypatch,defect):
    def write(path,value):path.write_text(json.dumps(value))
    trial='lr-0003';run=tmp_path/'runs'/trial;run.mkdir(parents=True)
    spec=dict(releases={'release':'unused'},tokenizer='unused');write(tmp_path/(trial+'.json'),spec)
    protocol=dict(groups=[],groups_sha256=digest([]),source_sha256={},specs={trial:dict(spec_file_sha256=sha(tmp_path/(trial+'.json')))},plan_hashes={trial:'plan'})
    write(tmp_path/'protocol.json',protocol);write(tmp_path/'freeze.json',dict(protocol_sha256=sha(tmp_path/'protocol.json')))
    expected=dict(step=256,cursor=256,tokens=262144,supervised_tokens=262144)
    (run/'events.jsonl').write_text(''.join(json.dumps(dict(step=i))+'\n' for i in range(1,256 if defect=='event_gap' else 257)))
    cp=run/'checkpoints/cp';cp.mkdir(parents=True);(cp/'manifest.json').write_text('{}')
    report=dict(plan_hash='wrong' if defect=='wrong_plan' else 'plan',status='soft_wall_limit' if defect=='incomplete' else 'invocation_update_limit',
        initial=dict(step=0,cursor=0,tokens=0,supervised_tokens=0),final=expected,
        executed_this_invocation=dict(updates=256,processed_positions=262144,supervised_positions=262144),
        events_sha256=sha(run/'events.jsonl'),latest_checkpoint=str(cp),latest_manifest_sha256=sha(cp/'manifest.json'))
    write(run/'report.json',report);write(run/'run.json',dict(plan_hash='plan',logical_plan={},resume_manifest_sha256='unexpected' if defect=='resume' else None))
    inputs=SimpleNamespace(identity='plan',plan={},pin_tree=lambda _:None,close=lambda:None)
    monkeypatch.setattr(results,'Inputs',lambda _:inputs)
    @contextmanager
    def checked(_):yield None
    monkeypatch.setattr(results,'open_checked',checked);monkeypatch.setattr(results.BPE,'load',lambda _:None)
    monkeypatch.setattr(results,'select',lambda *_:[])
    monkeypatch.setattr(results,'verify_checkpoint',lambda *_:(None,{**expected,'tokens':1}))
    monkeypatch.setattr(results,'score',lambda *_:pytest.fail('Invalid screen reached model scoring'))
    with pytest.raises(ValueError):results.evaluate_screen(tmp_path,trial,tmp_path/'freeze.json')
