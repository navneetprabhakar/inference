import copy
from types import SimpleNamespace
import pytest
from slm.restart import final_diagnostics as final


@pytest.fixture
def fixture(monkeypatch):
    context={'event':'final_research_evaluation','identity':'run','step':1,'targets':3000000,
             'schedule_sha256':'schedule','checkpoint_sha256':'a'*64}
    baseline=SimpleNamespace(pins={'count':'pin'},selection={'alpha':.01},verify=lambda:None)
    inputs=dict(context=context,store=None,grammar_items=[],grounded_items=[],narrative_items=[],copy_pairs=[],tokenizer=None,baselines=baseline)
    payload={'context':context,'baseline_receipt':{'artifact_sha256':baseline.pins,'selection':baseline.selection,'refitted':False}}
    for name in ('loss','grammar','grounded','empty_grounded','shuffled_grounded','narratives','copying'):
        payload[name]={'context':dict(context),'outputs':[]}
    payload['baselines']={name:{'context':dict(context)} for name in ('unigram','modified_kneser_ney')}
    monkeypatch.setattr(final.final_loss,'assess',lambda *a:{'passed':True})
    monkeypatch.setattr(final.choice_execution,'verify',lambda *a,**kw:None)
    monkeypatch.setattr(final.research_gates,'grammar',lambda *a:{'passed':True})
    monkeypatch.setattr(final.research_gates,'grounded',lambda *a:{'passed':True})
    monkeypatch.setattr(final.generation_verification,'copying',lambda *a:{'final_gate_pass':True})
    monkeypatch.setattr(final.narrative_review,'prepare',lambda *a:{'fixture_packet':True})
    monkeypatch.setattr(final.narrative_review,'assess',lambda *a:{'passed':True})
    return payload,inputs


def test_missing_reviews_never_become_metric_or_research_pass(fixture):
    payload,inputs=fixture;result=final.assess(payload,**inputs)
    assert result['status']=='NARRATIVE_REVIEW_REQUIRED' and result['final_research_pass'] is False


def test_metric_pass_never_grants_research_approval(fixture):
    payload,inputs=fixture;result=final.assess(payload,reviews=[],review_packet={},**inputs)
    assert result['status']=='METRIC_GATES_PASS' and result['final_research_pass'] is False
    assert result['remaining_authority_checks']


@pytest.mark.parametrize('fault',['checkpoint','baseline_context','baseline_pin','refit','missing_baseline','extra'])
def test_final_envelope_rejects_mixed_or_incomplete_evidence(fixture,fault):
    payload,inputs=fixture;payload=copy.deepcopy(payload)
    if fault=='checkpoint':payload['copying']['context']['checkpoint_sha256']='b'*64
    if fault=='baseline_context':payload['baselines']['unigram']['context']['step']=2
    if fault=='baseline_pin':payload['baseline_receipt']['artifact_sha256']['count']='other'
    if fault=='refit':payload['baseline_receipt']['refitted']=True
    if fault=='missing_baseline':payload['baselines'].pop('unigram')
    if fault=='extra':payload['repair']='replacement'
    with pytest.raises(ValueError):final.assess(payload,**inputs)


@pytest.mark.parametrize('gate',['loss','grammar','grounded','copying','narrative'])
def test_each_failed_metric_prevents_combined_pass(fixture,monkeypatch,gate):
    payload,inputs=fixture
    module,name,key={'loss':(final.final_loss,'assess','passed'),'grammar':(final.research_gates,'grammar','passed'),
        'grounded':(final.research_gates,'grounded','passed'),'copying':(final.generation_verification,'copying','final_gate_pass'),
        'narrative':(final.narrative_review,'assess','passed')}[gate]
    monkeypatch.setattr(module,name,lambda *a,**kw:{key:False})
    assert final.assess(payload,reviews=[],review_packet={},**inputs)['status']=='METRIC_GATES_FAIL'


def test_execution_uses_one_logits_callback_and_context(fixture,monkeypatch):
    _,inputs=fixture;events=[];logits=object()
    def operation(*a,**kw):
        assert kw['logits'] is logits;events.append(True);return {'outputs':[]}
    monkeypatch.setattr(final.development_loss,'score',operation)
    monkeypatch.setattr(final.choice_execution,'execute',operation)
    monkeypatch.setattr(final.generation_execution,'copying',operation)
    def narrative(*a,**kw):operation(*a,**kw);return []
    monkeypatch.setattr(final.generation_execution,'narrative',narrative)
    inputs['baselines'].score=lambda *a,**kw:({'unigram':{'context':kw['context']},'modified_kneser_ney':{'context':kw['context']}},{})
    # Loss scorer owns its context; substituted scorer mirrors that contract.
    monkeypatch.setattr(final.development_loss,'score',lambda *a,**kw:dict(operation(*a,**kw),context=kw['context']))
    result=final.execute(**inputs,logits=logits,heartbeat=lambda:None)
    assert len(events)==7
    assert all(result[key]['context']==inputs['context'] for key in ('loss','grammar','grounded','empty_grounded','shuffled_grounded','narratives','copying'))
