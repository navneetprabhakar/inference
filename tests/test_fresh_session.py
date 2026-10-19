# Creator: Navneet Prabhakar
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
from slm.common.tokenizer import train_core,STRUCTURAL
from slm.inference.greedy import prompt_ids
from slm.eval.fresh_session import token_stats,suffix_metrics,validate_cases,validate_response


@pytest.fixture
def prepared():
    config=json.loads(Path('configs/iteration-four-fresh-scenarios-v1.json').read_text())
    texts=[m['content'] for c in config['cases'] for m in c['messages']]+[c['reference'] for c in config['cases']]
    return config,train_core(texts,1024)


def test_stable_conditional_probability_rank_and_ties():
    r=token_stats(np.array([10000.,10001.,9999.]),1)
    assert r['rank']==1 and r['greedy_target']
    assert r['probability']==pytest.approx(1/(1+np.exp(-1)+np.exp(-2)))
    assert token_stats(np.array([3.,3.,1.]),1)['rank']==1
    assert not token_stats(np.array([3.,3.,1.]),1)['greedy_target']
    with pytest.raises(ValueError):token_stats([np.nan,1],1)
    with pytest.raises(ValueError):token_stats([0,1],2)


def test_reference_alignment_excludes_prior_assistant_and_checks_stop(prepared):
    config,bpe=prepared;c=config['cases'][2];ref=c['reference']
    x,y,_=bpe.serialize([*c['messages'],dict(role='assistant',content=ref)])
    last_role=max(i for i,t in enumerate(x) if t==STRUCTURAL['assistant'])
    assert last_role==len(prompt_ids(bpe,c['messages']))-1
    logits=np.zeros((len(x),bpe.vocab_size))
    ref_ids=bpe.encode(ref)
    for i,t in enumerate(ref_ids):logits[last_role+i,t]=3
    stop=last_role+len(ref_ids)
    logits[stop,STRUCTURAL['message_end']]=4
    logits[stop+1,STRUCTURAL['eos']]=5
    result=suffix_metrics(logits,x,y,last_role+1,ref_ids)
    assert result['content_targets']==len(ref_ids)
    assert result['content_nll_mean']==pytest.approx(np.log(np.exp(3)+bpe.vocab_size-1)-3)
    assert result['message_end_after_reference']['greedy_target']
    assert result['eos_after_message_end']['greedy_target']
    assert 0<result['either_stop_probability_after_reference']<1
    bad=list(y);bad[stop]=STRUCTURAL['user']
    with pytest.raises(ValueError):suffix_metrics(logits,x,bad,last_role+1,ref_ids)
    with pytest.raises(ValueError):suffix_metrics(logits,x,y,last_role+2,ref_ids)


def test_all_scenarios_are_distinct_protected_and_reviewed(prepared):
    config,bpe=prepared;validate_cases(config,bpe)
    for mutate in ('context','duplicate','review'):
        bad=deepcopy(config)
        if mutate=='context':bad['cases'][0]['messages'][-1]['content']='Unreserved replacement'
        elif mutate=='duplicate':bad['cases'][1]=deepcopy(bad['cases'][0])
        else:bad['review']['full_contexts_and_references_read']=False
        with pytest.raises(ValueError):validate_cases(bad,bpe)


def test_response_validation_rejects_repair_and_stop_mutation(prepared):
    config,bpe=prepared;c=config['cases'][0];token=bpe.encode('x')[0]
    r=dict(text=bpe.decode([token]),token_ids=[token,STRUCTURAL['message_end']],stop_reason='message_end',
        prompt_tokens=len(prompt_ids(bpe,c['messages'])),generated_tokens=2,content_tokens=1,
        max_new_tokens=2,ttft_seconds=.01,seconds=.02)
    validate_response(c,r,bpe,2)
    for key,value in [('text','repaired'),('stop_reason','length'),('prompt_tokens',0),('seconds',float('nan'))]:
        bad=deepcopy(r);bad[key]=value
        with pytest.raises(ValueError):validate_response(c,bad,bpe,2)
