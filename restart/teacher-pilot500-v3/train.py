"""Single-use, owner-approved bounded fresh-student research experiment.

The legacy training guard stays closed. This separate scope requires a passed
teacher acceptance receipt, pinned inputs, parent ticket and supervised budget.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
OUT=ROOT/'student-run-v1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(x,sort_keys=True,ensure_ascii=False,indent=2)+'\n');temp.replace(p)
def read_rows(p):return [json.loads(l) for l in Path(p).read_text().splitlines()]

def collate_chat(rows,bpe):
    encoded=[bpe.serialize(r['messages'],max_length=512) for r in rows];length=max(len(r[0]) for r in encoded)
    x=np.full((len(rows),length),2,np.int32);y=x.copy();mask=np.zeros_like(x,np.float32);attention=np.zeros_like(x,bool)
    for i,(a,b,c) in enumerate(encoded):
        n=len(a);x[i,:n]=a;y[i,:n]=b;mask[i,:n]=c;attention[i,:n]=True
    return x,y,mask,attention

def launch():
    from slm.restart.supervisor import TimeBudget,supervise
    from slm.restart import custody
    acceptance=json.loads((ROOT/'acceptance.json').read_text())
    if acceptance['status']!='PASS' or acceptance['usable']<475:raise ValueError('Teacher acceptance does not authorize training')
    if OUT.exists():raise FileExistsError('One fresh student attempt only')
    for name,h in acceptance['accepted_files'].items():
        if sha(ROOT/name)!=h:raise ValueError('Accepted data changed')
    OUT.mkdir()
    import shutil
    shutil.copytree(PROJECT/'restart/execution-v1/tokenizer-8192',OUT/'tokenizer')
    for split in ('train','development'):(OUT/(split+'.jsonl')).write_bytes((ROOT/(split+'-candidates.jsonl')).read_bytes())
    source=PROJECT/'restart/execution-v1/data-train'
    pin=sha(source/'manifest.json')
    (OUT/'acceptance.json').write_bytes((ROOT/'acceptance.json').read_bytes())
    contract=json.loads((ROOT/'contract.json').read_text());contract['training']['base_stage_seconds']=1800
    save(OUT/'contract.json',contract)
    inputs=[Path(__file__),PROJECT/'src/slm/backends/mlx_backend.py',PROJECT/'src/slm/common/config.py',
        PROJECT/'src/slm/common/tokenizer.py',PROJECT/'src/slm/restart/accumulation.py',PROJECT/'src/slm/restart/supervisor.py',
        PROJECT/'src/slm/restart/monitor.py',OUT/'train.jsonl',OUT/'development.jsonl',OUT/'acceptance.json',OUT/'contract.json',
        OUT/'tokenizer/core.json',OUT/'tokenizer/manifest.json']
    frozen={str(p):sha(p) for p in inputs}
    save(OUT/'source-pins.json',frozen)
    profile=custody.profile(read_roots=custody.runtime_roots(PROJECT)+[Path(__file__),source],write_root=OUT)
    (OUT/'worker.sb').write_text(profile)
    denied=[str(ROOT/'test-candidates.jsonl'),str(ROOT/'seeds.json'),str(PROJECT/'restart/execution-v1/data-final/tokens.u16')]
    probe='''import pathlib,socket,sys,json
for name in json.loads(sys.argv[1]):
 try:pathlib.Path(name).read_bytes()
 except PermissionError:pass
 else:raise RuntimeError('Forbidden holdout readable')
s=socket.socket()
try:s.bind(('127.0.0.1',0))
except PermissionError:pass
else:raise RuntimeError('Network accessible')
'''
    import subprocess
    env=dict(PATH='/usr/bin:/bin',PYTHONPATH=str(PROJECT/'src'),PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(OUT),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    check=subprocess.run(custody.command(OUT/'worker.sb',[sys.executable,'-c',probe,json.dumps(denied)]),cwd=OUT,env=env,capture_output=True,text=True,timeout=30)
    save(OUT/'custody-probe.json',dict(exit_code=check.returncode,stdout=check.stdout,stderr=check.stderr,denied=denied))
    if check.returncode:raise ValueError('Worker custody probe failed: '+check.stderr)
    deadline=min(time.time()+3600,1792816521.314878)
    ticket=dict(parent_pid=os.getpid(),output=str(OUT),code_pins_sha256=sha(OUT/'source-pins.json'),
        data_manifest_sha256=pin,profile_sha256=sha(OUT/'worker.sb'),acceptance_sha256=sha(OUT/'acceptance.json'),
        identity='diverse-pilot500-v3:'+sha(OUT/'contract.json'),deadline=deadline,parameters=5114112)
    save(OUT/'ticket.json',ticket)
    clock=TimeBudget(OUT/'time.sqlite',identity=ticket['identity'],seconds_cap=3600,deadline_utc=deadline)
    try:
        result=supervise(custody.command(OUT/'worker.sb',[sys.executable,str(Path(__file__).resolve()),'worker','--ticket-sha256',sha(OUT/'ticket.json')]),
            cwd=OUT,env=env,heartbeat=OUT/'heartbeat.json',budget=clock,receipt=OUT/'supervisor.json',tick=5)
    finally:clock.db.close()
    print(json.dumps(result),flush=True)

def generate(params,c,bpe,messages,max_tokens=64):
    import mlx.core as mx
    from slm.backends import mlx_backend as backend
    from slm.common.tokenizer import STRUCTURAL
    ids=[STRUCTURAL['bos']]
    for m in messages:ids += [STRUCTURAL[m['role']],*bpe.encode(m['content']),STRUCTURAL['message_end']]
    ids += [STRUCTURAL['assistant']]
    if len(ids)>=512:return '[CONTEXT_LIMIT]'
    output=[];cache=None;current=mx.array([ids],dtype=mx.int32)
    for k in range(min(max_tokens,512-len(ids))):
        logits,cache,_=backend.forward(params,c,current,cache=cache)
        token=int(mx.argmax(logits[0,-1]));mx.eval(cache)
        if token in (STRUCTURAL['message_end'],STRUCTURAL['eos']):break
        if token<10:return bpe.decode(output)+' [INVALID_STRUCTURAL_TOKEN]'
        output.append(token);current=mx.array([[token]],dtype=mx.int32)
    return bpe.decode(output)

def worker(ticket_sha):
    if sha(OUT/'ticket.json')!=ticket_sha:raise ValueError('Ticket changed')
    ticket=json.loads((OUT/'ticket.json').read_text())
    if ticket['parent_pid']!=os.getppid() or ticket['parameters']!=5114112 or time.time()>=ticket['deadline']:raise ValueError('Invalid owner/shape/deadline')
    if sha(OUT/'source-pins.json')!=ticket['code_pins_sha256'] or sha(OUT/'acceptance.json')!=ticket['acceptance_sha256']:raise ValueError('Changed gate or inputs')
    for name,h in json.loads((OUT/'source-pins.json').read_text()).items():
        if sha(name)!=h:raise ValueError('Frozen worker input changed')
    if json.loads((OUT/'acceptance.json').read_text())['status']!='PASS':raise ValueError('Acceptance failed')
    import sqlite3
    db=sqlite3.connect((OUT/'time.sqlite').as_uri()+'?mode=ro',uri=True)
    try:clock=db.execute('SELECT contract,charged,terminal FROM budget WHERE id=1').fetchone()
    finally:db.close()
    if (clock is None or json.loads(clock[0])!={'identity':ticket['identity'],'seconds_cap':3600,'deadline_utc':ticket['deadline']}
            or clock[2] is not None or not 0<clock[1]<=3600):raise ValueError('No matching supervised time reservation')
    with (OUT/'worker-started.json').open('x') as f:json.dump(dict(pid=os.getpid(),ticket_sha256=ticket_sha),f)
    # Scope and approval are validated before importing a backend or allocating weights.
    import mlx.core as mx
    from safetensors.numpy import save_file
    from slm.common.config import Config
    from slm.common.tokenizer import BPE
    from slm.backends import mlx_backend as backend
    from slm.restart.accumulation import TargetAccumulator
    from slm.restart.monitor import Monitor
    from slm.restart.token_store import TrainingTokens
    c=Config(vocab_size=8192,hidden_size=256,intermediate_size=640,num_layers=4,num_heads=4,num_kv_heads=4,max_seq_len=512)
    if c.parameter_count!=5114112:raise ValueError('Architecture changed')
    started=time.monotonic();rng=np.random.default_rng(20261022)
    weights={name:np.ones(shape,np.float32) if len(shape)==1 else rng.normal(0,.02/math.sqrt(2*c.num_layers) if name.endswith(('.o','.down')) else .02,shape).astype(np.float32) for name,shape in c.shapes().items()}
    params=backend.load(c,weights);moments={};global_step=0;optimizer_step=0;base_targets=0;sft_targets=0;best=float('inf');monitor=Monitor()
    save(OUT/'config.json',c.to_dict());save_file(weights,str(OUT/'initial.safetensors'));del weights
    # The tokenizer is part of the input binding and is copied by the parent.
    bpe=BPE.load(OUT/'tokenizer')
    train=read_rows(OUT/'train.jsonl');dev=read_rows(OUT/'development.jsonl')
    dev_cases=sorted(dev,key=lambda r:hashlib.sha256(('dev-response:'+r['id']).encode()).hexdigest())[:20]
    def tick():
        if time.time()>=ticket['deadline']:raise RuntimeError('Training deadline')
        if global_step>=1000:raise RuntimeError('Global update cap')
        save(OUT/'heartbeat.json',dict(pid=os.getpid(),monotonic=time.monotonic()))
    def checkpoint(name):
        tick();tmp=OUT/(name+'.tmp.safetensors');save_file(backend.export(params),str(tmp));tmp.replace(OUT/(name+'.safetensors'))
        save(OUT/(name+'.json'),dict(step=global_step,optimizer_step=optimizer_step,base_targets=base_targets,sft_targets=sft_targets,
            weights_sha256=sha(OUT/(name+'.safetensors')),config_sha256=sha(OUT/'config.json'),elapsed_seconds=time.monotonic()-started))
    def evaluate(label,responses=False):
        nonlocal best
        tick();total=0;weighted=0.
        for r in dev:
            x,y,m,pad=collate_chat([r],bpe);n=int(m.sum())
            value=backend.loss(params,c,mx.array(x),mx.array(y),mx.array(m),mx.array(pad),loss_implementation=backend.STABLE_LOSS_IMPLEMENTATION)
            weighted+=float(value)*n;total+=n;tick()
        nll=weighted/total
        if not math.isfinite(nll):raise ValueError('Nonfinite development loss')
        if nll<best:best=nll;checkpoint('best')
        values=[]
        if responses:
            for r in dev_cases:
                history=[];outputs=[]
                for u in r['users']:
                    history.append(dict(role='user',content=u));reply=generate(params,c,bpe,history)
                    history.append(dict(role='assistant',content=reply));outputs.append(reply);tick()
                values.append(dict(id=r['id'],family=r['family'],users=r['users'],replies=outputs,reference=[m['content'] for m in r['messages'] if m['role']=='assistant']))
        result=dict(label=label,step=global_step,development_nll=nll,assistant_targets=total,base_targets=base_targets,sft_targets=sft_targets,responses=values)
        save(OUT/(label+'.json'),result);print(json.dumps({k:v for k,v in result.items() if k!='responses'}),flush=True)
        return nll
    def update(micros,phase,lr,identities):
        nonlocal params,moments,global_step,optimizer_step,base_targets,sft_targets
        tick();count=sum(int(m[2].sum()) for m in micros)
        if phase=='base' and base_targets+count>2000000:raise ValueError('Base target cap')
        reservation=dict(step=global_step+1,optimizer_step=optimizer_step+1,phase=phase,targets=count,ids=identities,lr=lr,status='RESERVED')
        with (OUT/'work-ledger.jsonl').open('a') as f:f.write(json.dumps(reservation)+'\n');f.flush();os.fsync(f.fileno())
        acc=TargetAccumulator(c.shapes(),'mlx')
        for x,y,m,pad in micros:
            value,g=backend.value_and_grad(params,c,mx.array(x),mx.array(y),mx.array(m),mx.array(pad),loss_implementation=backend.STABLE_LOSS_IMPLEMENTATION)
            acc.add(value,g,int(m.sum()));tick()
        loss,g=acc.finish();norm=float(mx.sqrt(sum(mx.sum(mx.square(v)) for v in g.values())))
        proposed,state=backend.adamw(params,g,moments,optimizer_step+1,lr,clip=1)
        finite=all(bool(mx.all(mx.isfinite(v))) for v in proposed.values()) and all(bool(mx.all(mx.isfinite(t))) for pair in state.values() for t in pair)
        delta=float(sum(mx.sum(mx.square(proposed[k]-params[k])) for k in params));scale=float(sum(mx.sum(mx.square(v)) for v in params.values()))
        ratio=math.sqrt(delta/max(scale,1e-24));monitor.update(loss=loss,gradient_norm=norm,update_ratio=ratio,targets=base_targets+sft_targets+count,all_state_finite=finite)
        params,moments=proposed,state;global_step+=1;optimizer_step+=1
        if phase=='base':base_targets+=count
        else:sft_targets+=count
        reservation.update(status='COMPLETED',loss=loss,gradient_norm=norm,update_ratio=ratio,base_targets=base_targets,sft_targets=sft_targets)
        with (OUT/'work-ledger.jsonl').open('a') as f:f.write(json.dumps(reservation)+'\n');f.flush()
        if global_step%10==0:
            save(OUT/'progress.json',{**reservation,'elapsed_seconds':time.monotonic()-started});print(json.dumps(reservation),flush=True)
        if global_step%50==0:checkpoint('latest')
    try:
        tick();evaluate('initial')
        store=TrainingTokens(PROJECT/'restart/execution-v1/data-train',manifest_sha256=ticket['data_manifest_sha256'])
        spans=[];reserved=0
        for doc,r in store._index.items():
            for first in range(0,r['targets'],512):
                n=min(512,r['targets']-first,2000000-reserved)
                if n<=0:break
                spans.append((doc,first,first+n));reserved+=n
            if reserved==2000000:break
        pending=[];identities=[];count=0
        for index in range(0,len(spans),4):
            if time.monotonic()-started>=1800:break
            micro=spans[index:index+4];x,y,m,pad,ids=store.microbatch(micro)
            pending.append((x,y,m,pad));identities.extend(micro);count+=int(m.sum())
            if count>=4096 or index+4>=len(spans):
                rate=.0002*min(1.,(base_targets+count)/250000)*(.1+.9*.5*(1+math.cos(math.pi*min(1.,base_targets/2000000))))
                update(pending,'base',rate,identities);pending=[];identities=[];count=0
        checkpoint('after-base');evaluate('after-base',responses=True)
        moments={};optimizer_step=0;monitor=Monitor();losses=[]
        for epoch in range(1,4):
            if epoch==3:
                save(OUT/'awaiting-assessment.json',dict(phase='after two SFT passes',maximum_additional_passes=1))
                wait=time.monotonic()
                while not (OUT/'corrective-decision.json').exists():
                    tick()
                    if time.monotonic()-wait>180:raise RuntimeError('Corrective assessment not received within bound')
                    time.sleep(.25)
                choice=json.loads((OUT/'corrective-decision.json').read_text())
                if not choice.get('run_one_corrective_pass',False):break
                if len(losses)<2 or losses[-1]>losses[-2]*.99:break
            order=list(train);random.Random(20261022+epoch).shuffle(order)
            for index in range(0,len(order),4):
                group=order[index:index+4];lr=.0001*min(1.,(optimizer_step+1)/20)*(0.5 if epoch==3 else 1)
                update([collate_chat(group,bpe)],'sft',lr,[dict(id=r['id'],epoch=epoch) for r in group])
            checkpoint('latest');nll=evaluate(f'after-sft-{epoch}',responses=True);losses.append(nll)
            if len(losses)>1 and nll>min(losses[:-1])*1.05:raise RuntimeError('Development loss regression')
        checkpoint('latest')
        save(OUT/'result.json',dict(status='BOUNDED_TRAINING_COMPLETE_NOT_CAPABILITY_CERTIFICATION',step=global_step,
             base_targets=base_targets,sft_targets=sft_targets,elapsed_seconds=time.monotonic()-started,best_development_nll=best))
    except BaseException as e:
        save(OUT/'result.json',dict(status='STOPPED',error=type(e).__name__+': '+str(e),step=global_step,
             base_targets=base_targets,sft_targets=sft_targets,elapsed_seconds=time.monotonic()-started))
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['launch','worker']);parser.add_argument('--ticket-sha256');a=parser.parse_args()
    launch() if a.action=='launch' else worker(a.ticket_sha256)
