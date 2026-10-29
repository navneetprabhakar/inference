"""Gated CLI phases; every model invocation is charged to one durable ledger."""
import gc
import json
import math
import sys
import time
import numpy as np
import support as s
from sentencepiece import SentencePieceProcessor


def bank(name):
    return s.read(s.PRIVATE / (name + '.json'))


def groups_at(index, arm):
    batch = s.read(s.PRIVATE / 'schedule.json')['main'][index]
    return [('rehearsal', .25, [bank('rehearsal')[i] for i in batch['rehearsal']]),
            ('grounding', .10, [bank('grounding')[i] for i in batch['grounding']]),
            ('comparison', .15, [bank('teacher' if arm=='teacher' else 'grounding')[i] for i in batch[arm]])]


def numerical(e, meter, replay):
    import torch
    sys.path.insert(0, str(s.PROJECT / 'restart/mac15m-feasibility-v1/upstream'))
    from model import ModelArgs, Transformer
    torch.set_num_threads(2)
    model = Transformer(ModelArgs(**e.origin['model_args']))
    model.load_state_dict(e.origin['model'], strict=True)
    model.eval()
    fn, gfn = s.serializer.loss_functions(e)
    batches = {}
    for name, _, rows in groups_at(0, 'teacher'):
        batches[name] = s.serializer.collate(rows)[:3]
    batches['extra_grounding'] = s.serializer.collate(groups_at(0, 'control')[-1][2])[:3]
    batches['narrative'] = (replay[0, :, :-1], replay[0, :, 1:], np.ones((8,256), np.float32))
    gradients = {}; summaries = {}
    for name, (x,y,mask) in batches.items():
        meter.reserve(int(x.size)*4, 'independent-numerical-'+name)
        if name == 'narrative':
            value, grad = e.grad_fn(e.params,e.mx.array(x),e.mx.array(y))
            value=value/e.scale;grad={k:v/e.scale for k,v in grad.items()}
        else:
            value, grad = gfn(e.params,e.mx.array(x),e.mx.array(y),e.mx.array(mask))
        e.mx.eval(value,grad)
        bad=np.where(mask>0,y,(y+7)%32000).astype(np.int32)
        changed=fn(e.params,e.mx.array(x),e.mx.array(bad),e.mx.array(mask))
        pad=x.copy()
        if name!='narrative':
            rows=(groups_at(0,'teacher')[['rehearsal','grounding','comparison'].index(name)][2] if name!='extra_grounding' else groups_at(0,'control')[-1][2])
            for i,row in enumerate(rows):pad[i,len(row['ids'])-1:]=17
        padding=fn(e.params,e.mx.array(pad),e.mx.array(y),e.mx.array(mask))
        e.mx.eval(changed,padding)
        model.zero_grad(set_to_none=True)
        logits=model(torch.tensor(x,dtype=torch.long),torch.tensor(y,dtype=torch.long))
        ce=torch.nn.functional.cross_entropy(logits.reshape(-1,32000),torch.tensor(y.reshape(-1),dtype=torch.long),reduction='none').reshape(y.shape)
        loss=(ce*torch.tensor(mask)).sum()/float(mask.sum());loss.backward()
        a={e.mapping()[k]:p.grad.detach().numpy().copy() for k,p in model.named_parameters()}
        b={k:np.array(v) for k,v in grad.items()}
        gradients[name]=(a,b)
        norm_a=sum(float(np.sum(v.astype(np.float64)**2)) for v in a.values())
        norm_b=sum(float(np.sum(v.astype(np.float64)**2)) for v in b.values())
        dot=sum(float(np.sum(a[k].astype(np.float64)*b[k].astype(np.float64))) for k in a)
        diff=sum(float(np.sum((a[k].astype(np.float64)-b[k].astype(np.float64))**2)) for k in a)
        summary=dict(nll_delta=abs(float(value)-float(loss.detach())),gradient_relative_l2=math.sqrt(diff/norm_a),
            cosine=dot/math.sqrt(norm_a*norm_b),masked_label_delta=abs(float(value)-float(changed)),padding_delta=abs(float(value)-float(padding)))
        summaries[name]=summary
        assert summary['nll_delta']<=.02 and summary['gradient_relative_l2']<=.08 and summary['cosine']>=.995,summary
        assert summary['masked_label_delta']<=1e-6 and summary['padding_delta']<=1e-6,summary
    for arm, extra in [('control','extra_grounding'),('teacher','comparison')]:
        coeff={'narrative':.5,'rehearsal':.25,'grounding':.1,extra:.15}
        a={k:sum(weight*gradients[n][0][k].astype(np.float64) for n,weight in coeff.items()) for k in gradients['narrative'][0]}
        b={k:sum(weight*gradients[n][1][k].astype(np.float64) for n,weight in coeff.items()) for k in a}
        aa=sum(float(np.sum(v*v)) for v in a.values());bb=sum(float(np.sum(v*v)) for v in b.values())
        dot=sum(float(np.sum(a[k]*b[k])) for k in a);diff=sum(float(np.sum((a[k]-b[k])**2)) for k in a)
        summaries[arm+'-combined']=dict(gradient_relative_l2=math.sqrt(diff/aa),cosine=dot/math.sqrt(aa*bb))
        assert math.sqrt(diff/aa)<=.08 and dot/math.sqrt(aa*bb)>=.995
    s.save(s.ROOT/'numerical-preflight.json',dict(status='PASS',groups=summaries,optimizer_updates=0))
    del model,gradients,grad,logits,ce,loss
    gc.collect()
    return summaries


def preflight(meter,replay):
    e,c=s.load();summaries=numerical(e,meter,replay);del e,c;gc.collect()
    # Exact restart trajectory: two uninterrupted vs one + save/reload + one.
    e,c=s.load();_,gfn=s.serializer.loss_functions(e)
    for i in range(2):s.update(e,c,gfn,groups_at(i,'teacher'),replay[i],2e-5,meter)
    uninterrupted=s.snapshot(e,meter);del e,c,gfn;gc.collect()
    e,c=s.load();_,gfn=s.serializer.loss_functions(e)
    s.update(e,c,gfn,groups_at(0,'teacher'),replay[0],2e-5,meter)
    path=s.checkpoint(e,meter,'resume-preflight-step1');before=s.snapshot(e,meter)
    del e,c,gfn;gc.collect()
    e,c=s.load(path);restored=s.snapshot(e,meter);s.exact_state(before,restored,metadata=True)
    _,gfn=s.serializer.loss_functions(e)
    s.update(e,c,gfn,groups_at(1,'teacher'),replay[1],2e-5,meter)
    s.exact_state(uninterrupted,s.snapshot(e,meter))
    del e,c,gfn,uninterrupted,before,restored;gc.collect()
    e,c=s.load(mode='fresh');_,gfn=s.serializer.loss_functions(e)
    assert e.base_step==0
    for opt,names in [(e.om,e.matrix),(e.on,e.norm)]:
        assert int(opt.state['step'])==0
        assert all(not bool(e.mx.any(opt.state[k][f])) for k in names for f in ['m','v'])
    for i in range(2):s.update(e,c,gfn,[('fit',.5,bank('fit')[i*8:i*8+8])],replay[i],2e-5*(i+1)/5,meter)
    state=s.snapshot(e,meter);assert state['optimizer_step']==2 and state['effective_learning_rate']==2e-5*2/5
    s.checkpoint(e,meter,'fresh-preflight-step2')
    s.save(s.ROOT/'preflight.json',dict(status='PASS',six_disposable_optimizer_invocations=6,
        exact_save_reload=True,exact_resumed_trajectory=True,fresh_reset_and_counters=True,numerical=summaries,
        used_as_training_source=False))


def fit(meter,replay,sp):
    assert s.read(s.ROOT/'preflight.json')['status']=='PASS'
    e,c=s.load(mode='fresh');_,gfn=s.serializer.loss_functions(e)
    rows=bank('fit');schedule=s.read(s.PRIVATE/'schedule.json')['fit'];history=[]
    for i,indices in enumerate(schedule):
        stats=s.update(e,c,gfn,[('fit',.5,[rows[k] for k in indices])],replay[i],2e-5*min(1,(i+1)/5),meter)
        with (s.ROOT/'fit-updates.jsonl').open('a') as handle:handle.write(json.dumps(stats)+'\n')
        if (i+1)%25==0:print(json.dumps(dict(event='fit-progress',step=i+1,fit_loss=stats['components']['fit']['loss'])),flush=True)
        if (i+1)%50:continue
        path=s.checkpoint(e,meter,f'fit-{i+1}')
        loss=s.foundation(e,meter)
        metrics=s.generate(e,c,rows,sp,16,meter,f'fit-{i+1}')
        row=dict(step=i+1,narrative_nll=loss,narrative_regression=loss/s.ORIGINAL_NLL-1,fit=metrics,checkpoint=str(path.relative_to(s.PROJECT)),sha256=s.sha(path))
        history.append(row);s.save(s.ROOT/'fit-history.json',history);print(json.dumps(dict(event='fit-checkpoint',**row)),flush=True)
        if loss>s.ORIGINAL_NLL*1.05:
            s.save(s.ROOT/'fit-result.json',dict(status='NARRATIVE_GUARD_STOP',history=history,stage_II_started=False))
            raise RuntimeError('ORIGINAL_NARRATIVE_GUARD')
        if all(metrics['families'][f]['strict']>=15 for f in ['full_name','printed_time']):
            s.save(s.ROOT/'fit-result.json',dict(status='PASS',history=history,selected_for_fit_only=str(path.relative_to(s.PROJECT)),stage_II_source_is_original_B=True));return
    s.save(s.ROOT/'fit-result.json',dict(status='FIT_GATE_FAILED',history=history,stage_II_started=False))
    s.save(s.ROOT/'STOP.json',dict(reason='FIT_GATE_FAILED',updates=meter.data['updates'],positions=meter.data['positions'],new_teacher_calls=0,stage_II_started=False))


def baseline(meter,replay,sp):
    assert s.read(s.ROOT/'fit-result.json')['status']=='PASS'
    e,c=s.load()
    nll=s.foundation(e,meter);ret=s.generate(e,c,bank('retention'),sp,16,meter,'baseline-retention',legacy=True)
    assert ret['content']==72 and ret['strict']==64,(ret,'BASELINE_CALIBRATION')
    assert abs(nll-1.3738726079463959)<1e-5
    dev=s.generate(e,c,bank('development'),sp,48,meter,'baseline-development')
    secondary=s.generate(e,c,bank('secondary'),sp,48,meter,'baseline-secondary')
    s.save(s.ROOT/'baseline.json',dict(narrative_nll=nll,retention=ret,development=dev,secondary=secondary))


def block(meter,replay,sp,arm):
    assert s.read(s.ROOT/'fit-result.json')['status']=='PASS'
    assert (s.ROOT/'baseline.json').exists()
    histpath=s.ROOT/(arm+'-history.json');history=s.read(histpath) if histpath.exists() else []
    offset=history[-1]['step'] if history else 0
    otherpath=s.ROOT/(('teacher' if arm=='control' else 'control')+'-history.json')
    other=s.read(otherpath)[-1]['step'] if otherpath.exists() else 0
    assert (offset==other if arm=='control' else offset+50==other),'BLOCK_ORDER'
    assert offset<400
    path=s.PROJECT/history[-1]['checkpoint'] if history else s.SOURCE
    e,c=s.load(path);assert e.bridge_cursor==offset;_,gfn=s.serializer.loss_functions(e)
    for i in range(offset,offset+50):
        stats=s.update(e,c,gfn,groups_at(i,arm),replay[i],2e-5,meter)
        with (s.ROOT/(arm+'-updates.jsonl')).open('a') as handle:handle.write(json.dumps(stats)+'\n')
    path=s.checkpoint(e,meter,f'{arm}-{offset+50}')
    loss=s.foundation(e,meter);ret=s.generate(e,c,bank('retention'),sp,16,meter,f'{arm}-{offset+50}-retention',legacy=True)
    row=dict(arm=arm,step=offset+50,narrative_nll=loss,retention=ret,checkpoint=str(path.relative_to(s.PROJECT)),sha256=s.sha(path))
    if loss>s.ORIGINAL_NLL*1.05 or ret['content']<72:
        row['hard_stop']=True;history.append(row);s.save(histpath,history)
        raise RuntimeError('MAIN_PRESERVATION_GUARD')
    if (offset+50)%200==0:
        row['development']=s.generate(e,c,bank('development'),sp,48,meter,f'{arm}-{offset+50}-development')
        row['secondary']=s.generate(e,c,bank('secondary'),sp,48,meter,f'{arm}-{offset+50}-secondary')
        row['manual_development_review_required']=True
    history.append(row);s.save(histpath,history);print(json.dumps(row),flush=True)


def diagnosis(meter,replay,sp):
    assert (s.ROOT/'STOP.json').exists()
    result=s.read(s.ROOT/'fit-result.json');last=result['history'][-1]
    e,c=s.load(s.PROJECT/last['checkpoint']);model=c.bind(e);rows=[]
    for row in bank('fit'):
        ids,mask,spans=s.serializer.serialize(sp,row['messages']);span=spans[-1]
        meter.reserve(len(ids)-1,'fit-position-diagnosis')
        logits=model(e.mx.array([ids[:-1]],e.mx.int32))[0].astype(e.mx.float32)
        positions=e.mx.arange(span['start']-1,span['end']-1)
        selected=logits[positions];targets=ids[span['start']:span['end']]
        pred=e.mx.argmax(selected,axis=-1);nll=e.mx.logsumexp(selected,axis=-1)-selected[e.mx.arange(len(targets)),e.mx.array(targets)]
        e.mx.eval(pred,nll);e.memory()
        rows.append(dict(id=row['id'],family=row['family'],targets=targets.tolist(),predictions=np.array(pred).tolist(),target_nll=np.array(nll).tolist()))
    s.save(s.PRIVATE/'fit-position-diagnosis.json',rows)
    summary={}
    for family in sorted({r['family'] for r in rows}):
        rs=[r for r in rows if r['family']==family]
        summary[family]=dict(answers=len(rs),content_positions=sum(len(r['targets'])-1 for r in rs),
            content_correct=sum(sum(a==b for a,b in zip(r['targets'][:-1],r['predictions'][:-1])) for r in rs),
            eos_correct=sum(r['targets'][-1]==r['predictions'][-1] for r in rs),
            premature_eos=sum(sum(p==sp.eos_id() for p in r['predictions'][:-1]) for r in rs),
            all_reference_targets_correct=sum(r['targets']==r['predictions'] for r in rs),
            mean_target_nll=sum(sum(r['target_nll']) for r in rs)/sum(len(r['targets']) for r in rs))
    s.save(s.ROOT/'fit-position-diagnosis.json',dict(summary=summary,teacher_forced=True,new_updates=0,free_generation_is_in_fit_history=True))
    print(json.dumps(summary),flush=True)


def final(meter,replay,sp):
    selection=s.read(s.ROOT/'selection.json')
    models={'baseline':str(s.SOURCE.relative_to(s.PROJECT)),**selection['models']}
    output={}
    for name,path in models.items():
        e,c=s.load(s.PROJECT/path)
        output[name]=s.generate(e,c,bank('test'),sp,48,meter,'final-'+name)
        del e,c;gc.collect()
    s.save(s.ROOT/'final-automatic.json',dict(models=output,manual_blind_review_required=True,not_acceptance=True))


def main():
    phase=sys.argv[1]
    s.assert_frozen()
    assert s.sha(s.SOURCE)==s.SOURCE_SHA
    if (s.ROOT/'STOP.json').exists() and phase!='diagnosis':raise RuntimeError('TERMINAL_STOP')
    token=s.ROOT/('phase-'+phase+('.json' if not phase.startswith('block-') else '-'+str(len(s.read(s.ROOT/(phase[6:]+'-history.json'))) if (s.ROOT/(phase[6:]+'-history.json')).exists() else 0)+'.json'))
    assert not token.exists(),'PHASE_ALREADY_STARTED'
    s.save(token,dict(started=time.time(),phase=phase))
    meter=s.Meter(phase)
    try:
        replay=np.load(s.PRIVATE/'replay.npy').astype(np.int32)
        sp=SentencePieceProcessor(model_file=str(s.serializer.TOK))
        if phase=='preflight':preflight(meter,replay)
        elif phase=='fit':fit(meter,replay,sp)
        elif phase=='baseline':baseline(meter,replay,sp)
        elif phase.startswith('block-'):block(meter,replay,sp,phase[6:])
        elif phase=='diagnosis':diagnosis(meter,replay,sp)
        elif phase=='final':final(meter,replay,sp)
        else:raise ValueError(phase)
        s.assert_frozen()
        print(json.dumps(dict(event='phase_complete',phase=phase,updates=meter.data['updates'],positions=meter.data['positions'])),flush=True)
    except BaseException as ex:
        if not (s.ROOT/'STOP.json').exists():s.save(s.ROOT/'STOP.json',dict(reason=str(ex),type=type(ex).__name__,phase=phase,updates=meter.data['updates'],positions=meter.data['positions']))
        raise
    finally:
        meter.close()
        assert s.sha(s.SOURCE)==s.SOURCE_SHA


if __name__=='__main__':main()
