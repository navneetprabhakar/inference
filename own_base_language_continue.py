"""New finite Torch own-base continuation; no defaults, packing, or implicit launch.

Production CLI requires a reviewed hash-pinned spec and admitted data. Tiny CPU
fixtures call run_training directly; they cannot bypass the production CLI gates.
"""
import argparse
from dataclasses import asdict
import json
import math
import resource
import shutil
import sys
import time
from pathlib import Path
import torch
import numpy as np
from tokenizer import ASSETS
import torch.nn.functional as F
import checkpoint
from gpt2 import Config,GPT2
from train import optimizer_for
from base_train import precision,compare_losses
from guards import Guard
from own_base_language_control import LanguageCampaign,CampaignStop
from own_base_language_streams import AdmittedStreams,pinned,sha
from own_base_language_data import require,integer,aggregate_validation
ROOT=Path(__file__).resolve().parent
_TICKET=None
REQUIRED_CODE={'own_base_language_continue.py','own_base_language_control.py','own_base_language_streams.py','own_base_language_data.py',
 'own_base_language_launch.py','own_base_dev_run.py','checkpoint.py','guards.py','gpt2.py','train.py','base_train.py','own_base_sft_train.py','optimizer_ablation_train.py',
 'optimizer_ablation_report.py','base_run_control.py','own_base_sft_control.py','tokenizer.py','pretrain.py','pretrained_base.py','own_base_language_parent.py'}


def validate_launch(spec,run):
    require(spec.get('state')=='reviewed_for_own_language_continuation' and spec.get('schema')==1,'reviewed continuation spec required')
    run=Path(run);require(run==run.resolve() and run.parent==ROOT/'runs' and str(run)==spec['run'] and not run.is_symlink(),'canonical direct runs child required')
    require(spec['model']==asdict(Config()),'existing124M parent architecture required')
    require(spec['torch_version']==str(torch.__version__) and spec['numpy_version']==np.__version__ and spec['python_version']==sys.version,'runtime versions differ')
    require(Path(sys.executable).absolute()==Path(spec['python']).absolute(),'frozen worker interpreter differs')
    require(spec['tokenizer']==dict(vocabulary=50257,eot=50256,identity=ASSETS),'parent GPT2 tokenizer assets differ')
    require(REQUIRED_CODE<=set(spec['code_sha256']),'all runtime dependency pins required')
    for name,h in spec['code_sha256'].items():
        path=ROOT/name;require(path.resolve().is_relative_to(ROOT) and sha(path)==h,'runtime changed: '+name)
    require(spec['length'] in (512,1024) and spec['microbatch']==(2 if spec['length']==512 else 1) and spec['accumulation']==8,'explicit8192target layout required')
    require(type(spec['bf16']) is bool,'explicit precision required')
    require(spec['scheduler']['mode']=='constant' and math.isfinite(spec['scheduler']['lr']) and spec['scheduler']['lr']>0,'explicit constant continuation LR required')
    for key in ('training_goal','attempted_targets','evaluation_targets','active_seconds','calendar_seconds','lease_seconds','checkpoint_seconds','checkpoint_margin_seconds','checkpoint_bytes','disk_headroom_bytes','cpu_rss_limit_bytes'):
        require(isinstance(spec[key],(int,float)) and not isinstance(spec[key],bool) and math.isfinite(spec[key]) and spec[key]>0,'explicit finite '+key)
    require(integer(spec['training_goal']) and integer(spec['attempted_targets']) and spec['training_goal']%8192==spec['attempted_targets']%8192==0 and spec['training_goal']<=spec['attempted_targets'],'wholeupdate finite goal/attempt budget')
    require(spec['checkpoint_margin_seconds'] < spec['lease_seconds'] and spec['checkpoint_seconds'] <= spec['lease_seconds'],'checkpoint cadence/margin must fit lease')
    milestones=spec['evaluation_milestones'];require(milestones==sorted(set(milestones)) and milestones[0]==0 and milestones[-1]==spec['training_goal'] and all(integer(x) and x%8192==0 for x in milestones),'explicit aligned baseline/endpoint evaluation milestones')
    requiredstops={str(ROOT/'runs/STOP'),str(run/'STOP'),str(ROOT/'runs/own-base-foundation-01/STOP')}|{str(ROOT/f'runs/optimizer-ablation-v1-{name}/STOP') for name in ('preserve-095','reset-095','reset-scaled')}
    require(requiredstops<=set(spec['stop_paths']),'ancestor STOP inheritance required')
    evidence=spec['hardware_evidence']
    require(evidence['kind']=='completed_optimizer_screen_torch512' and evidence['report']==spec['optimizer_report'],'actual hardware evidence adapter required')
    report=pinned(evidence['report']);common=report['common']
    require(report.get('state')=='screen-completed' and report.get('selected_optimizer_recipe')=='preserve-095' and common['length']==spec['length']==512 and common['microbatch']==spec['microbatch']==2 and common['targets_per_update']==8192 and common['bf16']==spec['bf16'] is True,'completed matching Torch workload evidence required')
    gate=spec['external_milestone_gate'];require(gate['milestones']==milestones,'behavior gate at every fixed source-evaluation milestone')
    protocol=pinned(gate['protocol']);require(protocol['series']==['original-web-256','context-pairs-32','raw-continuations-32'],'unchanged external transfer series required')
    require(all(isinstance(protocol['budgets'][k],(int,float)) and protocol['budgets'][k]>0 for k in ('attempted_targets','active_seconds','calendar_seconds')),'explicit external evaluation budgets required')


def check_external(spec,run):
    if _TICKET is not None:
        import own_base_dev_run as runtime
        if runtime.remaining(_TICKET)<=10:raise CampaignStop('paused-lease','owned watchdog deadline margin')
        Path(_TICKET['heartbeat']).write_text(str(time.time()))
    if any(Path(p).exists() for p in spec['stop_paths']):raise CampaignStop('interrupted','explicit STOP')
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
    if peak>spec['cpu_rss_limit_bytes']:raise CampaignStop('paused-resource','explicit RSS ceiling')
    if shutil.disk_usage(run if run.exists() else run.parent).free<spec['disk_headroom_bytes']+spec['checkpoint_bytes']:
        raise CampaignStop('paused-resource','checkpoint disk headroom')


def optimizer_step(opt):
    steps=[]
    for group in opt.param_groups:
        for param in group['params']:
            state=opt.state[param];require(set(state)=={'step','exp_avg','exp_avg_sq'},'complete AdamW state required')
            step=float(state['step']);require(step.is_integer() and step>=0,'valid optimizer step');steps.append(int(step))
            for key in ('exp_avg','exp_avg_sq'):
                v=state[key];require(v.dtype==torch.float32 and v.shape==param.shape and bool(torch.isfinite(v).all()),'optimizer moment integrity')
            require(not bool((state['exp_avg_sq']<0).any()),'negative second moment')
    require(steps and len(set(steps))==1,'consistent perparameter optimizer steps');return steps[0]


def restore(model,payload,device):
    model.load_state_dict(payload['model'],strict=True);opt=optimizer_for(model);opt.load_state_dict(payload['optimizer'])
    # CPU fixture loads must not alias the retained parent payload. MPS loads
    # already copied state, but explicit ownership is the same in both paths.
    for state in opt.state.values():
        for key,value in state.items():
            if isinstance(value,torch.Tensor):state[key]=value.detach().clone()
    torch.set_rng_state(payload['cpu_rng'])
    if device=='mps':torch.mps.set_rng_state(payload['mps_rng'])
    return opt,optimizer_step(opt)


@torch.inference_mode()
def evaluate(model,data,campaign,check,device):
    model.eval();results=[]
    for window in data.validation['windows']:
        check();campaign.reserve_evaluation(window['targets'])
        row=torch.from_numpy(data.validation_row(window)).to(device).unsqueeze(0)
        loss=F.cross_entropy(model(row[:,:-1]).flatten(0,1),row[:,1:].flatten(),reduction='sum')
        value=float(loss.item());require(math.isfinite(value),'nonfinite heldout NLL')
        results.append(dict(source=window['source'],id=window['id'],targets=window['targets'],nll=value))
    return aggregate_validation(data.validation,results)


def external_milestone(spec,run,campaign,trained):
    gate=spec.get('external_milestone_gate')
    if gate is None:return  # Tiny core fixtures only; production validate requires it.
    if trained not in gate['milestones']:return
    entry=campaign.ledger['checkpoints'][0]
    request=dict(trained_tokens=trained,checkpoint=entry,protocol=gate['protocol'])
    request_path=run/f'milestone-{trained}-request.json'
    if request_path.exists():require(json.loads(request_path.read_text())==request,'existing milestone request differs from accepted checkpoint')
    else:checkpoint._atomic_json(request_path,request)
    decision_path=run/f'milestone-{trained}-decision.json'
    if not decision_path.exists():raise CampaignStop('paused-milestone','root-owned external transfer evaluation required')
    decision=json.loads(decision_path.read_text())
    require(decision['state']=='root_reviewed_external_milestone' and decision['request_sha256']==sha(request_path),'external milestone decision binds exact accepted checkpoint/request')
    require(decision['protocol_sha256']==gate['protocol']['sha256'] and decision['result_receipts'],'external evaluation protocol/results binding')
    for pin in decision['result_receipts']:pinned(pin)
    require(decision['decision'] in ('continue','stop'),'explicit root milestone decision')
    if decision['decision']=='stop':raise CampaignStop('diverged','root external transfer gate stopped continuation')


def run_training(spec,run,data,parent,*,device='mps',guard_factory=Guard,model_config=None,after_update=None):
    """Core loop, also usable with tiny explicit CPU fixtures (no CLI bypass)."""
    torch.set_num_threads(1)
    config=model_config or Config();run=Path(run);resume=spec.get('_resume',False)
    require(data.schedule.length==spec['length'],'schedule layout')
    data.schedule.state_at(spec['training_goal']//8192)  # Capacity/admitted finite pass check.
    identity=dict(seed=spec['seed'],model=asdict(config),tokenizer=spec['tokenizer'],
        initialization=spec['initialization'],corpus=dict(schedule_sha256=data.schedule.identity,validation_sha256=data.validation['sha256']),
        scheduler=spec['scheduler'],protocol={k:v for k,v in spec.items() if k!='_resume'},code=spec.get('code_sha256',{}))
    with LanguageCampaign(run,identity,training_goal=spec['training_goal'],token_limit=spec['attempted_targets'],evaluation_limit=spec['evaluation_targets'],
        active_seconds=spec['active_seconds'],calendar_seconds=spec['calendar_seconds'],lease_seconds=spec['lease_seconds'],resume=resume,guard_factory=guard_factory) as campaign:
        def check():campaign.check();check_external(spec,run)
        check();model=GPT2(config).to(device);source=campaign.load() if resume else parent
        opt,loaded_step=restore(model,source,device)
        parent_steps={int(float(state['step'])) for state in parent['optimizer']['state'].values()}
        require(len(parent_steps)==1,'selected parent optimizer step disagreement')
        initial_step=source['initial_optimizer_step'] if resume else loaded_step
        require(initial_step==next(iter(parent_steps)),'resume initial optimizer ancestry differs')
        cursor=source['cursor'] if resume else data.schedule.initial();history=source['history'] if resume else [];best=source['best'] if resume else {};bad=source['bad'] if resume else {}
        require(loaded_step==initial_step+cursor['updates'] and campaign.ledger['trained_tokens']==cursor['updates']*8192,'optimizer/campaign/source cursor mismatch')
        data.schedule.validate_resume(cursor);last_save=time.monotonic()
        def save():
            nonlocal last_save
            campaign.save(dict(step=cursor['updates'],model=model.state_dict(),optimizer=opt.state_dict(),cursor=cursor,initial_optimizer_step=initial_step,
                cpu_rng=torch.get_rng_state(),mps_rng=torch.mps.get_rng_state() if device=='mps' else None,history=history,best=best,bad=bad))
            last_save=time.monotonic()
        try:
            if not resume:save()
            while True:
                check();trained=cursor['updates']*8192
                if trained in spec['evaluation_milestones'] and not any(h['trained_tokens']==trained for h in history):
                    result=evaluate(model,data,campaign,check,device);result['trained_tokens']=trained
                    comparisons={}
                    for name in data.schedule.sources:
                        current=[d['mean_ce'] for d in result['documents'] if d['source']==name]
                        require(len(current)>=2,'at least two fixed documents/source required for paired regression')
                        comparison=compare_losses(current,best[name]) if name in best else None
                        bad[name]=bad.get(name,0)+1 if comparison and comparison['materially_worse'] else 0
                        if name not in best or sum(current)/len(current)<sum(best[name])/len(best[name]):best[name]=current
                        comparisons[name]=comparison
                    result['comparisons']=comparisons;history.append(result);save()
                external_milestone(spec,run,campaign,trained)
                if any(n>=2 for n in bad.values()):
                    confirmation=evaluate(model,data,campaign,check,device)
                    regression=[name for name in bad if bad[name]>=2 and compare_losses([d['mean_ce'] for d in confirmation['documents'] if d['source']==name],best[name])['materially_worse']]
                    history.append(dict(trained_tokens=trained,confirmation=confirmation,regression=regression));save()
                    if regression:campaign.finish('diverged','confirmed consecutive source regression');break
                    bad={name:0 for name in bad};save()
                if trained==spec['training_goal']:
                    save();checkpoint.protect(run);campaign.finish('completed','finite language continuation; assistant capability unestablished');break
                if campaign.snapshot()['remaining_tokens']<8192:
                    save();campaign.finish('budget-exhausted','attempted ceiling before committed goal');break
                if campaign.snapshot()['remaining_lease_seconds']<spec['checkpoint_margin_seconds']:raise CampaignStop('paused-lease','checkpoint lease margin')
                if time.monotonic()-last_save>=spec['checkpoint_seconds']:save()
                rows,next_cursor=data.schedule.next_update(cursor);campaign.reserve(8192);model.train();opt.zero_grad(set_to_none=True);loss_sum=0.
                for group in opt.param_groups:group['lr']=spec['scheduler']['lr']
                for start in range(0,len(rows),spec['microbatch']):
                    check();batch=torch.stack([torch.from_numpy(data.row(r)) for r in rows[start:start+spec['microbatch']]]).to(device)
                    with precision(spec['bf16'] and device=='mps'):
                        loss=F.cross_entropy(model(batch[:,:-1]).flatten(0,1),batch[:,1:].flatten(),reduction='sum')/8192
                    require(bool(torch.isfinite(loss)),'nonfinite train loss');loss.backward();loss_sum+=float(loss.detach())
                norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True);opt.step()
                if device=='mps':torch.mps.synchronize()
                cursor=next_cursor;campaign.commit(cursor['updates'],cursor['updates']*8192)
                checkpoint._atomic_json(run/'status.json',dict(campaign.snapshot(),cursor=cursor,train_ce=loss_sum,gradient_norm=float(norm),optimizer_step=initial_step+cursor['updates']))
                if after_update:after_update(cursor['updates'],campaign)
        except (CampaignStop,KeyboardInterrupt) as error:
            # Pending attempts are retained; a partially updated model is never saved.
            if not campaign.pending and not (isinstance(error,CampaignStop) and error.state=='paused-milestone'):save()
            campaign.finish(error.state if isinstance(error,CampaignStop) else 'interrupted',str(error))
        except BaseException as error:
            campaign.finish('failed',str(error));raise
        return campaign.ledger['state']


def train(spec_path,run,*,resume=False):
    spec=pinned(spec_path);validate_launch(spec,run);check_external(spec,Path(run))
    if 'language_parent' in spec:
        from own_base_language_parent import verified_language_parent
        data=AdmittedStreams(spec,check=lambda:check_external(spec,Path(run)))
        parent=verified_language_parent(spec,data,lambda:check_external(spec,Path(run)))
        spec['_resume']=resume;return run_training(spec,run,data,parent)
    from own_base_sft_train import verified_parent
    parent,name,receipt=verified_parent(spec)
    require(name=='preserve-095','frozen selected own parent required')
    require(spec['initialization']==dict(mode='own_pretraining',path=str(Path(receipt['run'])/receipt['checkpoint']['file']),sha256=receipt['checkpoint']['sha256'],random_lineage_root=parent['identity']['initialization']['random_lineage_root']),'parent lineage spec differs')
    data=AdmittedStreams(spec,check=lambda:check_external(spec,Path(run)))
    spec['_resume']=resume;return run_training(spec,run,data,parent)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('spec');p.add_argument('run');p.add_argument('--expected-spec-sha256',required=True);p.add_argument('--resume',action='store_true');p.add_argument('--ticket-fd',type=int,required=True);a=p.parse_args()
    import own_base_dev_run as runtime
    _TICKET=runtime.consume_ticket(a.ticket_fd)
    require(_TICKET['spec_sha256']==a.expected_spec_sha256,'owned watchdog spec identity')
    print(train(dict(path=str(Path(a.spec).resolve()),sha256=a.expected_spec_sha256),a.run,resume=a.resume))
