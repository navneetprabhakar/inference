"""Finite CUDA benchmark/learning diagnostics. Never a production promotion path."""
import argparse
import gc
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np
import torch
import torch.nn.functional as F

from gpt2 import GPT2,Config
from tokenizer import load,EOT
from cloud_training.runtime import Guard,atomic_json,optimizer,precision,restore,save,sha,synchronize,update

ROOT=Path(__file__).resolve().parents[1]


def verify_inputs(root):
    manifest=json.loads((root/'inputs.json').read_text())
    for name,expected in manifest['files'].items():
        path=root/name
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():raise ValueError('unsafe input')
        if path.stat().st_size!=expected['bytes'] or sha(path)!=expected['sha256']:raise ValueError('input hash mismatch: '+name)
    return manifest


def backup(path,bucket,*,restore_check=False):
    """No credentials in files. VM identity has access only to its dedicated bucket."""
    remote=bucket.rstrip('/')+'/'+path.name
    subprocess.run(['gcloud','storage','cp',str(path),remote,'--quiet'],check=True,timeout=180)
    if restore_check:
        temp=path.with_suffix(path.suffix+'.gcs-restore')
        subprocess.run(['gcloud','storage','cp',remote,str(temp),'--quiet'],check=True,timeout=180)
        try:
            if sha(temp)!=sha(path):raise ValueError('GCS restore checksum mismatch')
        finally:temp.unlink(missing_ok=True)
    return remote


def new_model(parent,device):
    model=GPT2().to(device);opt=optimizer(model)
    restore(model,opt,parent,device)
    return model,opt


@torch.inference_mode()
def validation(model,rows,device,guard):
    model.eval();values=[]
    for row in rows:
        guard.check();x=torch.tensor([row],device=device)
        with precision(device,True):
            loss=F.cross_entropy(model(x[:,:-1]).flatten(0,1),x[:,1:].flatten())
        values.append(float(loss))
    return {'mean_document_ce':float(np.mean(values)),'document_losses':values}


def synthetic(tok):
    """Diagnostic-only examples: separate entities and wording, balanced bindings."""
    values=[' amber',' violet']
    def case(i,split):
        a=f'unit {i//2+1000 if split=="train" else i//2+7000}'
        b=f'unit {i//2+3000 if split=="train" else i//2+9000}'
        binding=i%2;target_index=(i//2)%2;correct=binding^target_index
        target=(a,b)[target_index]
        if split=='template':
            prefix=f'Registry entry: {a} carries the{values[binding]} marker; {b} carries the{values[1-binding]} marker. Report the marker assigned to {target}:'
        else:
            prefix=f'The tag on {a} is{values[binding]}. The tag on {b} is{values[1-binding]}. The tag on {target} is'
        answer=values[correct]+'.'
        p=tok.encode(prefix).ids;ans=tok.encode(answer).ids+[EOT]
        assert tok.encode(prefix+answer).ids==p+ans[:-1]
        ids=p+ans;assert len(ids)<=96
        row=ids+[EOT]*(96-len(ids));labels=[-100]*95
        labels[len(p)-1:len(ids)-1]=ans
        return {'prefix':prefix,'answer':answer,'row':row,'labels':labels,'correct':correct,'target':target,'pair_id':i//2,'choices':[v+'.' for v in values]}
    return {s:[case(i,s) for i in range(128)] for s in ('train','entities','template')}


@torch.inference_mode()
def binding_scores(model,cases,tok,guard,device):
    model.eval();scores=[];correct=0;exact=0
    for case in cases:
        guard.check();p=tok.encode(case['prefix']).ids;choices=[]
        for answer in case['choices']:
            ids=tok.encode(answer).ids
            with precision(device,True):
                logits=model(torch.tensor([p+ids[:-1]],device=device))[0,len(p)-1:]
                loss=F.cross_entropy(logits.float(),torch.tensor(ids,device=device))
            choices.append(-float(loss))
        chosen=int(np.argmax(choices));correct+=chosen==case['correct']
        ids=list(p);generated=[];expected=tok.encode(case['answer']).ids+[EOT]
        for _ in range(len(expected)+2):
            guard.check()
            with precision(device,True):token=int(model(torch.tensor([ids],device=device))[0,-1].argmax())
            generated.append(token)
            if token==EOT:break
            ids.append(token)
        exact+=generated==expected
        scores.append({'correct':chosen==case['correct'],'scores':choices,'generated':tok.decode(generated),'expected':case['answer']})
    return {'choice_correct':correct,'both_members_correct':sum(scores[i]['correct'] and scores[i+1]['correct'] for i in range(0,len(scores),2)),'pairs':len(scores)//2,'exact_with_eot':exact,'n':len(cases),'rows':scores}


@torch.inference_mode()
def public_scores(model, definition, tok, guard):
    model.eval();pairs=[];completions=[]
    for pair in definition['pairs']:
        members=[]
        for m in pair['members']:
            guard.check();prefix=tok.encode(m['prefix']).ids;values=[]
            for text in pair['choices']:
                target=tok.encode(text).ids
                with precision('cuda',True):
                    logits=model(torch.tensor([prefix+target[:-1]],device='cuda'))[0,len(prefix)-1:]
                    ce=F.cross_entropy(logits.float(),torch.tensor(target,device='cuda'))
                values.append(-float(ce))
            members.append({'scores':values,'correct':int(np.argmax(values))==m['correct']})
        pairs.append({'id':pair['id'],'correct':all(m['correct'] for m in members),'members':members})
    for prefix in definition['prefixes']:
        prefix=prefix['text'] if isinstance(prefix,dict) else prefix
        ids=tok.encode(prefix).ids;generated=[]
        for _ in range(48):
            guard.check()
            with precision('cuda',True):token=int(model(torch.tensor([ids],device='cuda'))[0,-1].argmax())
            if token==EOT:break
            ids.append(token);generated.append(token)
        completions.append({'prefix':prefix,'generated':tok.decode(generated)})
    return {'pairs_correct':sum(p['correct'] for p in pairs),'pairs':pairs,'completions':completions}


def run(args):
    if not torch.cuda.is_available() or torch.cuda.device_count()!=1:raise ValueError('exactly one CUDA GPU required')
    if 'A100' not in torch.cuda.get_device_name():raise ValueError('approved A100 required')
    torch.set_num_threads(8)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    torch.manual_seed(20261110);torch.cuda.manual_seed_all(20261110)
    if args.lr not in (6e-5,1.2e-4,2.4e-4) or args.microbatch not in (2,4,8,16):raise ValueError('unreviewed diagnostic configuration')
    if not args.backup.startswith('gs://'):raise ValueError('GCS backup required')
    out=Path(args.output)
    if out.exists() and any(out.iterdir()) and not args.resume:raise ValueError('existing run; inspect or explicitly resume')
    out.mkdir(parents=True,exist_ok=True)
    guard=Guard(out,args.seconds);guard.install_signals();guard.check()
    inputs=Path(args.inputs);manifest=verify_inputs(inputs)
    parent=torch.load(inputs/'parent.pt',map_location='cpu',weights_only=True,mmap=True)
    if parent['identity']['initialization']['mode']!='own_pretraining':raise ValueError('own weights required')
    rows=np.load(inputs/'train.npy',mmap_mode='r');tok=load(inputs/'data/tokenizer')
    held=json.loads((inputs/'validation.json').read_text())[:64]
    identity={'parent_sha256':manifest['files']['parent.pt']['sha256'],'input_manifest_sha256':sha(inputs/'inputs.json'),
              'torch':str(torch.__version__),'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(),'mode':args.mode,'lr':args.lr,'microbatch':args.microbatch,'code_sha256':sha(Path(__file__)),'runtime_sha256':sha(ROOT/'cloud_training/runtime.py')}
    atomic_json(out/'identity.json',identity)
    backup(out/'identity.json',args.backup)
    if args.resume and args.mode not in ('memorize','lr'):raise ValueError('only learning stages resume')
    def checkpoint_resume(model,opt):
        if not args.resume:return 0
        path=Path(args.resume);receipt=json.loads(path.with_suffix('.json').read_text())
        if sha(path)!=receipt['sha256'] or receipt['identity']!=identity:raise ValueError('resume identity or hash mismatch')
        payload=torch.load(path,map_location='cpu',weights_only=True)
        if payload['identity']!=identity or payload['cursor']!=receipt['cursor']:raise ValueError('resume cursor mismatch')
        restore(model,opt,payload,'cuda');return payload['cursor']
    def publish_checkpoint(cp,model,opt,cursor):
        save(cp,model,opt,cursor=cursor,identity=identity)
        backup(cp,args.backup);backup(cp.with_suffix('.json'),args.backup)
    if args.mode=='preflight':
        model,opt=new_model(parent,'cuda')
        batch=np.array(rows[:2,:65],dtype=np.int64)
        # Compare actual checkpoint CPU/CUDA FP32 before any diagnostic update.
        model.eval()
        with torch.inference_mode():gpu=model(torch.tensor(batch[:,:-1],device='cuda')).float().cpu()
        cpu=GPT2();cpu.load_state_dict(parent['model']);cpu.eval()
        with torch.inference_mode():reference=cpu(torch.tensor(batch[:,:-1]))
        torch.testing.assert_close(gpu,reference,rtol=2e-3,atol=2e-3)
        fp32_max=float((gpu-reference).abs().max());del cpu,reference,gpu;gc.collect()
        # Save then reload through GCS; compare next update with uninterrupted path.
        first=update(model,opt,batch,device='cuda',microbatch=2,lr=6e-5,guard=guard,bf16=True)
        cp=out/'restart-proof.pt';save(cp,model,opt,cursor=1,identity=identity)
        backup(cp,args.backup,restore_check=True)
        second=update(model,opt,batch,device='cuda',microbatch=2,lr=6e-5,guard=guard,bf16=True)
        expected={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        payload=torch.load(cp,map_location='cpu',weights_only=True)
        restore(model,opt,payload,'cuda');del payload
        resumed=update(model,opt,batch,device='cuda',microbatch=2,lr=6e-5,guard=guard,bf16=True)
        maxdiff=0.
        for k,v in model.state_dict().items():
            diff=float((v.detach().cpu()-expected[k]).abs().max());maxdiff=max(maxdiff,diff)
            torch.testing.assert_close(v.detach().cpu(),expected[k],rtol=1e-5,atol=1e-6)
        result={'state':'passed','fp32_cpu_cuda_max_abs':fp32_max,'restart_weight_max_abs':maxdiff,'first':first,'second':second,'resumed':resumed,'gcs_restore_verified':True}
    elif args.mode=='benchmark':
        results=[]
        for microbatch in (2,4,8,16):
            guard.check();model,opt=new_model(parent,'cuda');torch.cuda.reset_peak_memory_stats()
            start=time.monotonic()
            try:
                for i in range(12):
                    if i==2:synchronize('cuda');start=time.monotonic()
                    update(model,opt,np.array(rows[i*16:(i+1)*16],dtype=np.int64),device='cuda',microbatch=microbatch,lr=6e-5,guard=guard)
                elapsed=time.monotonic()-start
                results.append({'microbatch':microbatch,'effective_tokens':8192,'measured_updates':10,'seconds':elapsed,'tokens_per_second':81920/elapsed,'peak_allocated_bytes':torch.cuda.max_memory_allocated()})
            except torch.cuda.OutOfMemoryError:
                results.append({'microbatch':microbatch,'state':'oom'})
            del model,opt;gc.collect();torch.cuda.empty_cache()
        result={'state':'completed_disposable_benchmark','results':results}
    elif args.mode=='memorize':
        cases=synthetic(tok);atomic_json(out/'synthetic.json',cases);backup(out/'synthetic.json',args.backup)
        model,opt=new_model(parent,'cuda')
        start_step=checkpoint_resume(model,opt)
        if args.resume:baseline=json.loads((out/'baseline.json').read_text())
        else:
            baseline={s:binding_scores(model,cs,tok,guard,'cuda') for s,cs in cases.items()}
            atomic_json(out/'baseline.json',baseline);backup(out/'baseline.json',args.backup)
        train=np.array([c['row'] for c in cases['train']]);labels=np.array([c['labels'] for c in cases['train']])
        history=[]
        for step in range(start_step,256):
            i=(step%8)*16
            row=update(model,opt,train[i:i+16],labels=labels[i:i+16],device='cuda',microbatch=16,lr=1.2e-4,guard=guard)
            history.append(dict(step=step+1,**row))
            if (step+1)%64==0:
                cp=out/f'memorize-{step+1:04d}.pt';publish_checkpoint(cp,model,opt,step+1)
                atomic_json(out/'progress.json',{'step':step+1,'last':row});backup(out/'progress.json',args.backup)
        endpoint={s:binding_scores(model,cs,tok,guard,'cuda') for s,cs in cases.items()}
        result={'state':'completed_diagnostic_not_acceptance','baseline':baseline,'endpoint':endpoint,'history':history,'note':'Diagnostic-only synthetic learning; never promoted to retained lineage.'}
    else:
        model,opt=new_model(parent,'cuda');start_step=checkpoint_resume(model,opt);history=[]
        if args.resume:baseline=json.loads((out/'baseline.json').read_text())
        else:
            baseline={'language':validation(model,held,'cuda',guard),'public':public_scores(model,json.loads((inputs/'public-diagnostics.json').read_text()),tok,guard)}
            atomic_json(out/'baseline.json',baseline);backup(out/'baseline.json',args.backup)
        for step in range(start_step,610):
            lr=6e-5+(args.lr-6e-5)*min((step+1)/64,1.)
            row=update(model,opt,np.array(rows[step*16:(step+1)*16],dtype=np.int64),device='cuda',microbatch=args.microbatch,lr=lr,guard=guard)
            history.append(dict(step=step+1,lr=lr,**row))
            if (step+1)%200==0 or step==609:
                cp=out/f'lr-{step+1:04d}.pt';publish_checkpoint(cp,model,opt,step+1)
                atomic_json(out/'progress.json',{'step':step+1,'last':row});backup(out/'progress.json',args.backup)
        result={'state':'completed_lr_screen_not_acceptance','lr':args.lr,'targets':610*8192,'baseline':baseline,'endpoint':{'language':validation(model,held,'cuda',guard),'public':public_scores(model,json.loads((inputs/'public-diagnostics.json').read_text()),tok,guard)},'history':history}
    atomic_json(out/'result.json',result);backup(out/'result.json',args.backup,restore_check=True)
    print(json.dumps({'state':result['state'],'mode':args.mode}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['preflight','benchmark','memorize','lr']);p.add_argument('--inputs',required=True);p.add_argument('--output',required=True);p.add_argument('--backup',required=True);p.add_argument('--seconds',type=int,default=1800);p.add_argument('--lr',type=float,default=6e-5);p.add_argument('--microbatch',type=int,default=8);p.add_argument('--resume')
    run(p.parse_args())
