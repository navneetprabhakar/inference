#!/usr/bin/env python3
"""Local MLX/CPU drift interventions; no production recipe or acceptance change."""
# Creator: Navneet Prabhakar
import argparse
from dataclasses import asdict
import gc
import json
from pathlib import Path
import numpy as np
import torch
import mlx.core as mx
from slm.backends import mlx_backend as mb,torch_backend as tb
from slm.common.config import Config,initialize
from slm.common.checkpoint import load
from slm.common.training import Batches,Trainer,Recipe
from slm.data.tokenized import sha
from slm.eval.portability import environment,get_batches
from slm.eval.precision import forward64

ANCHORS=(0,49,59,62,63,64,69,79,99)
BOUNDS={'weight':1e-5,'m':1e-6,'v':1e-6}


def state(trainer):
    return trainer.impl.export({**{'weight:'+k:v for k,v in trainer.params.items()},
        **{s+':'+k:v[i] for k,v in trainer.moments.items() for i,s in enumerate(('m','v'))}})


def differences(actual,reference):
    if actual.keys()!=reference.keys():raise ValueError('State inventories differ')
    result={}
    for group,atol in BOUNDS.items():
        names=[k for k in actual if k.startswith(group+':')]
        if not names:continue
        if any(actual[k].shape!=reference[k].shape or not np.isfinite(actual[k]).all() or not np.isfinite(reference[k]).all() for k in names):
            raise ValueError('Invalid state comparison')
        errors={k:float(np.max(np.abs(actual[k].astype(np.float64)-reference[k]))) for k in names}
        result[group]={'max_abs':max(errors.values()),'worst_tensor':max(errors,key=errors.get),
            'violations':sum(int((~np.isclose(actual[k],reference[k],atol=atol,rtol=1e-4)).sum()) for k in names),
            'atol':atol,'rtol':1e-4}
    return result


def exact(actual,reference):
    if actual.keys()!=reference.keys():raise AssertionError('Control inventory differs')
    for k in actual:np.testing.assert_array_equal(actual[k],reference[k])


class Hybrid:
    """Diagnostic adapter; canonical Torch storage, independent arithmetic choices."""
    def __init__(self,gradient,optimizer):self.gradient=gradient;self.optimizer=optimizer
    def export(self,params):return tb.export(params)
    def value_and_grad(self,params,config,*arrays,**kwargs):
        if self.gradient=='torch':return tb.value_and_grad(params,config,*arrays,**kwargs)
        value,grads=mb.value_and_grad(mb.load(config,tb.export(params)),config,
            *(mx.array(a.detach().numpy()) for a in arrays),**kwargs)
        return torch.tensor(float(value)),{k:torch.tensor(v) for k,v in mb.export(grads).items()}
    def adamw(self,params,grads,moments,*args,**kwargs):
        if self.optimizer=='torch':return tb.adamw(params,grads,moments,*args,**kwargs)
        pm={k:mx.array(v) for k,v in tb.export(params).items()};gm={k:mx.array(v) for k,v in tb.export(grads).items()}
        sm={k:tuple(mx.array(v.detach().numpy()) for v in pair) for k,pair in moments.items()}
        weights,out=mb.adamw(pm,gm,sm,*args,**kwargs)
        return ({k:torch.tensor(v,requires_grad=True) for k,v in mb.export(weights).items()},
            {k:tuple(torch.tensor(np.array(v)) for v in pair) for k,pair in out.items()})


def oracle(weights,config,batch):
    params={k:torch.tensor(v,dtype=torch.float64,requires_grad=True) for k,v in weights.items()}
    x,y,mask=batch;logits,_=forward64(params,config,torch.tensor(x))
    losses=torch.nn.functional.cross_entropy(logits.flatten(0,1),torch.tensor(y).flatten(),reduction='none').reshape(y.shape)
    value=(losses*torch.tensor(mask,dtype=torch.float64)).sum()/mask.sum()
    gradients=torch.autograd.grad(value,tuple(params.values()))
    return float(value.detach()),{k:v.detach().numpy().copy() for k,v in zip(params,gradients)}


def gradient_errors(actual,reference,value,loss):
    entries={};sign_max=0.;signs=0;total_error=total_norm=0.
    for k,expected in reference.items():
        error=actual[k].astype(np.float64)-expected;n=float(np.square(expected).sum());e=float(np.square(error).sum())
        disagree=actual[k]*expected<0;signs+=int(disagree.sum())
        if disagree.any():sign_max=max(sign_max,float(np.abs(expected[disagree]).max()))
        total_error+=e;total_norm+=n
        entries[k]={'relative_l2':float(np.sqrt(e/max(n,1e-60))),'max_abs':float(np.abs(error).max()),'reference_l2':float(np.sqrt(n))}
    return {'loss':value,'loss_abs_error':abs(value-loss),'gradient_max_abs':max(v['max_abs'] for v in entries.values()),
        'gradient_global_relative_l2':float(np.sqrt(total_error/max(total_norm,1e-60))),
        'sign_disagreements':signs,'largest_reference_magnitude_at_sign_disagreement':sign_max,
        'largest_tensor_relative_errors':dict(sorted(entries.items(),key=lambda item:item[1]['relative_l2'],reverse=True)[:5])}


def finite_difference(weights,config,batch,reference):
    name='layers.0.v';index=np.unravel_index(np.abs(reference[name]).argmax(),reference[name].shape)
    analytical=float(reference[name][index]);params={k:torch.tensor(v,dtype=torch.float64) for k,v in weights.items()};rows=[]
    x,y,mask=batch
    with torch.no_grad():
        for h in (1e-5,1e-6):
            values=[]
            for sign in (-1,1):
                changed=dict(params);changed[name]=params[name].clone();changed[name][index]+=sign*h
                logits,_=forward64(changed,config,torch.tensor(x))
                ce=torch.nn.functional.cross_entropy(logits.flatten(0,1),torch.tensor(y).flatten(),reduction='none').reshape(y.shape)
                values.append(float((ce*torch.tensor(mask,dtype=torch.float64)).sum()/mask.sum()))
            estimate=(values[1]-values[0])/(2*h)
            # Diagnostic oracle-consistency check only, not a model-state tolerance.
            np.testing.assert_allclose(estimate,analytical,rtol=3e-5,atol=1e-8)
            rows.append({'tensor':name,'index':[int(i) for i in index],'h':h,'analytical':analytical,'finite_difference':estimate,
                'abs_error':abs(estimate-analytical),'oracle_consistency_passed':True})
    return rows


def flat(impl,weights,moments):
    return impl.export({**{'weight:'+k:v for k,v in weights.items()},
        **{s+':'+k:pair[i] for k,pair in moments.items() for i,s in enumerate(('m','v'))}})


def common_anchor(raw,config,batch,step,recipe):
    weights={k[7:]:v for k,v in raw.items() if k.startswith('weight:')}
    params_t=tb.load(config,weights);params_m=mb.load(config,weights)
    mt={k:(torch.tensor(raw['m:'+k]),torch.tensor(raw['v:'+k])) for k in weights} if step else {}
    mm={k:tuple(mx.array(v.numpy()) for v in pair) for k,pair in mt.items()}
    vt,gt=tb.value_and_grad(params_t,config,*(torch.tensor(v) for v in batch),embedding_implementation=recipe.embedding_implementation)
    vm,gm=mb.value_and_grad(params_m,config,*(mx.array(v) for v in batch),embedding_implementation=recipe.embedding_implementation)
    loss,ref=oracle(weights,config,batch)
    errors={'torch':gradient_errors(tb.export(gt),ref,float(vt.detach()),loss),'mlx':gradient_errors(mb.export(gm),ref,float(vm),loss)}
    opts={k:v for k,v in asdict(recipe).items() if k not in ('lr','warmup_tokens','loss_implementation','embedding_implementation','accumulation_steps')}
    opts['lr']=recipe.rate((step+1)*batch[0].size)
    wt,st=tb.adamw(params_t,gt,mt,step+1,**opts)
    wc,sc=mb.adamw(params_m,{k:mx.array(v) for k,v in tb.export(gt).items()},mm,step+1,**opts)
    wo,so=mb.adamw(params_m,gm,mm,step+1,**opts)
    return {'state_step':step,'oracle_loss':loss,'gradient_errors':errors,
        'oracle_finite_difference':finite_difference(weights,config,batch,ref) if step in (0,99) else [],
        'optimizer_only_common_cpu_gradient':differences(flat(mb,wc,sc),flat(tb,wt,st)),
        'whole_single_update_own_gradients':differences(flat(mb,wo,so),flat(tb,wt,st))}


def compare_runs(config,data,recipe,name,artifacts=None):
    weights=initialize(config,42);perturbation=None
    if name=='cpu_one_embedding_ulp':
        before=float(weights['embedding'][1,0]);weights['embedding'][1,0]=np.nextafter(weights['embedding'][1,0],np.float32(np.inf))
        perturbation={'tensor':'embedding','index':[1,0],'before':before,'after':float(weights['embedding'][1,0]),
            'absolute_change':abs(float(weights['embedding'][1,0])-before),'changed_coordinates':1}
    elif name=='cpu_all_weights_one_ulp':
        original=weights;weights={k:np.nextafter(v,np.float32(np.inf)) for k,v in weights.items()}
        perturbation={'changed_coordinates':sum(v.size for v in weights.values()),'maximum_abs_change':max(float(np.abs(weights[k]-v).max()) for k,v in original.items())}
    candidate=Trainer(config,weights,data,'mlx' if name=='baseline' else 'torch',recipe=recipe)
    reference=Trainer(config,initialize(config,42),data,recipe=recipe)
    if name.endswith('optimizer') or name=='hybrid_passthrough':
        candidate.impl=Hybrid('mlx' if name=='mlx_gradient_cpu_optimizer' else 'torch','mlx' if name=='cpu_gradient_mlx_optimizer' else 'torch')
    rows=[];first=None;loss_failures=0
    for index in range(100):
        if artifacts is not None and index in ANCHORS:
            for tag,t in [('mlx',candidate),('torch',reference)]:np.savez(artifacts/f'{tag}-{index}.npz',**state(t))
        a=candidate.update();b=reference.update();error=differences(state(candidate),state(reference))
        if name=='hybrid_passthrough':
            exact(state(candidate),state(reference))
            if a!=b:raise AssertionError('Passthrough control changes metrics')
        if first is None and any(v['violations'] for v in error.values()):first={'step':index+1,'errors':error}
        loss_failures+=not np.isclose(a['loss'],b['loss'],atol=1e-5,rtol=1e-4)
        rows.append({'step':index+1,'candidate_loss':a['loss'],'reference_loss':b['loss'],'errors':error})
    return {'first_failure':first,'final_errors':error,'candidate_loss':a['loss'],'reference_loss':b['loss'],
        'perturbation':perturbation,'history':rows,'loss_outside_original_bounds':int(loss_failures),'exact_passthrough_control':name=='hybrid_passthrough'}


def full_anchor(fixture):
    fixture=Path(fixture);manifest=fixture/'retired-bundle.json'
    if not manifest.exists():manifest=fixture/'bundle.json'
    pinned=json.loads(manifest.read_text())['files']
    files=['fixture.json','batches.npz']+[str(p.relative_to(fixture)) for p in (fixture/'initial').rglob('*') if p.is_file()]
    for name in files:
        if sha(fixture/name)!=pinned[name]:raise ValueError('Retained fixture checksum differs')
    config,weights=load(fixture/'initial/model');batch=get_batches(fixture).items[0];loss,reference=oracle(weights,config,batch);results={}
    for formulation in (tb.DEFAULT_LOSS_IMPLEMENTATION,tb.STABLE_LOSS_IMPLEMENTATION):
        for backend,impl in [('torch',tb),('mlx',mb)]:
            params=impl.load(config,weights);arrays=tuple(torch.tensor(v) if backend=='torch' else mx.array(v) for v in batch)
            value,g=impl.value_and_grad(params,config,*arrays,loss_implementation=formulation)
            value=float(value.detach()) if backend=='torch' else float(value)
            results[backend+'-'+formulation]=gradient_errors(impl.export(g),reference,value,loss)
            del params,arrays,g;gc.collect();mx.clear_cache()
    return {'parameters':config.parameter_count,'binding_manifest_sha256':sha(manifest),'binding_manifest_name':manifest.name,
        'verified_retained_files':files,'checkpoint_manifest_sha256':sha(fixture/'initial/manifest.json'),'fixture_batch':0,
        'oracle_loss':loss,'results':results,'scope':'One common retained checkpoint/batch; missing retired trajectory probes are not revalidated'}


def run(output,artifacts,full_fixture=None):
    output,artifacts=Path(output),Path(artifacts)
    if output.exists() or artifacts.exists():raise FileExistsError('Fresh output/artifact destinations required')
    artifacts.mkdir(parents=True);torch.set_num_threads(4);config=Config()
    x=np.tile(np.array([[1,2,1,3,2,1,1,2]],np.int64),(2,1));batch=(x,np.roll(x,-1,axis=1),np.ones(x.shape,np.float32))
    data=Batches([batch]*100,64);recipe=Recipe(embedding_implementation='dense-onehot-v1',warmup_tokens=100)
    baseline=compare_runs(config,data,recipe,'baseline',artifacts);counterfactuals={}
    for name in ('hybrid_passthrough','cpu_one_embedding_ulp','cpu_all_weights_one_ulp','cpu_gradient_mlx_optimizer','mlx_gradient_cpu_optimizer'):
        counterfactuals[name]=compare_runs(config,data,recipe,name)
    anchors=[]
    for tag in ('torch','mlx'):
        for step in ANCHORS:
            with np.load(artifacts/f'{tag}-{step}.npz',allow_pickle=False) as raw:record=common_anchor(dict(raw),config,batch,step,recipe)
            record['anchor']=tag;anchors.append(record)
    rng=np.random.default_rng(8);golden=(rng.integers(0,64,(2,12),dtype=np.int32),rng.integers(0,64,(2,12),dtype=np.int32),rng.integers(0,2,(2,12)).astype(np.float32))
    control=compare_runs(config,Batches([golden]*100,64),Recipe(embedding_implementation='dense-onehot-v1',warmup_tokens=0),'baseline')
    if control['first_failure'] or control['loss_outside_original_bounds']:raise AssertionError('Existing golden control regressed')
    common_pass=all(not m['violations'] for a in anchors for group in ('optimizer_only_common_cpu_gradient','whole_single_update_own_gradients') for m in a[group].values())
    for name,record in [('baseline',baseline),*counterfactuals.items()]:
        history=record.pop('history');path=artifacts/(name+'-history.json');path.write_text(json.dumps(history,indent=2)+'\n')
        keep={s+1 for s in ANCHORS}
        if record['first_failure']:keep.add(record['first_failure']['step'])
        record['history_samples']=[v for v in history if v['step'] in keep];record['history_artifact']=str(path)
    report={'creator':'Navneet Prabhakar','audit_completed':True,'trajectory_gate_passed':baseline['first_failure'] is None,
        'tolerances_changed':False,'production_recipe_changed':False,'parameters':config.parameter_count,'initialization_seed':42,
        'recipe':asdict(recipe),'torch_threads':torch.get_num_threads(),'environment':{'mlx':environment('mlx','gpu'),'torch':environment('torch','cpu')},
        'baseline':baseline,'counterfactuals':counterfactuals,'common_state_anchors':anchors,'all_common_updates_within_original_bounds':common_pass,
        'golden_control':{'updates':100,'first_failure':control['first_failure'],'final_errors':control['final_errors']},
        'full_anchor':full_anchor(full_fixture) if full_fixture else None,'new_teacher_calls':0,'new_cloud_jobs':0,
        'scope':'Fixed-state arithmetic and deliberately perturbed tiny training diagnostics; no acceptance-policy change or learned-quality claim',
        'source_sha256':{str(p):sha(p) for p in map(Path,[Path(__file__).resolve().relative_to(Path.cwd()),'src/slm/common/training.py','src/slm/common/config.py',
            'src/slm/backends/mlx_backend.py','src/slm/backends/torch_backend.py','src/slm/eval/precision.py','tests/test_resume.py'])},
        'artifact_sha256':{str(p):sha(p) for p in sorted(artifacts.iterdir())}}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--artifacts',required=True);p.add_argument('--full-fixture')
    p.add_argument('--require-trajectory-pass',action='store_true');args=p.parse_args();result=run(args.output,args.artifacts,args.full_fixture)
    print(json.dumps({'audit_completed':True,'trajectory_gate_passed':result['trajectory_gate_passed'],'first_failure':result['baseline']['first_failure']['step'] if result['baseline']['first_failure'] else None}))
    if args.require_trajectory_pass and not result['trajectory_gate_passed']:raise SystemExit(1)
