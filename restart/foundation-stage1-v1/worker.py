"""Single-stage authorized continuation. No action for a second training stage."""
import argparse,concurrent.futures,copy,hashlib,json,math,os,sys,time,traceback
from pathlib import Path
import numpy as np
from engine_support import ROOT,PROJECT,UPSTREAM,CHECKPOINT,GIB,TARGETS,Stream,Meter,save,append,sha,rate

def check():
    if (ROOT/'global-stop.json').exists():raise RuntimeError('GLOBAL_STOP')
    clock=json.loads((ROOT/'clock.json').read_text())
    limit=clock['preflight_deadline_epoch'] if PHASE=='preflight' else min(clock['stage1_deadline_epoch'],clock['overall_original_deadline_epoch'])-300
    if time.time()>=limit:raise TimeoutError('AUTHORIZED_PHASE_DEADLINE')

def state_finite(engine):
    mx=engine.mx
    arrays=list(engine.params.values())
    for opt,names in [(engine.om,engine.matrix),(engine.on,engine.norm)]:
        arrays += [opt.state[k][field] for k in names for field in ['m','v']]
    good=mx.all(mx.stack([mx.all(mx.isfinite(v)) for v in arrays]));mx.eval(good)
    if not bool(good):raise RuntimeError('NONFINITE_MASTER_OR_OPTIMIZER')

def load_engine():
    from engine import MLXEngine
    engine=MLXEngine('bf16',16)
    assert engine.base_step==601 and engine.origin['completed_targets']==78774272
    if 'mlx_rng_state' not in engine.origin:raise RuntimeError('Missing own MLX RNG state')
    
    for i,x in enumerate(engine.origin['mlx_rng_state']):engine.mx.random.state[i][...] = engine.mx.array(x)
    engine.mx.eval(engine.mx.random.state)
    state_finite(engine);save(ROOT/f'{PHASE}-dtype-proof.json',engine.dtype_proof)
    return engine

def snapshot(engine,path):
    import torch
    check();state_finite(engine);s=engine.checkpoint();step=engine.base_step+engine.local_step
    s['optimizer_step']=step;s['completed_targets']=78774272+engine.local_step*TARGETS;s['reserved_targets']=s['completed_targets']
    s['scheduler']={**s['scheduler'],'step':step};s['data_cursor']={**s['data_cursor'],'completed_microbatches':step*32}
    s['benchmark_branch']=False;s['foundation_continuation_stage']=1;s['full_training_authorized']=False;s['next_stage_authorized']=False
    temp=path.with_suffix('.partial');torch.save(s,temp)
    # CPU reload every checkpoint; compare all master/moment tensors exactly.
    reloaded=torch.load(temp,map_location='cpu',weights_only=False)
    assert reloaded['optimizer_step']==step and reloaded['scheduler']['step']==step
    assert reloaded['data_cursor']['completed_microbatches']==step*32
    for k,v in s['model'].items():
        assert v.dtype==torch.float32 and torch.isfinite(v).all() and torch.equal(v,reloaded['model'][k])
    for k,v in s['optimizer']['state'].items():
        for field in ['step','exp_avg','exp_avg_sq']:assert torch.isfinite(v[field]).all() and torch.equal(v[field],reloaded['optimizer']['state'][k][field])
    for a,b in zip(s['mlx_rng_state'],reloaded['mlx_rng_state']):assert np.array_equal(a,b)
    temp.replace(path)
    receipt=dict(path=str(path.relative_to(PROJECT)),sha256=sha(path),optimizer_step=step,completed_targets=s['completed_targets'],additional_updates=engine.local_step,verified_exact_CPU_reload=True,epoch=time.time())
    save(path.with_suffix('.json'),receipt);return receipt

def evaluate(engine,name):
    from tokenizer import Tokenizer
    from mlx.utils import tree_unflatten
    mx=engine.mx
    check();meter=Meter();out=ROOT/name;out.mkdir(exist_ok=False)
    packet=json.loads((ROOT/'packet.json').read_text());frozen=json.loads((ROOT/'packet-freeze.json').read_text())
    assert sha(ROOT/'packet.json')==frozen['packet_sha256'] and sha(ROOT/'validation.npy')==frozen['validation_sha256']
    tok=Tokenizer(str(UPSTREAM/'tokenizer.model'));rng=[mx.array(x) for x in mx.random.state]
    model=engine.model
    model.update(tree_unflatten([(k,v.astype(engine.dtype)) for k,v in engine.params.items()]))
    val=np.load(ROOT/'validation.npy');losses=[]
    for i in range(0,len(val),16):
        check();meter.reserve(len(val[i:i+16])*256,name+'-validation');v=engine.validation(val[i:i+16]);losses.append(v)
    # Compiled loss_fn mutates model parameter references while tracing.
    # Rebind real compute arrays AFTER validation, before direct inference.
    from inference_binding import bind_compute_views
    model=bind_compute_views(engine)
    nll=float(np.mean(losses));assert math.isfinite(nll)
    save(out/'loss.json',dict(validation_nll=nll,targets=131072))
    options=[]
    for kind in ['grammar','grounded']:
      for case in packet[kind]:
        prefix=tok.encode(case['prefix'],bos=True,eos=False);scores=[];lengths=[]
        for option in case['options']:
          check();target=tok.encode(option,bos=False,eos=False);ids=prefix+target;assert len(ids)<=256
          meter.reserve(len(ids)-1,name+'-'+kind+'-scoring')
          logits=model(mx.array([ids[:-1]],dtype=mx.int32)).astype(mx.float32)
          selected=logits[0,len(prefix)-1:,:]
          target_ids=mx.array(target,dtype=mx.int32)
          logp=selected-mx.logsumexp(selected,axis=-1,keepdims=True)
          score=mx.sum(mx.take_along_axis(logp,target_ids[:,None],axis=-1));mx.eval(score);engine.memory()
          value=float(score);assert math.isfinite(value);scores.append(value);lengths.append(len(target))
        assert len(set(lengths))==1
        maximum=max(scores);winners=[i for i,v in enumerate(scores) if abs(v-maximum)<=1e-8]
        correct=len(winners)==1 and winners[0]==case['answer']
        options.append(dict(**case,kind=kind,scores=scores,correct=correct))
      save(out/'option-scores.json',options)
    stories=[]
    for case in packet['stories']:
      check();mx.random.seed(case['seed']);ids=tok.encode(case['prefix'],bos=True,eos=False);generated=[];eos=False
      for j in range(case['max_new_tokens']):
        check();meter.reserve(len(ids),name+'-story-full-input')
        logits=model(mx.array([ids],dtype=mx.int32))[0,-1,:].astype(mx.float32)/.7
        if not bool(mx.all(mx.isfinite(logits))):raise RuntimeError('NONFINITE_LOGITS')
        order=mx.argsort(logits)[::-1];sorted_logits=logits[order];probs=mx.softmax(sorted_logits)
        masked=mx.where(mx.cumsum(probs)-probs>.9,-float('inf'),sorted_logits)
        token=int(order[mx.random.categorical(masked)].item());engine.memory()
        if token==tok.eos_id:eos=True;break
        ids.append(token);generated.append(token)
      stories.append(dict(**case,response=tok.decode(generated),generated_tokens=len(generated),eos=eos))
      save(out/'stories.json',stories)
      if len(stories)%10==0:print(json.dumps(dict(phase=name,stories=len(stories))),flush=True)
    
    for i,x in enumerate(rng):mx.random.state[i][...] = x
    mx.eval(mx.random.state)
    summary=dict(validation_nll=nll,grammar_correct=sum(v['correct'] for v in options if v['kind']=='grammar'),grounded_correct=sum(v['correct'] for v in options if v['kind']=='grounded'),story_cases=len(stories),diagnostic_only=True,teacher_and_primary_review_pending=True)
    save(out/'summary.json',summary);return summary

def preflight():
    import torch
    sys.path.insert(0,str(UPSTREAM));from model import Transformer,ModelArgs
    engine=load_engine();check();stream=Stream(skip_sequences=601*512);fixture=stream.batch(2)
    assert np.array_equal(fixture,Stream(skip_sequences=307712).batch(2))
    np.save(ROOT/'resume-next-two-sequences.npy',fixture)
    meter=Meter();meter.reserve(512,'preflight-native-loss');native=engine.validation(fixture)
    model=Transformer(ModelArgs(**engine.origin['model_args'])).to('mps');model.load_state_dict(engine.origin['model'],strict=True);model.eval()
    with torch.inference_mode():
      meter.reserve(512,'preflight-reference-loss');model(torch.from_numpy(fixture[:,:-1].astype(np.int64)).to('mps'),torch.from_numpy(fixture[:,1:].astype(np.int64)).to('mps'));reference=float(model.last_loss)
    del model;torch.mps.empty_cache()
    if abs(native-reference)>.02:raise RuntimeError('RESUME_NUMERICAL_PARITY_FAILURE')
    receipt=snapshot(engine,ROOT/'initial-roundtrip.pt')
    # Untouched source equals every exported FP32 master and optimizer moment.
    original=torch.load(CHECKPOINT,map_location='cpu',weights_only=False);roundtrip=torch.load(ROOT/'initial-roundtrip.pt',map_location='cpu',weights_only=False)
    for k,v in original['model'].items():assert torch.equal(v,roundtrip['model'][k])
    for k,v in original['optimizer']['state'].items():
      for field in ['step','exp_avg','exp_avg_sq']:assert torch.equal(v[field],roundtrip['optimizer']['state'][k][field])
    save(ROOT/'resume-verification.json',dict(status='PASS',origin_step=engine.base_step,own_checkpoint_sha256=sha(CHECKPOINT),BF16_loss=native,FP32_reference_loss=reference,absolute_difference=abs(native-reference),exact_master_and_moment_roundtrip=True,next_sequence_cursor=307712,RNG_restored=True,weights_updated=False))
    baseline=evaluate(engine,'baseline');check()
    save(ROOT/'preflight-worker-result.json',dict(status='BASELINE_READY_FOR_REVIEW',baseline=baseline,weights_updated=False,origin_unchanged=sha(CHECKPOINT)==json.loads((ROOT/'contract.json').read_text())['reference']['checkpoint_sha256']))

def train():
    import torch
    assert json.loads((ROOT/'preflight-pass.json').read_text())['status']=='PASS'
    contract=json.loads((ROOT/'contract.json').read_text());assert contract['first_stage_training_authorized'] and not contract['next_stage_authorized']
    baseline=json.loads((ROOT/'baseline/summary.json').read_text())['validation_nll']
    engine=load_engine();meter=Meter();stream=Stream(skip_sequences=601*512);start=time.monotonic();updates=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
      future=pool.submit(stream.batch,512)
      for i in range(572):
        check();a=future.result()
        if i<571:future=pool.submit(stream.batch,512)
        meter.reserve(TARGETS,'stage1-training-reservation')
        loss,norm=engine.update(a,check);state_finite(engine)
        record=dict(additional_update=i+1,optimizer_step=601+i+1,loss=loss,gradient_norm=norm,lr=rate(601+i),seconds=time.monotonic()-start,targets=(i+1)*TARGETS)
        updates.append(record);append(ROOT/'updates.jsonl',record)
        save(ROOT/'progress.json',dict(status='TRAINING_FIRST_STAGE_ONLY',**record,tokens_per_second=(i+1)*TARGETS/(time.monotonic()-start),next_stage_authorized=False))
        if (i+1)%10==0:print(json.dumps(record),flush=True)
        if (i+1)%100==0:snapshot(engine,ROOT/'latest.pt')
    receipt=snapshot(engine,ROOT/'stage1-checkpoint.pt')
    result=evaluate(engine,'stage1-evaluation')
    reason='VALIDATION_REGRESSION' if result['validation_nll']>baseline+.20 else 'FIRST_CHECKPOINT_REACHED_WAITING_FOR_OWNER_REVIEW'
    if reason=='VALIDATION_REGRESSION':save(ROOT/'global-stop.json',dict(reason=reason,epoch=time.time()))
    save(ROOT/'stage1-result.json',dict(status=reason,checkpoint=receipt,baseline_nll=baseline,evaluation=result,additional_updates=engine.local_step,additional_training_targets=engine.local_step*TARGETS,training_seconds=time.monotonic()-start,next_stage_authorized=False,conversation_training_started=False,teacher_and_primary_review_pending=True))

if __name__=='__main__':
    PHASE='train'
    sys.path.insert(0,str(UPSTREAM))
    try:
      torch_args=dict()
      import torch;torch.set_num_threads(4)
      train()
    except BaseException as e:
      save(ROOT/(PHASE+'-failure.json'),dict(error=type(e).__name__+': '+str(e),traceback=traceback.format_exc(),epoch=time.time()));raise
