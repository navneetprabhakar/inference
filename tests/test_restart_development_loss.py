import copy,hashlib,json,math
from types import SimpleNamespace
import numpy as np
import pytest
from slm.common.tokenizer import STRUCTURAL
from slm.restart.development_loss import DevelopmentTokens,score,verifier
from slm.restart.evaluation_barrier import EvaluationBarrier,EvaluationPending
from slm.restart.schedule import ScheduledUpdate


def make(root,*,split='development',partial=True):
    root.mkdir(exist_ok=True)
    tokens=np.array([10]*513+[STRUCTURAL['eos']]+[11]*3,dtype='<u2')
    rows=[dict(audit_id='a',family_id='fa',split=split,offset=0,targets=514,full_document_targets=514,partial=False,scored_utf8_bytes=1026),
          dict(audit_id='b',family_id='fb',split=split,offset=514,targets=3,full_document_targets=5 if partial else 3,partial=partial,scored_utf8_bytes=6)]
    if not partial:tokens[-1]=STRUCTURAL['eos']
    (root/'tokens.u16').write_bytes(tokens.tobytes())
    (root/'index.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    m=dict(split=split,targets=517,documents=2,families=2,scored_utf8_bytes=1032,
           files={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ('tokens.u16','index.jsonl')})
    (root/'manifest.json').write_text(json.dumps(m))
    return hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()


@pytest.fixture
def fixture(tmp_path):
    pin=make(tmp_path)
    store=DevelopmentTokens(tmp_path,manifest_sha256=pin,vocab_size=16)
    context=dict(identity='fixture',schedule_sha256='schedule',step=0,targets=0,event='dev_loss_checkpoint',checkpoint_sha256='a'*64)
    return store,context,tmp_path


def calculate(store,context):
    return score(store,context=context,logits=lambda x,p:np.zeros((*x.shape,16),np.float32),heartbeat=lambda:None)


def test_exact_segmentation_partial_tail_and_uniform_loss(fixture):
    store,context,_=fixture;parts=list(store.segments())
    assert [(p.first,p.last) for p in parts]==[(0,512),(512,514),(0,3)]
    assert parts[1].inputs[0]==10 and parts[2].inputs[0]==STRUCTURAL['bos']
    assert parts[1].targets[-1]==STRUCTURAL['eos'] and parts[2].targets==(11,11,11)
    result=calculate(store,context)
    assert result['metrics']['targets']==517
    assert result['metrics']['nll']==pytest.approx(math.log(16))
    assert result['metrics']['bits_per_byte']==pytest.approx(517*4/1032)
    assert verifier(store)(json.dumps(result).encode(),context)


@pytest.mark.parametrize('fault',['missing','duplicate','wrong_target','wrong_span','nan','negative','short','summary','manifest','context'])
def test_faults_cannot_unlock_barrier(fixture,fault):
    store,context,root=fixture;r=calculate(store,context)
    if fault=='missing':r['records'].pop()
    if fault=='duplicate':r['records'][1]=copy.deepcopy(r['records'][0])
    if fault=='wrong_target':r['records'][0]['target_ids'][0]=11
    if fault=='wrong_span':r['records'][0]['first']=False
    if fault=='nan':r['records'][0]['nll'][0]=float('nan')
    if fault=='negative':r['records'][0]['nll'][0]=-.1
    if fault=='short':r['records'][0]['nll'].pop()
    if fault=='summary':r['metrics']['nll']*=.5
    if fault=='manifest':r['manifest_sha256']='different'
    if fault=='context':r['context']=dict(context,targets=1)
    schedule=SimpleNamespace(sha256='schedule',updates=(ScheduledUpdate(1,1,3,3,.001,(),()),))
    b=EvaluationBarrier(root/'barrier',identity='fixture',schedule=schedule)
    p=root/'result.json';p.write_text(json.dumps(r))
    try:
        with pytest.raises(ValueError):b.accept('dev_loss_checkpoint',p,checkpoint_sha256='a'*64,verify=verifier(store))
        with pytest.raises(EvaluationPending):b.require_update(schedule.updates[0])
    finally:b.close()


def test_verified_raw_metrics_unlock_initial_barrier(fixture):
    store,context,root=fixture;r=calculate(store,context)
    schedule=SimpleNamespace(sha256='schedule',updates=(ScheduledUpdate(1,1,3,3,.001,(),()),))
    b=EvaluationBarrier(root/'barrier',identity='fixture',schedule=schedule)
    p=root/'result.json';p.write_text(json.dumps(r))
    try:
        b.accept('dev_loss_checkpoint',p,checkpoint_sha256='a'*64,verify=verifier(store))
        b.require_update(schedule.updates[0])
    finally:b.close()


@pytest.mark.parametrize('split',['train','test'])
def test_reject_non_development_stream(tmp_path,split):
    pin=make(tmp_path,split=split)
    with pytest.raises(ValueError):DevelopmentTokens(tmp_path,manifest_sha256=pin,vocab_size=16)


def test_changed_bytes_rejected(tmp_path):
    pin=make(tmp_path);(tmp_path/'tokens.u16').write_bytes(b'changed')
    with pytest.raises(ValueError):DevelopmentTokens(tmp_path,manifest_sha256=pin,vocab_size=16)


@pytest.mark.parametrize('fault',['nan','shape','dtype'])
def test_invalid_backend_outputs_fail(fixture,fault):
    store,context,_=fixture
    def logits(x,p):
        a=np.zeros((*x.shape,16),np.float32)
        if fault=='nan':a[0,0,0]=float('nan')
        if fault=='shape':a=a[:,:,:15]
        if fault=='dtype':a=a.astype(np.float64)
        return a
    with pytest.raises(ValueError):score(store,context=context,logits=logits,heartbeat=lambda:None)


def test_raw_losses_commit_with_durable_quality_transition(fixture):
    from slm.restart.development_loss import quality_verifier
    from slm.restart.evaluation_quality import EvaluationQualityBarrier
    from slm.restart.monitor import Monitor
    store,context,root=fixture;r=calculate(store,context)
    schedule=SimpleNamespace(sha256='schedule',updates=(ScheduledUpdate(1,1,3,3,.001,(),()),))
    b=EvaluationQualityBarrier(root/'quality-barrier',identity='fixture',schedule=schedule)
    p=root/'result.json';p.write_text(json.dumps(r))
    try:
        b.accept('dev_loss_checkpoint',p,checkpoint_sha256='a'*64,verify=quality_verifier(store))
        assert b.evaluation_state()['dev']==[r['metrics']['nll']]
        restored=b.overlay(Monitor());b.require_monitor(restored)
        assert b.pending()==()
    finally:b.close()
