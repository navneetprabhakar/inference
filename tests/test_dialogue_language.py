"""Short conversation uncertainty is distinct from strong language contradiction."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import pytest
from slm.data.dialogue_language import assess,reasons,RULE,checked_policy
from slm.data.schema import digest
from test_dialogue_screen import record,audit,snapshot
from slm.data.dialogue_screen import screen,checked
import json


def window(text,language='en',score=.9):
    return [dict(message=0,start=0,end=len(text),status='scored',top_scores=[dict(language=language,score=score),dict(language='fr' if language=='en' else 'en',score=.01)])]


def test_short_informal_or_missing_predictions_need_review_not_a_fake_english_pass():
    text='Me want bread. You help?';w=window(text,'de',.9)
    result=assess([dict(content=text)],w)
    assert result['status']=='review_attention' and not result['hard_attention'] and not result['english_certified']
    w[0].update(status='no_prediction',top_scores=None)
    assert not assess([dict(content=text)],w)['hard_attention']


def test_long_confident_non_english_prose_remains_hard_attention():
    text='Esto es un texto escrito en español para explicar una conversación y sus preguntas con suficiente detalle para reconocer el idioma.'
    assert assess([dict(content=text)],window(text,'es',.95))['hard_attention']


def test_long_low_confidence_english_and_code_remain_uncertainty():
    text='This sentence discusses a meeting and asks the colleague to preserve the corrected appointment and the previously supplied quantities.'
    assert not assess([dict(content=text)],window(text,'en',.6))['hard_attention']
    code='```python\n'+text+'\n```'
    assert assess([dict(content=code)],window(code,'fr',.99))['windows'][0]['status']=='code_review_attention'


@pytest.mark.parametrize('defect',['gap','missing','nan','order'])
def test_bad_evidence_still_fails(defect):
    text='Hello there';w=window(text)
    if defect=='gap':w[0]['start']=1
    elif defect=='missing':w=[]
    elif defect=='nan':w[0]['top_scores'][0]['score']=float('nan')
    else:w[0]['top_scores'].reverse()
    with pytest.raises(ValueError):assess([dict(content=text)],w)


def test_v2_preserves_nonlanguage_exclusions_and_does_not_change_v1_behavior():
    from slm.data.dialogue_screen import reasons as v1
    r=record();a=audit(r);a['signals']['language_windows'][0]['top_scores'][0]['score']=.2
    assert 'language_score_attention' in v1(r,a,.8)
    assert 'language_score_attention' not in reasons(r,a,.8)
    r['messages'][1]['content']='Discuss dosage.';r['validation_results']['dialogue_candidate']['raw_nodes'][1]['text_sha256']=digest('Discuss dosage.');a=audit(r)
    assert 'bounded_scope_attention' in reasons(r,a,.8)


def test_versioned_policy_and_engine_keep_sample_only_whole_group_quarantine(tmp_path):
    args=snapshot(tmp_path);policy=json.loads(args[3].read_text());policy.update(version=2,kind='oasst-research-screen-v2',language_rule_sha256=digest(RULE));args[3].write_text(json.dumps(policy))
    checked_policy(policy)
    with pytest.raises(ValueError):checked(policy)
    report=screen(*args,tmp_path/'out')
    assert report['counts']=={'quarantined_train':2,'remaining_train':1} and not report['training_eligible']
    assert report['language_observation_counts']['review_attention']==3
    bad=deepcopy(policy);bad['language_rule_sha256']='0'*64
    with pytest.raises(ValueError):checked_policy(bad)
