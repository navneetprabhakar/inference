import copy
import math
import numpy as np
import pytest
from slm.common.tokenizer import STRUCTURAL
from slm.restart.choice_execution import prepare,execute,verify


class Tokenizer:
    vocab_size=16
    def encode(self,text):return [10+ord(c)%6 for c in text]


def items():
    return [dict(id='one',prompt='abc',alternatives=['de','fg'],continuation_token_lengths=[2,2],
                 correct_index=0,subtype='fixture',controls={'empty_prompt':'','shuffled_prompt':'xy'})]


def result(variant='original'):
    return execute(items(),Tokenizer(),variant=variant,heartbeat=lambda:None,
                   logits=lambda x,p:np.zeros((*x.shape,16),np.float32))


def test_scores_complete_continuation_and_eos_excluding_prompt():
    prepared=prepare(items(),Tokenizer())[0]['alternatives'][0]
    assert prepared['score_start']==3
    assert prepared['inputs']==[STRUCTURAL['bos'],*Tokenizer().encode('abcde')]
    assert prepared['targets'][3:]==[*Tokenizer().encode('de'),STRUCTURAL['eos']]
    r=result();assert len(r['outputs'][0]['token_log_probabilities'][0])==3
    assert r['metrics']['items'][0]['scores'][0]==pytest.approx(-3*math.log(16))
    assert r['metrics']['correct']==0 and r['metrics']['items'][0]['failure']=='tie'
    assert verify(items(),r,variant='original')==r['metrics']


@pytest.mark.parametrize('variant,length',[('original',6),('empty',3),('shuffled',5)])
def test_controls_change_context_without_changing_continuation(variant,length):
    p=prepare(items(),Tokenizer(),variant=variant)[0]['alternatives'][0]
    assert len(p['inputs'])==length
    assert p['targets'][p['score_start']:]==[*Tokenizer().encode('de'),STRUCTURAL['eos']]
    verify(items(),result(variant),variant=variant)


@pytest.mark.parametrize('fault',['length','context','control','structural'])
def test_prepare_refuses_changed_inputs(fault):
    i=items();t=Tokenizer();kw={}
    if fault=='length':i[0]['continuation_token_lengths']=[1,1]
    if fault=='context':kw['context_limit']=3
    if fault=='control':kw['variant']='other'
    if fault=='structural':t.encode=lambda text:[STRUCTURAL['eos']]*len(text)
    with pytest.raises(ValueError):prepare(i,t,**kw)


@pytest.mark.parametrize('fault',['missing','duplicate','eos','nan','summary','variant'])
def test_verify_refuses_incomplete_or_tampered_evidence(fault):
    r=result()
    if fault=='missing':r['outputs']=[]
    if fault=='duplicate':r['outputs']*=2
    if fault=='eos':r['outputs'][0]['token_log_probabilities'][0].pop()
    if fault=='nan':r['outputs'][0]['token_log_probabilities'][0][0]=float('nan')
    if fault=='summary':r['metrics']['correct']=1
    if fault=='variant':r['variant']='empty'
    with pytest.raises(ValueError):verify(items(),r,variant='original')


def test_nonfinite_logits_fail_before_aggregate():
    with pytest.raises(ValueError):execute(items(),Tokenizer(),heartbeat=lambda:None,
        logits=lambda x,p:np.full((*x.shape,16),np.nan,np.float32))
