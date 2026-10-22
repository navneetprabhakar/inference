import copy,json,math
from types import SimpleNamespace
import numpy as np
import pytest
from slm.restart import full_diagnostics,choice_execution,generation_execution,development_loss
from slm.restart.evaluation_quality import EvaluationQualityBarrier
from slm.restart.schedule import ScheduledUpdate
from test_restart_development_loss import fixture as loss_fixture
from test_restart_generation_execution import Tokens,logits_for


@pytest.fixture
def assembled(loss_fixture):
    store,_,root=loss_fixture;t=Tokens()
    context=dict(identity='run',schedule_sha256='schedule',step=1,targets=2000000,
                 event='full_development_diagnostics',checkpoint_sha256='a'*64)
    choices=[dict(id='choice',correct_index=0,subtype='fixture',prompt='word',alternatives=['word','word'],
                  continuation_token_lengths=[1,1],controls={'empty_prompt':'','shuffled_prompt':'word word'})]
    stories=[dict(id=str(i),prefix='word',prefix_token_ids=[10],generation_seed=i,temperature=.7,top_p=.9,
                  minimum_words=80,maximum_words=120,early_eos_failure_below_words=40) for i in range(100)]
    p=full_diagnostics.execute(context=context,train_store=store,dev_store=store,grammar_items=choices,
        grounded_items=choices,narrative_items=stories,tokenizer=t,logits=logits_for(1),heartbeat=lambda:None)
    verify=full_diagnostics.verifier(train_store=store,dev_store=store,grammar_items=choices,grounded_items=choices,
                                    narrative_items=stories,smoke_ids=[str(i) for i in range(20)],tokenizer=t)
    return p,verify,root


def test_full_raw_diagnostics_commit_quality_history(assembled):
    p,verify,root=assembled
    metrics=verify(json.dumps(p).encode(),p['context'])
    nll=p['development_loss']['metrics']['nll'];assert nll>0
    assert metrics==dict(train_nll=nll,dev_nll=nll,grammar=0.,grounded=0.,degenerate_outputs=0)
    update=ScheduledUpdate(1,1,2000000,2000000,.001,('dev_loss_checkpoint','full_development_diagnostics'),())
    b=EvaluationQualityBarrier(root/'events',identity='run',schedule=SimpleNamespace(sha256='schedule',updates=(update,)))
    try:
        path=root/'event.json'
        for step in (0,1):
            c=dict(p['context'],step=step,targets=step*2000000,event='dev_loss_checkpoint')
            path.write_text(json.dumps({'context':c}))
            b.accept('dev_loss_checkpoint',path,checkpoint_sha256='a'*64,verify=lambda raw,context:{'nll':nll})
            if step==0:b.completed_update(update)
        path.write_text(json.dumps(p))
        b.accept('full_development_diagnostics',path,checkpoint_sha256='a'*64,verify=verify)
        assert b.evaluation_state()['diagnostics']==[[nll,nll,0.,0.]]
        assert b.pending()==('copying_probes',)
    finally:b.close()


@pytest.mark.parametrize('fault',['checkpoint','loss','choice','missing_control','narrative','inventory'])
def test_full_bundle_rejects_missing_or_mixed_evidence(assembled,fault):
    p,verify,_=assembled;p=copy.deepcopy(p)
    if fault=='checkpoint':p['grammar']['context']=dict(p['context'],checkpoint_sha256='b'*64)
    if fault=='loss':p['training_loss']['metrics']['nll']=.01
    if fault=='choice':p['grounded']['outputs'][0]['token_log_probabilities'][0].pop()
    if fault=='missing_control':del p['empty_grounded']
    if fault=='narrative':p['narratives']['outputs'].pop()
    if fault=='inventory':p['extra']='ignored'
    with pytest.raises(ValueError):verify(json.dumps(p).encode(),p['context'])
