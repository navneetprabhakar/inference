import pytest
from slm.restart import candidate_pipeline as pipeline


@pytest.mark.parametrize('stop',['none','pilot_budget','pilot_error','continuation_error','final_error'])
def test_pipeline_advances_only_through_successful_stages(tmp_path,monkeypatch,stop):
    calls=[]
    monkeypatch.setattr(pipeline.candidate_launch,'prepare',lambda p:{'output':str(tmp_path)})
    def stage(binding,phase):
        calls.append(phase)
        if stop==phase+'_error':raise ValueError('terminal fixture failure')
        if phase=='pilot':return {'status':'PILOT_BUDGET_END' if stop=='pilot_budget' else 'PILOT_PASS'}
        return {'status':'NORMAL_BUDGET_END'}
    def final(binding):
        calls.append('final')
        if stop=='final_error':raise ValueError('terminal final fixture failure')
        return dict(status='NARRATIVE_REVIEW_REQUIRED',final_research_pass=False)
    monkeypatch.setattr(pipeline.candidate_launch,'stage',stage);monkeypatch.setattr(pipeline.final_launch,'launch',final)
    if stop.endswith('error'):
        with pytest.raises(ValueError):pipeline.run(tmp_path)
        assert not (tmp_path/'pipeline-completion.json').exists()
    else:
        result=pipeline.run(tmp_path)
        assert result['final_research_pass'] is False
        assert result['status']==('M1_INCOMPLETE_PILOT' if stop=='pilot_budget' else 'NARRATIVE_REVIEW_REQUIRED')
    assert calls==(['pilot'] if stop in ('pilot_budget','pilot_error') else ['pilot','continuation'] if stop=='continuation_error' else ['pilot','continuation','final'])
