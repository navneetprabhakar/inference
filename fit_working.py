"""Train one bounded curriculum stage with supervised assistant spans only."""
import argparse
import hashlib
import json
import math
import os
import random
import time
from pathlib import Path

import torch
from checkpoint import checksum, save as save_checkpoint, load as load_checkpoint
from gpt2 import GPT2
from guards import Guard
from local_chat import encode_frame
from plain_grounding import examples, PLAIN, JSON_REPLY, score
from pretrain import atomic_status
from tokenizer import EOT,load
from train import optimizer_for

SEED=1459


def chat_row(tok,history):
    ids,labels=[],[]
    for message in history:
        role=message['role']
        if role=='assistant':
            value={'text':message['text']} if 'text' in message else {'call':message['call']}
        elif role=='tool':
            value=message['result']
        else:
            value=message['text']
        head,body=encode_frame(tok,role,value)
        ids.extend(head+body)
        labels.extend([-100]*len(head)+(body if role=='assistant' else [-100]*len(body)))
    if len(ids)>1024:
        raise ValueError("overlength teaching conversation")
    return ids[:-1],labels[1:]


def copy_row(tok,text,v,use_json):
    prefix=tok.encode(text+(JSON_REPLY if use_json else PLAIN)).ids
    body=(json.dumps({'text':str(v)},separators=(',',':')) if use_json else ' '+str(v))
    answer=tok.encode(body).ids+[EOT]
    return (prefix+answer)[:-1],[-100]*(len(prefix)-1)+answer


def pack(rows):
    width=max(len(x) for x,_ in rows)
    x=torch.tensor([x+[0]*(width-len(x)) for x,_ in rows],device='mps')
    y=torch.tensor([y+[-100]*(width-len(y)) for _,y in rows],device='mps')
    return x,y


def run(args):
    root=args.run
    guard=Guard(root,args.minutes*60,resume=args.resume)
    status=dict(stage=args.stage,state='running',step=0,input_tokens=0,target_tokens=0)
    try:
        if checksum(args.base)!=args.sha:
            raise ValueError("base pin mismatch")
        torch.manual_seed(SEED)
        rng=random.Random(SEED)
        tok=load()
        model=GPT2().to('mps')
        model.load_state_dict(torch.load(args.base,map_location='cpu',weights_only=True,mmap=True))
        opt=optimizer_for(model)
        teach,_,_=examples()
        pools={}
        pools['copy']=[copy_row(tok,t,v,j) for t,v in teach for j in (True,False)]
        weights={'copy':1}
        if args.stage in ('chat','adapt'):
            from chat_teaching import examples as conversations, natural_examples
            from tool_teaching import examples as tools
            excluded=set(json.loads(Path('reports/working-chat/excluded-histories.json').read_text()))
            for name,make in [('chat',conversations),('natural',natural_examples),('tool',tools)]:
                rows=[]
                for history in make(SEED):
                    key=json.dumps(history,sort_keys=True,ensure_ascii=False).encode()
                    if hashlib.sha256(key).hexdigest() not in excluded:
                        rows.append(chat_row(tok,history))
                if not rows:
                    raise ValueError(f"all examples excluded for {name}")
                pools[name]=rows
            weights={'copy':.05,'chat':.35,'natural':.17,'tool':.43}
        loss_weights=None
        if args.stage=='adapt':
            from followon_curriculum import additional_pools
            weights=additional_pools(tok,SEED,pools,chat_row,copy_row)
            if not math.isclose(sum(weights.values()),1.):
                raise ValueError("invalid pool mix")
            values=[]
            for n in range(tok.get_vocab_size()):
                term=tok.decode([n]).strip()
                if n==EOT or not any(c.isalnum() for c in term) or term in ("text","call","name","arguments"):
                    values.append(.5)
                elif term.isdigit():
                    values.append(2.)
                else:
                    values.append(1.)
            loss_weights=torch.tensor(values,device='mps')
        identity=dict(seed=SEED,stage=args.stage,base=str(args.base),sha256=args.sha,
                   steps=args.steps,lr=args.lr,batch=args.batch,minutes=args.minutes,weights=weights,
                   corpus_counts={k:len(v) for k,v in pools.items()},
                   token_cap=args.token_cap,
                   dataset_sha256={k:hashlib.sha256(json.dumps(v).encode()).hexdigest() for k,v in pools.items()},
                   code_sha256={f:checksum(Path(f)) for f in ['fit_working.py','local_chat.py','gpt2.py','train.py']})
        if args.resume:
            if json.loads((root/'status.json').read_text())['state']!='running':
                raise ValueError("Only an interrupted active run may resume")
            state=load_checkpoint(root,identity)
            model.load_state_dict(state['model'])
            opt.load_state_dict(state['optimizer'])
            rng.setstate(state['rng'])
            status=state['status']
            # Charge all work since last durable checkpoint conservatively.
            previous=json.loads((root/'status.json').read_text())
            status['charged_inputs']=max(previous.get('charged_inputs',0),status['input_tokens'])
            del state
        else:
            atomic_status(root/'config.json',identity)
            status['charged_inputs']=0
            atomic_status(root/'status.json',status)
        for step in range(status["step"]+1,args.steps+1):
            guard.check()
            # Pick comparably sized histories within a task to limit padding waste.
            task=rng.choices(list(weights),weights=list(weights.values()))[0]
            choices=rng.choices(pools[task],k=args.batch*4)
            choices.sort(key=lambda row:len(row[0]))
            start=rng.choice(range(0,len(choices),args.batch))
            rows=choices[start:start+args.batch]
            x,y=pack(rows)
            n=int((y!=-100).sum())
            lr=args.lr*min(1,step/15)*(.25+.75*(1+math.cos(math.pi*step/args.steps))/2)
            for group in opt.param_groups:
                group['lr']=lr
            opt.zero_grad(set_to_none=True)
            count=sum(len(z[0]) for z in rows)
            if status['charged_inputs']+count>args.token_cap:
                raise ValueError("input token cap")
            status['charged_inputs']+=count
            atomic_status(root/'status.json',status)
            mask=y!=-100
            logits=model(x,prediction_mask=mask)
            if loss_weights is None:
                loss=torch.nn.functional.cross_entropy(logits,y[mask],reduction='sum')/n
            else:
                target=y[mask]
                importance=loss_weights[target]
                loss=(torch.nn.functional.cross_entropy(logits,target,reduction='none')*importance).sum()/importance.sum()
            loss.backward()
            norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
            opt.step()
            status.update(step=step,loss=loss.item(),gradient_norm=norm.item(),
                          target_tokens=status['target_tokens']+n,
                          input_tokens=status['input_tokens']+sum(len(z[0]) for z in rows))
            if args.stage!='format' and step%600==0:
                guard.check(force=True)
                save_checkpoint(root,dict(identity=identity,step=step,rng=rng.getstate(),status=status.copy(),
                                          model=model.state_dict(),optimizer=opt.state_dict()))
            if step%25==0:
                status['elapsed']=time.time()-guard.wall_start
                atomic_status(root/'status.json',status)
                with (root/'loss.jsonl').open('a') as f:
                    f.write(json.dumps(status)+'\n')
        guard.check(force=True)
        tmp=root/'weights.tmp'
        torch.save(model.state_dict(),tmp)
        os.replace(tmp,root/'weights.pt')
        status.update(state='trained',weights_sha256=checksum(root/'weights.pt'))
        if args.stage=='format':
            # New pairs, distinct from the earlier plain-text test and all teaching subjects.
            scenarios=['The clock repairer saw {v} on the timing dial.','The chocolate tempering probe gave {v}.',
                'The grain hopper sensor returned {v}.','A drum tuner measured {v}.','The pier tide meter read {v}.',
                'A chemistry titrator logged {v}.','A laundry meter indicated {v}.','The marble grader counted {v}.',
                'A centrifuge tachometer reported {v}.','The elevator monitor showed {v}.','The prism spectrometer logged {v}.',
                'The silversmith read {v} on the assay display.','The sailmaker found {v} on the tension gauge.',
                'The ticket booth scanner counted {v}.','The weather balloon receiver transmitted {v}.',
                'The sculpture gallery counter reported {v}.','The grain mill register showed {v}.',
                'The seam gauge displayed {v}.','The film projector gauge returned {v}.','The loom inspector read {v}.']
            eval_rng=random.Random(8721)
            pairs=[]
            for i,s in enumerate(scenarios):
                a,b,d=eval_rng.sample(range(10,100),3)
                previous=f'Previous reading: {d}.'
                pairs.append(dict(template=s+' '+previous if i%2 else previous+' '+s,values=[a,b]))
            results={fmt:score(model,tok,pairs,guard,fmt=='json') for fmt in ('plain','json')}
            atomic_status(root/'format-test.json',results)
            status['pairs']={k:v['pairs_passed'] for k,v in results.items()}
    except BaseException as e:
        status.update(state='stopped',reason=str(e))
        raise
    finally:
        status['elapsed']=time.time()-guard.wall_start
        atomic_status(root/'status.json',status)
        guard.close()


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('stage',choices=['format','chat','adapt'])
    p.add_argument('base',type=Path)
    p.add_argument('sha')
    p.add_argument('run',type=Path)
    p.add_argument('--steps',type=int,required=True)
    p.add_argument('--minutes',type=int,required=True)
    p.add_argument('--lr',type=float,default=.00012)
    p.add_argument('--batch',type=int,default=8)
    p.add_argument("--token-cap",type=int,default=4000000)
    p.add_argument("--resume",action="store_true")
    run(p.parse_args())
