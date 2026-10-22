import copy
import pytest
from slm.restart.generation_execution import generate,narrative,copying
from slm.restart.generation_verification import verify_stream,narrative as verify_narrative,apply_copying
from slm.restart.monitor import Monitor,StopRun
from test_restart_generation_execution import Tokens,logits_for


def test_valid_stream_recomputed():
    r=generate([10],Tokens(),logits=logits_for(10),heartbeat=lambda:None,seed=42)
    assert verify_stream([10],r,Tokens(),seed=42)['whitespace_words']==120


@pytest.mark.parametrize('fault',['text','reason','eos','seed','policy','tail','truncated','bool'])
def test_inconsistent_generation_rejected(fault):
    r=generate([10],Tokens(),logits=logits_for(10),heartbeat=lambda:None,seed=42)
    if fault=='text':r['text']='corrected output'
    if fault=='reason':r['stop_reason']='eos'
    if fault=='eos':r['ended_with_eos']=0
    if fault=='seed':r['seed']=43
    if fault=='policy':r['decode_policy']='different'
    if fault=='tail':r['generated_token_ids'].append(10)
    if fault=='truncated':r['generated_token_ids'].pop()
    if fault=='bool':r['generated_token_ids'][0]=True
    with pytest.raises(ValueError):verify_stream([10],r,Tokens(),seed=42)


def test_smoke_count_is_recomputed_and_fixed():
    items=[dict(id=str(i),prefix='word',prefix_token_ids=[10],generation_seed=i,
                temperature=.7,top_p=.9,minimum_words=80,maximum_words=120,early_eos_failure_below_words=40) for i in range(100)]
    outputs=narrative(items,Tokens(),logits=logits_for(10),heartbeat=lambda:None)
    smoke=[str(i) for i in range(20)]
    result=verify_narrative(items,outputs,Tokens(),smoke_ids=smoke)
    assert result['smoke_degenerate_outputs']==20
    monitor=Monitor()
    with pytest.raises(StopRun,match='generation collapse'):
        monitor.diagnostic(train_nll=2.,dev_nll=2.,grammar=.5,grounded=.5,degenerate_outputs=result['smoke_degenerate_outputs'])
    outputs[0]['diagnostics']['fourgram_failure']=False
    with pytest.raises(ValueError):verify_narrative(items,outputs,Tokens(),smoke_ids=smoke)


def test_copying_failure_is_terminal_and_raw_counts_cannot_be_hidden():
    a={'prefix':' '.join(['word']*64),'prefix_token_ids':[10]*64,'expected_next_64_token_ids':[10]*64}
    b=dict(a,expected_next_64_token_ids=[11]*64)
    pairs=[dict(pair_id=str(i),training=a,heldout=b) for i in range(100)]
    result=copying(pairs,Tokens(),logits=logits_for(10),heartbeat=lambda:None)
    m=Monitor()
    with pytest.raises(StopRun,match='copying concern'):apply_copying(m,pairs,result,Tokens())
    assert m.terminal=='copying concern'
    changed=copy.deepcopy(result);changed['metrics']['training_copies']=0
    m=Monitor()
    with pytest.raises(ValueError):apply_copying(m,pairs,changed,Tokens())
    assert m.terminal
