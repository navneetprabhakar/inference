"""Tiny synthetic CPU state-format tests; no live checkpoint, MLX or GPU reads."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import time

import numpy as np
import torch

from gpt2 import Config,GPT2,next_token_loss
from train import optimizer_for
import own_base_neutral_state as neutral


def update(model,opt,batch):
    opt.zero_grad(set_to_none=True)
    loss=next_token_loss(model,batch);loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
    opt.step()
    return float(loss.item())


def progress(campaign, initial=2):
    return dict(campaign_step=campaign,optimizer_step=initial+campaign,initial_optimizer_step=initial,
                trained_tokens=36*campaign,reserved_tokens=36*(campaign+1),targets_per_update=36,
                initial_source_offset=100,source_offset=100+36*campaign)


def run():
    started=time.monotonic();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    cfg=Config(vocabulary=43,context=16,width=32,heads=4,depth=2)
    cases=[];negative_checks=0
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary)
        for seed in (4817,5209,6211):
            for beta in (.95,.95**(8192/524288)):
                torch.manual_seed(seed);model=GPT2(cfg).cpu();opt=optimizer_for(model)
                for g in opt.param_groups:g['betas']=(.9,beta);g['lr']=.001;g['params'].reverse()
                batches=torch.randint(0,cfg.vocabulary,(8,3,13),device='cpu');batches[:,:,3]=batches[:,:,1]
                for batch in batches[:3]:update(model,opt,batch)
                identity=dict(model=asdict(cfg),tokenizer={'fixture':'a'*64},seed=seed,
                              initialization=dict(mode='own_pretraining',path='tiny-random-parent.pt',sha256='b'*64,random_lineage_root='c'*64),
                              scheduler=dict(mode='fixed-fixture',learning_rate=.001),corpus={'sha256':'d'*64},
                              protocol=dict(target_tokens=36000),code={'gpt2.py':neutral.checksum(Path(__file__).with_name('gpt2.py'))})
                source_file=root/f'source-{seed}-{beta}.pt'
                cpu_rng=torch.get_rng_state();mps_rng=torch.arange(32,dtype=torch.uint8)
                torch.save(dict(model=model.state_dict(),optimizer=opt.state_dict(),identity=identity,
                                progress=progress(1),cpu_rng=cpu_rng,mps_rng=mps_rng),source_file)
                source=dict(path=str(source_file),bytes=source_file.stat().st_size,sha256=neutral.checksum(source_file))
                expected=dict(expected_identity=identity,expected_source=source,expected_progress=progress(1),
                              expected_optimizer=neutral.optimizer_policy(opt))
                meta,arrays=neutral.export_objects(model,opt,identity=identity,source=source,progress=progress(1),
                                                   cpu_rng=cpu_rng,mps_rng=mps_rng,**expected)
                directory=root/f'bundle-{seed}-{beta}';neutral.write_bundle(directory,meta,arrays,**expected)
                loaded_meta,loaded=neutral.read_bundle(directory,**expected)
                assert loaded_meta==meta and all(np.array_equal(arrays[n],loaded[n]) for n in arrays)
                target=GPT2(cfg).cpu();target_opt=optimizer_for(target)
                result=neutral.import_objects(target,target_opt,loaded_meta,loaded,**expected)
                assert torch.equal(result['cpu_rng'],cpu_rng) and torch.equal(result['mps_rng'],mps_rng)
                assert result['progress']['campaign_step']==1 and result['progress']['optimizer_step']==3
                round_meta,round_arrays=neutral.export_objects(target,target_opt,identity=identity,source=source,progress=progress(1),
                                                               cpu_rng=result['cpu_rng'],mps_rng=result['mps_rng'],**expected)
                assert round_meta==meta and all(np.array_equal(round_arrays[n],arrays[n]) for n in arrays)
                traces=[]
                for step,batch in enumerate(batches[3:],2):
                    lr=.001/(step-1)
                    for o in (opt,target_opt):
                        for g in o.param_groups:g['lr']=lr
                    one=update(model,opt,batch);two=update(target,target_opt,batch)
                    assert one==two
                    for (n,p),(other_n,q) in zip(model.named_parameters(),target.named_parameters()):
                        assert n==other_n and torch.equal(p,q)
                        for kind in ('exp_avg','exp_avg_sq','step'):assert torch.equal(opt.state[p][kind],target_opt.state[q][kind])
                    traces.append(one)
                # Every malformed import must fail before destination parameter mutation.
                tests=[]
                for name in ('wrong_identity','wrong_source','wrong_scheduler','wrong_tokenizer','missing_moment',
                             'extra_tensor','wrong_shape','non_fp32','nonfinite','negative_second_moment','bad_step',
                             'duplicate_group','wrong_group','bad_progress','wrong_beta','missing_rng','rng_dtype',
                             'mps_absence','wrong_heads'):
                    mm=copy.deepcopy(meta);aa={n:a.copy() for n,a in arrays.items()};ee=copy.deepcopy(expected)
                    if name=='wrong_identity':mm['identity']['seed']+=1
                    elif name=='wrong_source':mm['source']['sha256']='e'*64
                    elif name=='wrong_scheduler':mm['identity']['scheduler']['learning_rate']=.002
                    elif name=='wrong_tokenizer':mm['identity']['tokenizer']['fixture']='f'*64
                    elif name=='missing_moment':del aa['m::tokens.weight']
                    elif name=='extra_tensor':aa['extra']=np.array(1)
                    elif name=='wrong_shape':aa['weight::tokens.weight']=aa['weight::tokens.weight'][:1]
                    elif name=='non_fp32':aa['m::tokens.weight']=aa['m::tokens.weight'].astype(np.float64)
                    elif name=='nonfinite':aa['m::tokens.weight'][0,0]=np.nan
                    elif name=='negative_second_moment':aa['v::tokens.weight'][0,0]=-1
                    elif name=='bad_step':aa['step::tokens.weight']=np.array(4.,dtype=np.float32)
                    elif name=='duplicate_group':mm['groups'][0].append(mm['groups'][0][0])
                    elif name=='wrong_group':mm['groups'][0][0],mm['groups'][1][0]=mm['groups'][1][0],mm['groups'][0][0]
                    elif name=='bad_progress':
                        mm['progress']['source_offset']+=1;ee['expected_progress']=copy.deepcopy(mm['progress'])
                    elif name=='wrong_beta':mm['optimizer'][0]['betas'][1]=.9
                    elif name=='missing_rng':del aa['cpu_rng']
                    elif name=='rng_dtype':aa['cpu_rng']=aa['cpu_rng'].astype(np.int32)
                    elif name=='mps_absence':mm['mps_rng_present']=False
                    elif name=='wrong_heads':
                        mm['identity']['model']['heads']=8;ee['expected_identity']=copy.deepcopy(mm['identity'])
                    before={n:p.detach().clone() for n,p in target.named_parameters()}
                    try:neutral.import_objects(target,target_opt,mm,aa,**ee)
                    except ValueError:pass
                    else:raise AssertionError('invalid state accepted: '+name)
                    assert all(torch.equal(p,before[n]) for n,p in target.named_parameters())
                    tests.append(name);negative_checks+=1
                # Validate checksums against changed bytes, independently of semantics.
                body=directory/'state.npz'
                with body.open('r+b') as stream:stream.seek(-1,2);stream.write(b'X')
                try:neutral.read_bundle(directory,**expected)
                except ValueError:negative_checks+=1
                else:raise AssertionError('changed NPZ accepted')
                # Optional MPS RNG absent is valid and does not invoke any MPS API.
                missing=copy.deepcopy(meta);missing['mps_rng_present']=False
                aa={n:a.copy() for n,a in arrays.items()};aa['mps_rng']=np.empty(0,dtype=np.uint8)
                neutral.validate(missing,aa,**expected)
                cases.append(dict(seed=seed,beta2=beta,parameters=sum(p.numel() for p in model.parameters()),
                                  arrays=len(arrays),exact_roundtrip=True,exact_continuation_updates=len(traces),
                                  distinct_campaign_optimizer_steps=True,reversed_source_group_order=True,
                                  refusal_checks=tests+['corrupt_npz'],mps_rng='synthetic opaque CPU bytes only'))
    _,full=neutral.shapes_for(Config())
    assert sum(np.prod(s) for s in full.values())==124439808
    result=dict(state='passed',cases=cases,negative_checks=negative_checks,device='cpu',gpu_operations=False,
                live_checkpoint_read=False,full_model_allocated=False,full_parameter_count_arithmetic_only=124439808,
                elapsed_seconds=time.monotonic()-started,
                limitation='Pure state format; trusted source objects/receipts supplied by caller. Production ancestry loader and full-model validation remain pending.')
    print(json.dumps(result,indent=2))
    return result

if __name__=='__main__':run()
