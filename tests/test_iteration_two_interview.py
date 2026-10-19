"""Interview preparation cannot fabricate a completed conversation or fix history."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import json
from pathlib import Path
import pytest
from slm.data.schema import digest
from slm.eval.iteration_two_interview import protocol_checked,converse,terminal_binding
from slm.eval import iteration_two_interview as interview


class Model:
    identity={'scope':'Synthetic fixture only'}
    def __init__(self):self.contexts=[]
    def generate(self,messages,budget):
        assert budget==64;self.contexts.append(deepcopy(messages))
        messages[0]['content']='A malicious mock must not rewrite stored history.'
        return dict(text='Unrelated bad reply '+str(len(self.contexts)),token_ids=[99],stop_reason='length',max_new_tokens=budget)


def protocol():return json.loads(Path('configs/iteration-two-conversation-assessment-v1.json').read_text())


def header(model,p):return dict(creator='Navneet Prabhakar',review_mode='delegated_expert',human_attestation=False,training_approved=False,student=model.identity,protocol_digest=digest(p))


def test_all_actual_bad_replies_remain_in_history_and_completion_is_not_a_grade(tmp_path):
    p=protocol();model=Model();requests=[dict(user=p['initial_prompt'])]+[dict(user=f'Follow-up {i}') for i in range(1,9)]
    emitted=[];out=tmp_path/'interview';result=converse(model,p,out,header(model,p),requests,emitted.append)
    assert len(model.contexts)==8 and result['assessment_pending'] is True and result['training_approved'] is False
    rows=[json.loads(x) for x in (out/'turns.jsonl').read_text().splitlines()]
    for i,row in enumerate(rows):
        assert row['response']['text']==f'Unrelated bad reply {i+1}'
        assert row['context_sha256']==digest(model.contexts[i])
        assert model.contexts[i][0]['content']==p['initial_prompt']
        if i:assert model.contexts[i][-2]['content']==rows[i-1]['response']['text']
    assert emitted[-1]==dict(status='complete',turns=8)


def test_early_eof_retains_partial_transcript_and_does_not_mark_completion(tmp_path):
    p=protocol();model=Model();out=tmp_path/'partial'
    with pytest.raises(ValueError,match='Incomplete interview'):converse(model,p,out,header(model,p),[dict(user=p['initial_prompt'])],lambda _:None)
    assert (out/'turns.jsonl').exists() and not (out/'completion.json').exists()


def test_generation_failure_retains_the_actual_request_without_substituting_a_reply(tmp_path):
    p=protocol();model=Model();out=tmp_path/'failed'
    def fail(*args):raise FloatingPointError('Synthetic generation failure')
    model.generate=fail
    with pytest.raises(FloatingPointError):converse(model,p,out,header(model,p),[dict(user=p['initial_prompt'])],lambda _:None)
    row=json.loads((out/'turns.jsonl').read_text());assert row['user']==p['initial_prompt'] and row['response'] is None
    assert row['generation_error']['type']=='FloatingPointError' and (out/'failure.json').exists()
    assert not (out/'completion.json').exists()


@pytest.mark.parametrize('defect',['initial_prompt','budget','anchors','attestation'])
def test_comparative_protocol_cannot_change_after_preparation(defect):
    p=protocol()
    if defect=='initial_prompt':p['initial_prompt']='Easier prompt.'
    elif defect=='budget':p['max_new_tokens']=512
    elif defect=='anchors':p['score_anchors']['4']='Any grammatical word.'
    else:p['human_attestation']=True
    with pytest.raises(ValueError):protocol_checked(p)


def test_user_requests_cannot_inject_a_corrected_assistant_history(tmp_path):
    p=protocol();model=Model();out=tmp_path/'injection'
    with pytest.raises(ValueError,match='Exactly one'):converse(model,p,out,header(model,p),[dict(user=p['initial_prompt'],assistant='Ideal repaired answer.')],lambda _:None)
    assert not model.contexts and not (out/'completion.json').exists()


@pytest.mark.parametrize('state',['live','partial'])
def test_nonterminal_training_is_refused_before_model_or_source_allocation(tmp_path,monkeypatch,state):
    run=tmp_path/'runs/selected-continuation';run.mkdir(parents=True)
    monkeypatch.setattr(interview,'Inputs',lambda *_:pytest.fail('Nonterminal run reached Inputs'))
    if state=='live':
        with pytest.raises(FileNotFoundError):terminal_binding(tmp_path,'unused','unused','unused')
    else:
        (run/'report.json').write_text(json.dumps(dict(status='soft_wall_limit')))
        with pytest.raises(ValueError,match='Complete terminal'):terminal_binding(tmp_path,'unused','unused','unused')
