"""Bounded, opt-in recovery evidence. No raw prompts, RNG bytes or tensor values.

Exact content hashes and tensor layouts locate the earliest differing boundary.
Tracing is synchronous and changes timing; it must be identity-bound on both
branches and its overhead budgeted. It does not establish CUDA determinism.
"""
import hashlib,json,os
from pathlib import Path
import torch
from cloud_training.nano_checkpoint import _exact_fingerprint,capture_rng

VERSION=1

def compare_traces(reference,resumed):
    """Compare matching traced branches; partial traces never establish a pass."""
    def read(path):
        files=sorted(Path(path).glob('*.json'))
        if not files:raise ValueError('Empty trace')
        if [int(p.name.split('-')[0]) for p in files]!=list(range(len(files))):raise ValueError('Trace record gap')
        rows=[json.loads(p.read_text()) for p in files]
        if rows[0]['event']!='initial' or rows[-1]['event'] not in ('after_optimizer','rollback'):
            raise ValueError('Incomplete trace boundaries')
        if len({r['identity_sha256'] for r in rows})!=1:raise ValueError('Mixed trace identities')
        return rows
    a,b=read(reference),read(resumed)
    if a[0]['identity_sha256']!=b[0]['identity_sha256']:raise ValueError('Trace identity mismatch')
    for index,(x,y) in enumerate(zip(a,b)):
        if (x['event'],x['update_start_step'])!=(y['event'],y['update_start_step']):
            return {'status':'hold','first_difference':index,'reason':'observation_schedule'}
        if x['values']!=y['values']:
            keys=sorted(set(x['values'])|set(y['values']))
            return {'status':'hold','first_difference':index,'event':x['event'],'update_start_step':x['update_start_step'],
                    'different_components':[k for k in keys if x['values'].get(k)!=y['values'].get(k)]}
    return {'status':'pass' if len(a)==len(b) else 'hold','records_reference':len(a),'records_resumed':len(b),
            'scope':'Matching traced observations only; not training or release acceptance'}

def fingerprint(value):
    def canonical(v):
        if isinstance(v,dict):return [(repr(k),canonical(v[k])) for k in sorted(v,key=lambda k:(type(k).__name__,repr(k)))]
        if isinstance(v,(tuple,list)):return [canonical(x) for x in v]
        if isinstance(v,bytes):return v.hex()
        return v
    exact=_exact_fingerprint(value)
    content=canonical(exact)
    tensors={}
    def layouts(v,path,fp):
        if torch.is_tensor(v):
            tensors[path]={'dtype':str(v.dtype),'shape':list(v.shape),'stride':list(v.stride()),'device':str(v.device),'storage_offset':v.storage_offset(),'content_sha256':fp[3]}
        elif isinstance(v,dict):
            for k,x in v.items():layouts(x,path+'.'+str(k),fp[1][k])
        elif isinstance(v,(tuple,list)):
            for i,x in enumerate(v):layouts(x,path+'.'+str(i),fp[1][i])
    layouts(value,'state',exact)
    return {'content_sha256':hashlib.sha256(json.dumps(content,separators=(',',':')).encode()).hexdigest(),'tensor_layouts':tensors}

class UpdateTrace:
    def __init__(self,path,*,limit,identity):
        if type(limit)is not int or not 1<=limit<=2:raise ValueError('Trace limit must be1..2absolute updates')
        self.path=Path(path);self.limit=limit;self.serial=0
        self.path.mkdir(exist_ok=False)
        self.identity_sha256=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    def record(self,event,step,**values):
        if type(step)is not int or step<0:raise ValueError('Invalid trace step')
        if step>=self.limit:return
        report={'schema':VERSION,'identity_sha256':self.identity_sha256,'event':event,'update_start_step':step,
                'values':{k:fingerprint(v) for k,v in values.items()}}
        path=self.path/f'{self.serial:04d}-{event}.json'
        with path.open('x') as f:
            json.dump(report,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
        self.serial+=1
    def state(self,event,step,model,optimizer,packing):
        if step>=self.limit:return
        self.record(event,step,model=model.state_dict(),optimizer=optimizer.state_dict(),
                    gradients={n:p.grad for n,p in model.named_parameters()},rng=capture_rng(),packing=packing.state_dict())
    def microbatch(self,step,model,index,x,y,phase):
        if step>=self.limit:return
        values={'microbatch':index,'inputs':x,'labels':y,'target_count':int((y!=-1).sum())}
        if phase=='after':values['gradients']={n:p.grad for n,p in model.named_parameters()}
        self.record('microbatch_'+phase,step,**values)
