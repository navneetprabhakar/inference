"""Synthetic transcript integrity and direct-score boundaries, never student grades."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import pytest
from slm.common.tokenizer import train_core,STRUCTURAL
from slm.data.schema import digest
from slm.inference.greedy import prompt_ids
from slm.eval.iteration_two_assessment import validate_and_score


def fixture():
    p=json.loads(Path('configs/iteration-two-conversation-assessment-v1.json').read_text())
    bpe=train_core(['This is synthetic text. Hello Mira.']*5,512,min_frequency=1);history=[];rows=[]
    for i in range(1,9):
        user=p['initial_prompt'] if i==1 else f'Follow-up {i}';history.append(dict(role='user',content=user));text=f'Synthetic bad reply {i}.';tokens=bpe.encode(text)
        r=dict(text=text,token_ids=tokens+[STRUCTURAL['eos']],stop_reason='eos',prompt_tokens=len(prompt_ids(bpe,history)),
            generated_tokens=len(tokens)+1,content_tokens=len(tokens),ttft_seconds=.1,seconds=.2,max_new_tokens=64)
        rows.append(dict(turn=i,user=user,context_sha256=digest(history),response=r));history.append(dict(role='assistant',content=text))
    grades=dict(creator='Navneet Prabhakar',review_mode='delegated_expert',human_attestation=False,full_transcript_read=True,
        dimensions={k:dict(score=0,evidence_turns=[1,8],reason='Synthetic fixture: unrelated replies.') for k in p['assessment_dimensions']},
        turn_judgments=[dict(turn=i,reason='Synthetic fixture failure.',task_succeeded=False) for i in range(1,9)],limitations='Synthetic fixture only, not a student assessment.')
    return p,bpe,rows,grades


def test_raw_history_verification_does_not_improve_or_replace_direct_grade():
    p,bpe,rows,grades=fixture();r=validate_and_score(rows,p,bpe,grades)
    assert r['normalized_score_out_of_100']==0 and r['successful_tasks']==0 and r['transcript']==rows
    grades['dimensions']['coherence']['score']=2
    assert validate_and_score(rows,p,bpe,grades)['normalized_score_out_of_100']==10


def test_context_budget_is_checked_without_dropping_history():
    p,bpe,rows,grades=fixture()
    with pytest.raises(ValueError,match='budget'):validate_and_score(rows,p,bpe,grades,max_context=32)


@pytest.mark.parametrize('defect',['text','raw_tokens','history','prompt_length','stop','timing','partial','grade_range','evidence','unread','human','turn_judgment'])
def test_corrupted_or_unread_evidence_cannot_publish_a_valid_score(defect):
    p,bpe,rows,grades=fixture()
    if defect=='text':rows[0]['response']['text']='Ideal repaired reply.'
    elif defect=='raw_tokens':rows[0]['response']['token_ids'][0]=STRUCTURAL['user']
    elif defect=='history':rows[1]['context_sha256']='0'*64
    elif defect=='prompt_length':rows[1]['response']['prompt_tokens']+=1
    elif defect=='stop':rows[0]['response']['stop_reason']='length'
    elif defect=='timing':rows[0]['response']['seconds']=float('nan')
    elif defect=='partial':rows.pop()
    elif defect=='grade_range':grades['dimensions']['coherence']['score']=5
    elif defect=='evidence':grades['dimensions']['coherence']['evidence_turns']=[9]
    elif defect=='unread':grades['full_transcript_read']=False
    elif defect=='human':grades['human_attestation']=True
    else:grades['turn_judgments'].pop()
    with pytest.raises(ValueError):validate_and_score(rows,p,bpe,grades)
