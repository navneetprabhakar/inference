"""Prospective standalone masked-SFT lease entrypoint; no implicit launch budget.

Production execution requires a reviewed, hash-pinned specification, admitted
streams, independent verification, hardware preflight and completed selected own
optimizer endpoint. No current queue or frozen runtime is modified here.
"""
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import json
import math
from pathlib import Path
import random
import resource
import sys
import time
import numpy as np
import torch
from torch.nn import functional as F
import checkpoint
from base_run_control import CampaignStop
from base_train import precision
from gpt2 import Config,GPT2
from own_base_sft_control import SFTCampaign,WORK,valid_work
from optimizer_ablation_report import analyze,read_run,BRANCHES,TARGET,canonical,digest
from optimizer_ablation_train import parent_lock,validate_optimizer,BRANCHES as BETAS
from tokenizer import ASSETS
from train import optimizer_for
ROOT=Path(__file__).resolve().parent
RUNTIME=('own_base_sft_train.py','own_base_sft_control.py','base_run_control.py','base_train.py','checkpoint.py','guards.py','gpt2.py','train.py','tokenizer.py','optimizer_ablation_report.py','optimizer_ablation_train.py','pretrained_base.py','pretrain.py')


def stop_check(spec,run=None):
    paths=[ROOT/'runs/STOP']+[Path(p) for p in spec.get('stop_paths',[])]
    if run is not None:paths.append(Path(run)/'STOP')
    if any(p.exists() for p in paths):raise CampaignStop('interrupted','explicit STOP')
    if 'cpu_rss_limit_bytes' in spec:
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>spec['cpu_rss_limit_bytes']:raise CampaignStop('paused-resource','explicit CPU RSS ceiling')


def pinned_json(pin):
    p=Path(pin['path'])
    if not p.is_absolute() or p.is_symlink() or digest(p)!=pin['sha256']:raise ValueError('artifact identity mismatch')
    return json.loads(p.read_text())


def validate_run_path(spec,run):
    """All production workers must share ROOT/runs/mps.lock through Guard."""
    path=Path(run);directory=ROOT/'runs'
    if not path.is_absolute() or path!=path.resolve() or directory!=directory.resolve():
        raise ValueError('run path must be canonical and absolute')
    if path.parent!=directory or path.name in ('','.','..'):
        raise ValueError('run must be a direct canonical ROOT/runs child')
    if any(part.is_symlink() for part in (path,*path.parents)):
        raise ValueError('symlink run paths or parents are forbidden')
    if spec.get('run')!=str(path):
        raise ValueError('immutable specification must bind the exact run path')
    return path


def validate_launch(spec,run):
    validate_run_path(spec,run)
    stop_check(spec,run)
    if spec.get('state')!='reviewed_for_diagnostic_execution' or spec.get('schema')!=1:raise ValueError('reviewed launch specification required')
    if spec.get('optimizer_initialization')!='fresh_selected_beta2':raise ValueError('fresh optimizer initialization must be explicit')
    if spec.get('context')!=1024 or spec.get('model')!=asdict(Config()) or spec.get('tokenizer')!=ASSETS:raise ValueError('production model/tokenizer/context mismatch')
    if not set(RUNTIME)<=spec['code_sha256'].keys():raise ValueError('missing runtime pins')
    for name,expected in spec['code_sha256'].items():
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or digest(path)!=expected:raise ValueError('runtime changed')
    for key in ('microbatch','evaluation_microbatch','accumulation','checkpoint_updates','validation_updates','schedule_rows_limit'):
        if type(spec[key])!=int or spec[key]<=0:raise ValueError('explicit positive schedule/batch parameters required')
    valid_work(spec['work_limits'])
    if any(n<=0 for n in spec['work_limits'].values()):raise ValueError('every work ceiling required')
    for key in ('active_seconds','calendar_seconds','lease_seconds','checkpoint_margin_seconds','checkpoint_bytes','disk_headroom_bytes','cpu_rss_limit_bytes'):
        if not isinstance(spec[key],(int,float)) or not math.isfinite(spec[key]) or spec[key]<=0:raise ValueError('explicit finite execution/disk limits required')
    s=spec['scheduler']
    if s['kind']!='warmup_cosine_updates' or type(s['warmup_updates'])!=int or s['warmup_updates']<0 or not 0<s['end_fraction']<=1 or not 0<s['peak_lr']<1:raise ValueError('invalid explicit LR schedule')
    if spec.get('mixing')!='proportional_source_update_midpoints' or not spec.get('datasets'):
        raise ValueError('explicit source schedule required')
    names=set()
    for source in spec['datasets']:
        if source['name'] in names or type(source['passes'])!=int or source['passes']<=0 or type(source['validation_rows'])!=int or source['validation_rows']<=0:
            raise ValueError('unique sources and explicit positive passes/evaluation rows required')
        if source['development_split'] not in ('validation','exposed-development'):raise ValueError('explicit development split required')
        names.add(source['name'])
        valid_work(source['work_limits'])
        if any(v<=0 for v in source['work_limits'].values()):raise ValueError('positive per-source work ceilings required')
        admission=pinned_json(source['admission']);verification=pinned_json(source['verification'])
        if admission.get('training_admitted') is not True or admission.get('dataset_sha256')!=source['receipt']['sha256']:
            raise ValueError('source dataset not admitted')
        if verification.get('state')!='PASS' or verification.get('dataset_sha256')!=source['receipt']['sha256']:
            raise ValueError('independent source verification required')
    hardware=pinned_json(spec['hardware_preflight'])
    expected={k:spec[k] for k in ('context','microbatch','evaluation_microbatch','accumulation','bf16')}
    expected['evaluation_precision']='fp32'
    if hardware.get('state')!='PASS' or hardware.get('configuration')!=expected or hardware.get('validation_exercised') is not True or hardware.get('runtime_sha256')!=spec['code_sha256']:
        raise ValueError('matching hardware preflight required')


def validate_parent_payload(payload,frozen,entry,ledger,config,check=lambda:None):
    if (payload['identity']!=frozen['identity'] or payload['campaign_id']!=ledger['campaign_id'] or
        payload['spec_sha256']!=__import__('hashlib').sha256(canonical(frozen)).hexdigest() or payload['trained_tokens']!=TARGET):raise ValueError('selected payload ancestry mismatch')
    protocol=frozen['identity']['protocol'];step=payload['initial_optimizer_step']+payload['step']
    expected_initial=frozen['identity']['parent_receipt']['step'] if protocol['branch']=='preserve-095' else 0
    if payload['initial_optimizer_step']!=expected_initial:raise ValueError('selected optimizer ancestry step mismatch')
    if payload['step']!=TARGET//8192 or payload['offset']!=protocol['source_offset']+TARGET:raise ValueError('selected endpoint cursor mismatch')
    with torch.device('meta'):shape_model=GPT2(config)
    if sum(p.numel() for p in shape_model.parameters())>200_000_000:raise ValueError('own model exceeds parameter cap')
    expected=shape_model.state_dict()
    if expected.keys()!=payload['model'].keys():raise ValueError('parent tensor inventory mismatch')
    for name,tensor in payload['model'].items():
        check()
        if tensor.shape!=expected[name].shape or tensor.dtype!=torch.float32 or not bool(torch.isfinite(tensor).all()):raise ValueError('parent tensor invalid')
    groups=[[p for p in shape_model.parameters() if p.ndim>=2],[p for p in shape_model.parameters() if p.ndim<2]]
    opt=payload['optimizer'];ids=[]
    if len(opt['param_groups'])!=2:raise ValueError('parent optimizer groups')
    for index,(actual,params) in enumerate(zip(opt['param_groups'],groups)):
        if tuple(actual['betas'])!=(.9,BETAS[protocol['branch']]) or actual['eps']!=1e-8 or actual['weight_decay']!=(.1 if index==0 else 0.) or len(actual['params'])!=len(params):raise ValueError('parent optimizer hyperparameters')
        for pid,param in zip(actual['params'],params):
            check()
            ids.append(pid);state=opt['state'][pid]
            if set(state)!={'step','exp_avg','exp_avg_sq'} or float(state['step'])!=step:raise ValueError('parent optimizer step/inventory')
            for key in ('exp_avg','exp_avg_sq'):
                value=state[key]
                if value.shape!=param.shape or value.dtype!=torch.float32 or not bool(torch.isfinite(value).all()):raise ValueError('parent moment invalid')
            if bool((state['exp_avg_sq']<0).any()):raise ValueError('negative parent moment')
    if len(set(ids))!=len(ids) or set(ids)!=set(opt['state']):raise ValueError('parent optimizer parameter identity')


def verified_parent(spec):
    """Future execution only: never called by CPU preparation against real runs."""
    stop_check(spec);report=pinned_json(spec['optimizer_report']);experiment=pinned_json(spec['optimizer_experiment'])
    if report.get('state')!='screen-completed' or report.get('report_code_sha256')!=digest(ROOT/'optimizer_ablation_report.py'):raise ValueError('completed pinned optimizer report required')
    if report['common']['parent']['run']!=experiment['parent']['run'] or report['common']['source_offset']!=experiment['parent']['required_trained_tokens']:
        raise ValueError('report foundation ancestry differs from pinned experiment')
    arm_paths={x['name']:str(Path(x['run']).resolve()) for x in experiment['arms']}
    if set(arm_paths)!=set(BRANCHES):raise ValueError('three parent arms required')
    histories={};receipts={};common=None
    with ExitStack() as locks:
        for name in BRANCHES:stop_check(spec);locks.enter_context(parent_lock(Path(arm_paths[name])))
        for name in BRANCHES:
            stop_check(spec);arm,history,receipt=read_run(arm_paths[name])
            if arm['branch']!=name or receipt!=report['receipts'][name]:raise ValueError('report endpoint receipt changed')
            if any(arm[key]!=value for key,value in report['common'].items()):raise ValueError('comparison common identity mismatch')
            histories[name]=history;receipts[name]=receipt
        recomputed=analyze(histories)
        if any(report.get(key)!=value for key,value in recomputed.items()):raise ValueError('optimizer selection/report changed')
        name=recomputed['selected_optimizer_recipe'];receipt=receipts[name]
        if spec['parent']!=receipt:raise ValueError('must use exact selected endpoint')
        run=Path(receipt['run']);entry=receipt['checkpoint'];stop_check(spec)
        payload=torch.load(run/entry['file'],map_location='cpu',weights_only=True,mmap=True)
        frozen=json.loads((run/'campaign-spec.json').read_text());ledger=json.loads((run/'campaign.json').read_text())
        validate_parent_payload(payload,frozen,entry,ledger,Config(),lambda:stop_check(spec))
        identity=payload['identity'];origin=identity['initialization']
        if origin.get('mode')!='own_pretraining' or not origin.get('random_lineage_root') or origin['random_lineage_root']!=identity['parent_receipt']['random_lineage_root']:
            raise ValueError('selected own random-initialization lineage mismatch')
    return payload,name,receipt


class Streams:
    """Pinned storage streams, not concatenated training examples."""
    def __init__(self,pin,*,development_split='validation',vocabulary=50257,context=1024,check=lambda:None):
        check();receipt=pinned_json(pin);root=Path(pin['path']).parent;self.rows={};self.arrays={}
        if development_split not in ('validation','exposed-development'):raise ValueError('unsupported development split')
        for split in ('train','validation'):
            physical='train' if split=='train' else development_split
            paths=[root/f'{physical}.{suffix}' for suffix in ('inputs.u16','labels.u16','index.jsonl')]
            for path in paths:
                check();expected=receipt['outputs'][path.name]
                if path.is_symlink() or path.stat().st_size!=expected['bytes'] or digest(path)!=expected['sha256']:raise ValueError('aligned stream changed')
            if any(p.stat().st_size%2 for p in paths[:2]):raise ValueError('unaligned uint16 stream')
            x,y=[np.memmap(p,mode='r',dtype='<u2') for p in paths[:2]]
            if len(x)!=len(y):raise ValueError('input/label stream mismatch')
            rows=[];offset=0
            with paths[2].open() as stream:
                for line in stream:
                    if len(rows)%256==0:check()
                    row=json.loads(line);n=row['length']
                    if row['offset']!=offset or row['split']!=physical or not 0<n<=context or offset+n>len(x):raise ValueError('row bounds/order/context mismatch')
                    a,b=x[offset:offset+n],y[offset:offset+n];mask=b!=65535
                    if bool((a>=vocabulary).any()) or bool((b[mask]>=vocabulary).any()) or int(mask.sum())!=row['target_count'] or not row['target_count']:raise ValueError('invalid tokens/mask/target count')
                    if n==context and mask[-1]:raise ValueError('supervised predicted position outside context')
                    rows.append(row);offset+=n
            if offset!=len(x) or not rows:raise ValueError('missing/empty indexed stream')
            self.rows[split]=rows;self.arrays[split]=(x,y)
        train={r['family'] for r in self.rows['train']};val={r['family'] for r in self.rows['validation']}
        if train&val:raise ValueError('train/validation family overlap')

    def row(self,split,index):
        r=self.rows[split][index];a,b=self.arrays[split];sl=slice(r['offset'],r['offset']+r['length'])
        x=np.array(a[sl],dtype=np.int64);y=np.array(b[sl],dtype=np.int64);y[y==65535]=-100
        return x,y


class Sources:
    def __init__(self,sources,check=lambda:None):
        self.parts={source['name']:Streams(source['receipt'],development_split=source['development_split'],check=check) for source in sources}
        self.rows={'train':[],'validation':[]}
        for name,part in self.parts.items():
            for split in self.rows:
                self.rows[split].extend(dict(row,_source=name,_index=i) for i,row in enumerate(part.rows[split]))
        train={r['doc_id'] for r in self.rows['train']};val={r['doc_id'] for r in self.rows['validation']}
        if train&val:raise ValueError('cross-source document split overlap')
    def row(self,split,index):
        row=self.rows[split][index]
        return self.parts[row['_source']].row(split,row['_index'])


def updates(data,spec):
    if spec['mixing']!='proportional_source_update_midpoints':raise ValueError('explicit source mixing required')
    scheduled_rows=sum(sum(r['_source']==source['name'] for r in data.rows['train'])*source['passes'] for source in spec['datasets'])
    if scheduled_rows>spec['schedule_rows_limit']:raise ValueError('explicit schedule memory/row limit exceeded')
    queues=[];size=spec['microbatch']*spec['accumulation']
    for source_index,source in enumerate(spec['datasets']):
        queue=[];eligible=[i for i,r in enumerate(data.rows['train']) if r['_source']==source['name']]
        if not eligible:raise ValueError('empty training source')
        for epoch in range(source['passes']):
            order=list(eligible);random.Random(spec['seed']+source_index*1000003+epoch).shuffle(order)
            queue.extend([order[i:i+size] for i in range(0,len(order),size)])
        queues.append(queue)
    # Merge by exact rational normalized-progress midpoint; keep each source's
    # order and count, spreading short queues through the entire run.
    from fractions import Fraction
    merged=[(Fraction(2*i+1,2*len(queue)),source_index,batch) for source_index,queue in enumerate(queues) for i,batch in enumerate(queue)]
    merged.sort(key=lambda item:(item[0],item[1]))
    return [batch for _,_,batch in merged]


def work_for(data,indices,microbatch,split='train'):
    work={k:0 for k in WORK}
    for i in range(0,len(indices),microbatch):
        rows=[data.rows[split][j] for j in indices[i:i+microbatch]];length=max(r['length'] for r in rows)
        work['input_tokens']+=sum(r['length'] for r in rows);work['padded_tokens']+=len(rows)*length;work['attention_cells']+=len(rows)*length*length
        work['assistant_targets' if split=='train' else 'evaluation_targets']+=sum(r['target_count'] for r in rows)
    return work


def padded(data,indices,split,device):
    rows=[data.row(split,j) for j in indices];length=max(len(x) for x,y in rows)
    x=np.zeros((len(rows),length),dtype=np.int64);y=np.full_like(x,-100)
    for i,(a,b) in enumerate(rows):x[i,:len(a)]=a;y[i,:len(b)]=b
    return torch.from_numpy(x).to(device),torch.from_numpy(y).to(device)


def learning_rate(step,total,schedule):
    warm=schedule['warmup_updates'];peak=schedule['peak_lr']
    if warm and step<warm:return peak*(step+1)/warm
    fraction=min(1,max(0,(step-warm)/max(1,total-warm-1)))
    return peak*(schedule['end_fraction']+(1-schedule['end_fraction'])*(1+math.cos(math.pi*fraction))/2)


def update(model,opt,data,indices,spec,step,total,check,device):
    work=work_for(data,indices,spec['microbatch']);opt.zero_grad(set_to_none=True);model.train();loss=0.
    for group in opt.param_groups:group['lr']=learning_rate(step,total,spec['scheduler'])
    for i in range(0,len(indices),spec['microbatch']):
        check();x,y=padded(data,indices[i:i+spec['microbatch']],'train',device);mask=y!=-100
        with precision(spec['bf16'] and device=='mps'):
            value=F.cross_entropy(model(x,prediction_mask=mask),y[mask],reduction='sum')/work['assistant_targets']
        if not bool(torch.isfinite(value)):raise ValueError('nonfinite masked SFT loss')
        value.backward();loss+=float(value.detach())
    norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True);opt.step()
    if device=='mps':torch.mps.synchronize()
    return dict(masked_ce=loss,gradient_norm=float(norm),lr=opt.param_groups[0]['lr'])


@torch.inference_mode()
def evaluate(model,data,spec,campaign,device):
    reports={};model.eval()
    for source in spec['datasets']:
        eligible=[i for i,r in enumerate(data.rows['validation']) if r['_source']==source['name']]
        indices=eligible[:source['validation_rows']];total_loss=0.;targets=0
        if not indices:raise ValueError('empty validation source')
        for i in range(0,len(indices),spec['evaluation_microbatch']):
            stop_check(spec,campaign.path)
            batch=indices[i:i+spec['evaluation_microbatch']];work=work_for(data,batch,spec['evaluation_microbatch'],'validation');campaign.reserve_evaluation(work,source['name'])
            x,y=padded(data,batch,'validation',device);mask=y!=-100
            value=F.cross_entropy(model(x,prediction_mask=mask),y[mask],reduction='sum')
            if not bool(torch.isfinite(value)):raise ValueError('nonfinite validation')
            total_loss+=float(value);targets+=work['evaluation_targets']
        reports[source['name']]=dict(masked_ce=total_loss/targets,targets=targets,rows=len(indices),physical_split=source['development_split'],precision='fp32')
    return dict(sources=reports,scope='Teacher-forced source-specific development CE, not conversation/tool capability')


def train(spec_path,run_path,*,resume=False):
    """Production-only entrypoint; tiny tests exercise helpers with small models."""
    os.nice(10);torch.set_num_threads(1);spec=json.loads(Path(spec_path).read_text());run=Path(run_path);validate_launch(spec,run)
    parent,branch,receipt=verified_parent(spec);data=Sources(spec['datasets'],check=lambda:stop_check(spec,run));plan=updates(data,spec)
    evaluation_count=len({0,len(plan)}|set(range(spec['validation_updates'],len(plan),spec['validation_updates'])))
    nominal={k:0 for k in WORK}
    for source in spec['datasets']:
        training=[b for b in plan if data.rows['train'][b[0]]['_source']==source['name']]
        evaluation=[i for i,row in enumerate(data.rows['validation']) if row['_source']==source['name']][:source['validation_rows']]
        cost={k:sum(work_for(data,b,spec['microbatch'])[k] for b in training) for k in WORK}
        eval_cost=work_for(data,evaluation,spec['evaluation_microbatch'],'validation')
        for k in WORK:cost[k]+=evaluation_count*eval_cost[k];nominal[k]+=cost[k]
        if any(cost[k]>source['work_limits'][k] for k in WORK):raise ValueError('nominal source schedule/evaluation exceeds explicit ceiling')
    if any(nominal[k]>spec['work_limits'][k] for k in WORK):raise ValueError('nominal schedule/evaluation exceeds global ceiling')
    if spec['scheduler']['warmup_updates']>len(plan):raise ValueError('warmup exceeds whole planned schedule')
    identity=dict(seed=spec['seed'],model=spec['model'],tokenizer=ASSETS,initialization=deepcopy(parent['identity']['initialization']),corpus=spec['datasets'],scheduler=spec['scheduler'],work_limits=spec['work_limits'],source_work_limits={s['name']:s['work_limits'] for s in spec['datasets']},protocol=spec,parent=receipt,optimizer_initialization='fresh_selected_beta2',beta2=BETAS[branch],torch_version=str(torch.__version__))
    identity['initialization'].update(path=str(Path(receipt['run'])/receipt['checkpoint']['file']),sha256=receipt['checkpoint']['sha256'])
    with SFTCampaign(run,identity,limits=spec['work_limits'],active_seconds=spec['active_seconds'],calendar_seconds=spec['calendar_seconds'],lease_seconds=spec['lease_seconds'],resume=resume) as campaign:
        import shutil
        if shutil.disk_usage(run).free<20*1024**3+3*spec['checkpoint_bytes']+spec['disk_headroom_bytes']:raise CampaignStop('paused-resource','checkpoint forecast does not fit')
        torch.manual_seed(spec['seed']);model=GPT2().to('mps');opt=optimizer_for(model)
        for group in opt.param_groups:group['betas']=(.9,BETAS[branch])
        cursor=0;history=[];position_exposure=[0,0,0,0]
        if resume:
            saved=campaign.load();model.load_state_dict(saved['model'],strict=True);opt.load_state_dict(saved['optimizer']);cursor=saved['cursor']
            validate_optimizer(opt,cursor,BETAS[branch])
            history=saved['history'];position_exposure=saved['position_exposure']
            if cursor!=saved['step'] or not 0<=cursor<=len(plan):raise ValueError('resume schedule cursor mismatch')
            expected={k:sum(work_for(data,b,spec['microbatch'])[k] for b in plan[:cursor]) for k in WORK}
            if expected!=saved['committed_work']:raise ValueError('resume data/compute cursor mismatch')
            if len(position_exposure)!=4 or any(type(n)!=int or n<0 for n in position_exposure) or sum(position_exposure)!=saved['trained_tokens']:raise ValueError('position exposure/target mismatch')
            torch.set_rng_state(saved['cpu_rng']);torch.mps.set_rng_state(saved['mps_rng'])
        else:
            model.load_state_dict(parent['model'],strict=True)
            validate_optimizer(opt,0,BETAS[branch])
        del parent
        def checked():
            stop_check(spec,run);campaign.check()
        def save(protect=False):
            if sum(position_exposure)!=campaign.ledger['trained_tokens']:raise ValueError('position exposure accounting mismatch')
            stop_check(spec,run)
            if shutil.disk_usage(run).free<20*1024**3+spec['checkpoint_bytes']+spec['disk_headroom_bytes']:raise CampaignStop('paused-resource','save disk reserve')
            campaign.save(dict(step=cursor,cursor=cursor,model=model.state_dict(),optimizer=opt.state_dict(),cpu_rng=torch.get_rng_state(),mps_rng=torch.mps.get_rng_state(),history=history,position_exposure=position_exposure))
            if protect:checkpoint.protect(run)
        if not resume:save()
        try:
            while True:
                stop_check(spec,run);campaign.check()
                if (cursor==0 or cursor==len(plan) or cursor%spec['validation_updates']==0) and not any(h['step']==cursor for h in history):
                    history.append(dict(step=cursor,**evaluate(model,data,spec,campaign,'mps')));save()
                if cursor==len(plan):save(True);campaign.finish('completed','bounded SFT diagnostic complete; usability not established');break
                if campaign.snapshot()['remaining_lease_seconds']<=spec['checkpoint_margin_seconds']:save();raise CampaignStop('paused-lease','checkpoint margin')
                batch=plan[cursor];work=work_for(data,batch,spec['microbatch']);campaign.reserve_work(work,data.rows['train'][batch[0]]['_source'])
                metric=update(model,opt,data,batch,spec,cursor,len(plan),checked,'mps')
                for index in batch:
                    _,labels=data.row('train',index)
                    for pos in np.flatnonzero(labels!=-100):position_exposure[min(3,(int(pos)+1)//256)]+=1
                cursor+=1;campaign.commit_work(cursor)
                with (run/'metrics.jsonl').open('a') as stream:stream.write(json.dumps(dict(step=cursor,source=data.rows['train'][batch[0]]['_source'],**metric,work=work))+'\n')
                if cursor%spec['checkpoint_updates']==0:save()
        except (CampaignStop,KeyboardInterrupt) as error:
            # Never save partially updated weights or advance a checkpoint cursor.
            # Existing checkpoint is authoritative; all attempted costs stay charged.
            campaign.finish(error.state if isinstance(error,CampaignStop) else 'interrupted',str(error))

    return campaign.snapshot()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('spec',type=Path);parser.add_argument('run',type=Path);parser.add_argument('--resume',action='store_true');parser.add_argument('--execute-reviewed',action='store_true');args=parser.parse_args()
    if not args.execute_reviewed:parser.error('candidate-only entrypoint: explicit --execute-reviewed and complete reviewed evidence required')
    result=train(args.spec,args.run,resume=args.resume)
    print(json.dumps(result))
    raise SystemExit(0 if result['state']=='completed' else 75)
