"""Pure CPU Torch/NumPy state interchange for an already verified own model.

This format preserves caller-pinned provenance; it does not load production
checkpoints, prove ancestry, authorize migration, or implement crash recovery.
The caller must verify its source checkpoint before exporting its live objects.
"""
from collections import defaultdict
from dataclasses import asdict, is_dataclass
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
import torch

SHA = re.compile(r'[0-9a-f]{64}')


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def checksum(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def shapes_for(config):
    config=asdict(config) if is_dataclass(config) else dict(config)
    if set(config)!={'vocabulary','context','width','heads','depth'}:
        raise ValueError('unexpected architecture fields')
    if any(type(v)!=int or v<=0 for v in config.values()) or config['width']%config['heads']:
        raise ValueError('invalid architecture dimensions')
    w=config['width']
    shapes={'tokens.weight':(config['vocabulary'],w),'positions.weight':(config['context'],w),
            'final_norm.weight':(w,),'final_norm.bias':(w,)}
    for i in range(config['depth']):
        prefix=f'blocks.{i}.'
        for norm in ('before_attention','before_mlp'):
            shapes[prefix+norm+'.weight']=(w,);shapes[prefix+norm+'.bias']=(w,)
        for name,nin,nout in [('qkv',w,3*w),('attention_out',w,w),('mlp.0',w,4*w),('mlp.2',4*w,w)]:
            shapes[prefix+name+'.weight']=(nout,nin);shapes[prefix+name+'.bias']=(nout,)
    if sum(math.prod(s) for s in shapes.values())>200_000_000:
        raise ValueError('architecture exceeds own-model parameter ceiling')
    return config,shapes


def check_model(model, config):
    config,shapes=shapes_for(config)
    named=dict(model.named_parameters())
    if (set(named)!=set(shapes) or set(model.state_dict())!=set(named)
            or any(tuple(p.shape)!=shapes[n] or p.dtype!=torch.float32
                   or p.device.type!='cpu' for n,p in named.items())):
        raise ValueError('model architecture/device/dtype differs')
    if (len(model.blocks)!=config['depth'] or any(b.heads!=config['heads'] for b in model.blocks)
            or model.final_norm.eps!=1e-5 or any(b.before_attention.eps!=1e-5 or b.before_mlp.eps!=1e-5
                                                or b.mlp[1].approximate!='tanh' for b in model.blocks)):
        raise ValueError('model attention/normalization semantics differ')
    return named


def optimizer_policy(optimizer):
    if type(optimizer) is not torch.optim.AdamW or len(optimizer.param_groups)!=2:
        raise ValueError('expected exactly two native AdamW groups')
    groups=[]
    for group in optimizer.param_groups:
        values=dict(learning_rate=float(group['lr']),betas=list(group['betas']),epsilon=group['eps'],
                    weight_decay=group['weight_decay'],bias_correction=True,
                    foreach=group.get('foreach'),fused=group.get('fused'),amsgrad=group.get('amsgrad',False),
                    maximize=group.get('maximize',False),capturable=group.get('capturable',False),
                    differentiable=group.get('differentiable',False))
        groups.append(values)
    return groups


def validate_policy(policy):
    if not isinstance(policy,list) or len(policy)!=2:raise ValueError('invalid optimizer policy')
    for i,g in enumerate(policy):
        required={'learning_rate','betas','epsilon','weight_decay','bias_correction','foreach','fused',
                  'amsgrad','maximize','capturable','differentiable'}
        if set(g)!=required:raise ValueError('optimizer policy fields differ')
        if (not math.isfinite(g['learning_rate']) or g['learning_rate']<=0 or not math.isfinite(g['epsilon'])
                or g['epsilon']<=0 or not math.isfinite(g['weight_decay']) or g['weight_decay']<0):
            raise ValueError('invalid optimizer scalars')
        if len(g['betas'])!=2 or any(not math.isfinite(b) or not 0<=b<1 for b in g['betas']):
            raise ValueError('invalid Adam betas')
        if (g['bias_correction'] is not True or g['foreach'] is not False or g['fused'] not in (None,False)
                or any(g[k] is not False for k in ('amsgrad','maximize','capturable','differentiable'))):
            raise ValueError('unsupported AdamW execution policy')
        if i==1 and g['weight_decay']!=0:raise ValueError('nonmatrix group must have zero decay')
    if policy[0]['betas']!=policy[1]['betas'] or policy[0]['epsilon']!=policy[1]['epsilon']:
        raise ValueError('group Adam moment semantics differ')


def validate(meta,arrays,*,expected_identity,expected_source,expected_progress,expected_optimizer):
    if set(meta)!={'schema','identity','source','progress','optimizer','parameter_order','groups','mps_rng_present'} or meta['schema']!=1:
        raise ValueError('neutral format schema mismatch')
    for key,expected in [('identity',expected_identity),('source',expected_source),('progress',expected_progress),('optimizer',expected_optimizer)]:
        if canonical(meta[key])!=canonical(expected):raise ValueError('caller-pinned '+key+' changed')
    identity=meta['identity']
    if not {'model','tokenizer','scheduler','initialization','seed','corpus'}<=identity.keys():
        raise ValueError('complete model/tokenizer/scheduler/lineage identity required')
    init=identity['initialization']
    if init!='random':
        if (not isinstance(init,dict) or init.get('mode')!='own_pretraining'
                or not isinstance(init.get('path'),str) or not SHA.fullmatch(init.get('sha256',''))
                or not SHA.fullmatch(init.get('random_lineage_root',''))):
            raise ValueError('own-random initialization identity required')
    if not isinstance(identity['tokenizer'],dict) or not identity['tokenizer']:
        raise ValueError('tokenizer identity missing')
    if type(identity['seed'])!=int or not isinstance(identity['scheduler'],dict):
        raise ValueError('seed/scheduler identity missing')
    source=meta['source']
    if (not {'path','sha256','bytes'}<=source.keys() or not isinstance(source['path'],str)
            or not SHA.fullmatch(source['sha256']) or type(source['bytes'])!=int or source['bytes']<=0):
        raise ValueError('source artifact receipt required')
    config,shapes=shapes_for(identity['model'])
    order=meta['parameter_order']
    if not isinstance(order,list) or len(order)!=len(set(order)) or set(order)!=set(shapes):
        raise ValueError('architecture parameter inventory mismatch')
    groups=meta['groups']
    if not isinstance(groups,list) or len(groups)!=2:raise ValueError('invalid parameter groups')
    for index,names in enumerate(groups):
        expected={n for n,s in shapes.items() if (len(s)>=2)==(index==0)}
        if len(names)!=len(set(names)) or set(names)!=expected:
            raise ValueError('parameter group membership differs from matrix-only decay')
    validate_policy(meta['optimizer'])
    p=meta['progress']
    keys={'campaign_step','optimizer_step','initial_optimizer_step','trained_tokens','reserved_tokens',
          'targets_per_update','initial_source_offset','source_offset'}
    if set(p)!=keys or any(type(v)!=int or v<0 for v in p.values()) or p['targets_per_update']<=0:
        raise ValueError('invalid explicit progress counters')
    if (p['optimizer_step']!=p['initial_optimizer_step']+p['campaign_step']
            or p['trained_tokens']!=p['campaign_step']*p['targets_per_update']
            or p['reserved_tokens']<p['trained_tokens'] or p['reserved_tokens']%p['targets_per_update']
            or p['source_offset']!=p['initial_source_offset']+p['trained_tokens']):
        raise ValueError('optimizer/campaign/data counters are inconsistent')
    ceiling=identity.get('protocol',{}).get('target_tokens')
    if ceiling is not None and p['reserved_tokens']>ceiling:raise ValueError('attempted targets exceed pinned campaign budget')
    expected={kind+'::'+name for name in order for kind in ('weight','m','v','step')}|{'cpu_rng','mps_rng'}
    if set(arrays)!=expected:raise ValueError('missing or extra neutral arrays')
    for name,shape in shapes.items():
        for kind in ('weight','m','v'):
            a=arrays[kind+'::'+name]
            if not isinstance(a,np.ndarray) or a.dtype!=np.float32 or a.shape!=shape or not np.isfinite(a).all():
                raise ValueError('invalid FP32 parameter or moment')
        if (arrays['v::'+name]<0).any():raise ValueError('negative second moment')
        step=arrays['step::'+name]
        if (not isinstance(step,np.ndarray) or step.shape!=() or step.dtype not in (np.float32,np.float64)
                or not np.isfinite(step) or float(step)!=p['optimizer_step']):
            raise ValueError('native optimizer step differs from explicit optimizer counter')
    if type(meta['mps_rng_present'])!=bool:raise ValueError('invalid MPS RNG presence flag')
    for key in ('cpu_rng','mps_rng'):
        value=arrays[key]
        if not isinstance(value,np.ndarray) or value.dtype!=np.uint8 or value.ndim!=1 or value.size>1024**2:
            raise ValueError('invalid opaque RNG bytes')
    if arrays['cpu_rng'].size==0 or bool(arrays['mps_rng'].size)!=meta['mps_rng_present']:
        raise ValueError('missing RNG state or inconsistent absence marker')
    return config


def export_objects(model,optimizer,*,identity,source,progress,cpu_rng,mps_rng,expected_identity,expected_source,
                   expected_progress,expected_optimizer):
    """Export trusted loaded CPU objects; no serialized optimizer-ID assumptions."""
    named=check_model(model,identity['model'])
    arrays={};groups=[]
    by_object={id(p):n for n,p in named.items()}
    for group in optimizer.param_groups:
        names=[]
        for p in group['params']:
            if id(p) not in by_object:raise ValueError('optimizer includes a parameter outside the model')
            names.append(by_object[id(p)])
        groups.append(names)
    if set(optimizer.state)!={p for p in named.values()}:
        raise ValueError('optimizer must contain initialized state for exactly every model parameter')
    for name,p in named.items():
        state=optimizer.state[p]
        if set(state)!={'step','exp_avg','exp_avg_sq'}:raise ValueError('unsupported or incomplete AdamW state')
        for kind,tensor in [('weight',p),('m',state['exp_avg']),('v',state['exp_avg_sq']),('step',state['step'])]:
            if not isinstance(tensor,torch.Tensor) or tensor.device.type!='cpu':raise ValueError('CPU tensors required')
            arrays[kind+'::'+name]=tensor.detach().numpy().copy()
    for key,tensor in [('cpu_rng',cpu_rng),('mps_rng',mps_rng)]:
        if tensor is None and key=='mps_rng':arrays[key]=np.empty((0,),dtype=np.uint8)
        else:
            if not isinstance(tensor,torch.Tensor) or tensor.device.type!='cpu' or tensor.dtype!=torch.uint8:
                raise ValueError('RNG state must be opaque CPU uint8 tensor')
            arrays[key]=tensor.numpy().copy()
    meta=dict(schema=1,identity=json.loads(canonical(identity)),source=json.loads(canonical(source)),
              progress=dict(progress),optimizer=optimizer_policy(optimizer),parameter_order=list(named),groups=groups,
              mps_rng_present=mps_rng is not None)
    validate(meta,arrays,expected_identity=expected_identity,expected_source=expected_source,
             expected_progress=expected_progress,expected_optimizer=expected_optimizer)
    return meta,arrays


def import_objects(model,optimizer,meta,arrays,*,expected_identity,expected_source,expected_progress,expected_optimizer):
    """Validate fully, then mutate caller-supplied fresh CPU objects by name."""
    config=validate(meta,arrays,expected_identity=expected_identity,expected_source=expected_source,
                    expected_progress=expected_progress,expected_optimizer=expected_optimizer)
    named=check_model(model,config)
    if type(optimizer) is not torch.optim.AdamW or len(optimizer.param_groups)!=2:
        raise ValueError('destination must be native two-group AdamW')
    current=[p for g in optimizer.param_groups for p in g['params']]
    if len(current)!=len(named) or {id(p) for p in current}!={id(p) for p in named.values()}:
        raise ValueError('destination optimizer does not own exactly the destination model')
    # Stage every tensor and group before mutation; validation failure leaves
    # destination objects untouched. Runtime allocation failure is not rollback.
    weights={n:torch.from_numpy(arrays['weight::'+n].copy()) for n in named}
    state=defaultdict(dict)
    for n,p in named.items():
        state[p]={key:torch.from_numpy(arrays[kind+'::'+n].copy()) for key,kind in
                  [('step','step'),('exp_avg','m'),('exp_avg_sq','v')]}
    policies=[]
    for i,policy in enumerate(meta['optimizer']):
        values={k:policy[k] for k in ('weight_decay','foreach','fused','amsgrad','maximize','capturable','differentiable')}
        values.update(lr=policy['learning_rate'],betas=tuple(policy['betas']),eps=policy['epsilon'],
                      params=[named[n] for n in meta['groups'][i]])
        policies.append(values)
    with torch.no_grad():
        for n,p in named.items():p.copy_(weights[n])
    optimizer.state=state
    for group,values in zip(optimizer.param_groups,policies):group.update(values)
    # No global RNG side effect: the caller chooses if/when to apply CPU state.
    return dict(progress=dict(meta['progress']),cpu_rng=torch.from_numpy(arrays['cpu_rng'].copy()),
                mps_rng=torch.from_numpy(arrays['mps_rng'].copy()) if meta['mps_rng_present'] else None)


def write_bundle(directory,meta,arrays,**expected):
    """Exclusive tiny-experiment output; not a production atomic publication API."""
    validate(meta,arrays,**expected)
    directory=Path(directory);directory.mkdir(exist_ok=False)
    path=directory/'state.npz';np.savez(path,**arrays)
    receipt=dict(schema=1,metadata=meta,data_file='state.npz',bytes=path.stat().st_size,sha256=checksum(path))
    receipt['receipt_sha256']=hashlib.sha256(canonical(receipt)).hexdigest()
    (directory/'receipt.json').write_bytes(canonical(receipt)+b'\n')


def read_bundle(directory,**expected):
    directory=Path(directory);receipt=json.loads((directory/'receipt.json').read_bytes())
    signature=receipt.pop('receipt_sha256')
    if hashlib.sha256(canonical(receipt)).hexdigest()!=signature or receipt.get('schema')!=1 or receipt.get('data_file')!='state.npz':
        raise ValueError('neutral receipt mismatch')
    path=directory/'state.npz'
    if path.is_symlink() or path.stat().st_size!=receipt['bytes'] or checksum(path)!=receipt['sha256']:
        raise ValueError('neutral data checksum/size mismatch')
    with np.load(path,allow_pickle=False) as f:arrays={n:f[n] for n in f.files}
    validate(receipt['metadata'],arrays,**expected)
    return receipt['metadata'],arrays
