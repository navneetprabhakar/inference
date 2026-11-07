"""Own-model neutral-state adapter for disposable full-size MLX experiments.

No production loader/CLI, no automatic GPU selection, no promotion. Callers must
verify own_base_neutral_state provenance and own all budgets/locks/watchdogs.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import os
import numpy as np
# Deliberately NumPy-only: Torch and MLX remain in separate environments.
class neutral:
    @staticmethod
    def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    @staticmethod
    def checksum(path):
        with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    @staticmethod
    def shapes_for(config):
        from mlx_base import Config,parameter_shapes
        cfg=Config(**config);return dict(config),parameter_shapes(cfg)
    @staticmethod
    def validate(meta,arrays,**pinned):
        if set(meta)!={'schema','identity','source','progress','optimizer','parameter_order','groups','mps_rng_present'} or meta['schema']!=1:raise ValueError('neutral source schema')
        for key in ('identity','source','progress','optimizer'):
            if neutral.canonical(meta[key])!=neutral.canonical(pinned['expected_'+key]):raise ValueError('pinned source '+key+' changed')
        _,shapes=neutral.shapes_for(meta['identity']['model']);names=meta['parameter_order']
        if len(names)!=len(set(names)) or set(names)!=set(shapes):raise ValueError('neutral source parameter inventory')
        if len(meta['groups'])!=2 or len(meta['optimizer'])!=2:raise ValueError('source groups')
        for i,names in enumerate(meta['groups']):
            if len(names)!=len(set(names)) or set(names)!={n for n,shape in shapes.items() if (len(shape)>=2)==(i==0)}:raise ValueError('source group membership')
            g=meta['optimizer'][i]
            if g['bias_correction'] is not True or g['foreach'] is not False or g['fused'] not in (False,None) or any(g[k] for k in ('amsgrad','maximize','capturable','differentiable')):raise ValueError('source optimizer execution policy')
            if not math.isfinite(g['learning_rate']) or g['learning_rate']<=0 or not math.isfinite(g['epsilon']) or g['epsilon']<=0 or not 0<=g['weight_decay'] or any(not 0<=b<1 for b in g['betas']):raise ValueError('source optimizer scalars')
        if meta['optimizer'][1]['weight_decay']!=0 or any(meta['optimizer'][0][k]!=meta['optimizer'][1][k] for k in ('betas','epsilon')):raise ValueError('source group policies')
        p=meta['progress']
        if any(type(v)is not int or v<0 for v in p.values()) or p['targets_per_update']<=0 or p['optimizer_step']!=p['initial_optimizer_step']+p['campaign_step'] or p['trained_tokens']!=p['campaign_step']*p['targets_per_update'] or p['source_offset']!=p['initial_source_offset']+p['trained_tokens'] or p['reserved_tokens']<p['trained_tokens']:raise ValueError('source progress')
        wanted={k+'::'+n for n in shapes for k in ('weight','m','v','step')}|{'cpu_rng','mps_rng'}
        if set(arrays)!=wanted:raise ValueError('source array inventory')
        for n,shape in shapes.items():
            for k in ('weight','m','v'):
                a=arrays[k+'::'+n]
                if a.dtype!=np.float32 or a.shape!=shape or not np.isfinite(a).all():raise ValueError('source tensor invalid')
            if (arrays['v::'+n]<0).any():raise ValueError('negative source moment')
            a=arrays['step::'+n]
            if a.shape!=() or a.dtype not in (np.float32,np.float64) or float(a)!=p['optimizer_step']:raise ValueError('source step')
        for n in ('cpu_rng','mps_rng'):
            a=arrays[n]
            if a.dtype!=np.uint8 or a.ndim!=1 or a.size>1024**2:raise ValueError('opaque source RNG')
        if arrays['cpu_rng'].size==0 or bool(arrays['mps_rng'].size)!=meta['mps_rng_present']:raise ValueError('source RNG presence')



def expected(meta):
    return {'expected_'+key:meta[key] for key in ('identity','source','progress','optimizer')}


def convert_neutral(meta, arrays, *, pinned):
    """Build TrainCore-native state without changing original progress/RNG bytes."""
    neutral.validate(meta,arrays,**pinned)
    policy=meta['optimizer'];step=meta['progress']['optimizer_step']
    if policy[0]['learning_rate']!=policy[1]['learning_rate']:
        raise ValueError('TrainCore requires equal group learning rates')
    cfg,shapes=neutral.shapes_for(meta['identity']['model'])
    native={kind+'::'+name:arrays[kind+'::'+name] for name in shapes for kind in ('weight','m','v')}
    for group in (0,1):
        native[f'group_step::{group}']=np.array(step,dtype=np.uint64)
        native[f'group_lr::{group}']=np.array(policy[group]['learning_rate'],dtype=np.float32)
    core_meta=dict(cursor=dict(step=step,trained_tokens=meta['progress']['trained_tokens']),
                   betas=policy[0]['betas'],epsilon=policy[0]['epsilon'],matrix_decay=policy[0]['weight_decay'],clip=1.)
    # core.cursor.step is ONLY the native optimizer counter. It is not a
    # campaign step or a data offset. Source progress is immutable below.
    provenance=dict(schema=1,source_neutral=deepcopy(meta),
                    source_rng_sha256={name:hashlib.sha256(arrays[name].tobytes()).hexdigest() for name in ('cpu_rng','mps_rng')},
                    source_step_dtype={name:str(arrays['step::'+name].dtype) for name in shapes},
                    note='Original Torch LR and opaque RNG bytes preserved in provenance; MLX native LR tensor is float32. No cross-runtime RNG equivalence.')
    return cfg,core_meta,native,provenance


def validate_native(meta, arrays, *, benchmark_identity, source_provenance):
    if set(meta)!={'schema','benchmark_identity','source_provenance','benchmark_progress','core'} or meta['schema']!=1:
        raise ValueError('native benchmark schema')
    if meta['benchmark_identity']!=benchmark_identity or meta['source_provenance']!=source_provenance:
        raise ValueError('native benchmark/source identity')
    original=source_provenance['source_neutral'];_,shapes=neutral.shapes_for(original['identity']['model'])
    progress=meta['benchmark_progress'];core=meta['core'];base=original['progress']
    required={'committed_updates','committed_targets','source_offset','optimizer_step'}
    if set(progress)!=required or any(type(v)is not int or v<0 for v in progress.values()):raise ValueError('benchmark progress')
    if (progress['committed_targets']!=progress['committed_updates']*base['targets_per_update']
        or progress['source_offset']!=base['source_offset']+progress['committed_targets']
        or progress['optimizer_step']!=base['optimizer_step']+progress['committed_updates']
        or core['cursor']!={'step':progress['optimizer_step'],'trained_tokens':base['trained_tokens']+progress['committed_targets']}):
        raise ValueError('native optimizer and benchmark counters differ')
    policy=original['optimizer']
    if core['betas']!=policy[0]['betas'] or core['epsilon']!=policy[0]['epsilon'] or core['matrix_decay']!=policy[0]['weight_decay'] or core['clip']!=1.:
        raise ValueError('native optimizer policy')
    keys={kind+'::'+name for name in shapes for kind in ('weight','m','v')}|{f'group_{k}::{i}' for i in (0,1) for k in ('step','lr')}|{'cpu_rng','mps_rng'}
    if set(arrays)!=keys:raise ValueError('native array inventory')
    for name,shape in shapes.items():
        for kind in ('weight','m','v'):
            a=arrays[kind+'::'+name]
            if a.dtype!=np.float32 or a.shape!=shape or not np.isfinite(a).all():raise ValueError('native tensor invalid')
        if (arrays['v::'+name]<0).any():raise ValueError('negative native moment')
    for i in (0,1):
        step=arrays[f'group_step::{i}'];lr=arrays[f'group_lr::{i}']
        if step.shape!=() or step.dtype!=np.uint64 or int(step)!=progress['optimizer_step']:raise ValueError('native group step')
        if lr.shape!=() or lr.dtype!=np.float32 or not np.isfinite(lr) or float(lr)<=0:raise ValueError('native group LR')
    if not np.array_equal(arrays['group_lr::0'],arrays['group_lr::1']):raise ValueError('native group LR mismatch')
    for name in ('cpu_rng','mps_rng'):
        a=arrays[name]
        if a.dtype!=np.uint8 or a.ndim!=1 or hashlib.sha256(a.tobytes()).hexdigest()!=source_provenance['source_rng_sha256'][name]:raise ValueError('opaque RNG bytes changed')


def _core_type():
    import mlx_train_core as core
    class TracedCore(core.TrainCore):
        def __init__(self,*args,**kwargs):
            self.trace_count=0
            super().__init__(*args,**kwargs)
        def _update(self,*args):
            # Python executes on compilation/cache miss, not each compiled GPU update.
            self.trace_count+=1
            return super()._update(*args)
    return TracedCore


class DisposableCore:
    def __init__(self, meta, arrays, *, pinned, benchmark_identity, device, compiled=True, native=None):
        import mlx_train_core as core
        cfg,core_meta,native_arrays,self.provenance=convert_neutral(meta,arrays,pinned=pinned)
        self.identity=deepcopy(benchmark_identity);self.source_meta=deepcopy(meta)
        self.rng={n:arrays[n].copy() for n in ('cpu_rng','mps_rng')}
        self.progress=dict(committed_updates=0,committed_targets=0,source_offset=meta['progress']['source_offset'],optimizer_step=meta['progress']['optimizer_step'])
        if native is not None:
            saved,native_arrays=native;validate_native(saved,native_arrays,benchmark_identity=self.identity,source_provenance=self.provenance)
            core_meta=saved['core'];self.progress=dict(saved['benchmark_progress'])
        parameters={n:native_arrays['weight::'+n] for n in meta['parameter_order']}
        self.core=_core_type()(parameters,core.Config(**cfg),device=device,compiled=compiled,
             learning_rate=float(native_arrays['group_lr::0']),betas=tuple(core_meta['betas']),epsilon=core_meta['epsilon'],matrix_decay=core_meta['matrix_decay'],clip=1.,restored=(core_meta,{k:v for k,v in native_arrays.items() if k not in self.rng}))
    @classmethod
    def from_native(cls,meta,arrays,*,benchmark_identity,source_provenance,device,compiled=True):
        import mlx_train_core as core
        validate_native(meta,arrays,benchmark_identity=benchmark_identity,source_provenance=source_provenance)
        obj=cls.__new__(cls);obj.provenance=deepcopy(source_provenance);obj.identity=deepcopy(benchmark_identity)
        obj.source_meta=deepcopy(source_provenance['source_neutral']);obj.rng={n:arrays[n].copy() for n in ('cpu_rng','mps_rng')};obj.progress=dict(meta['benchmark_progress'])
        cfg=obj.source_meta['identity']['model'];params={n:arrays['weight::'+n] for n in obj.source_meta['parameter_order']};cm=meta['core']
        obj.core=_core_type()(params,core.Config(**cfg),device=device,compiled=compiled,learning_rate=float(arrays['group_lr::0']),betas=tuple(cm['betas']),epsilon=cm['epsilon'],matrix_decay=cm['matrix_decay'],clip=cm['clip'],restored=(cm,{k:v for k,v in arrays.items() if k not in obj.rng}))
        return obj
    def restore_source_in_place(self,arrays,*,pinned):
        import mlx.core as mx
        _,cm,state,provenance=convert_neutral(self.source_meta,arrays,pinned=pinned)
        if provenance!=self.provenance:raise ValueError('source restore provenance')
        with mx.stream(self.core.device):
            for n in self.core.params:self.core.params[n]=mx.array(state['weight::'+n])
            for i,opt in enumerate(self.core.optimizers):
                opt.state['step']=mx.array(state[f'group_step::{i}']);opt.state['learning_rate']=mx.array(state[f'group_lr::{i}'])
                for n,p in self.core.params.items():
                    if (p.ndim>=2)==(i==0):
                        for kind in ('m','v'):opt.state[n][kind]=mx.array(state[kind+'::'+n])
            mx.eval(self.core.state)
        self.core.cursor=dict(cm['cursor']);p=self.source_meta['progress']
        self.progress=dict(committed_updates=0,committed_targets=0,source_offset=p['source_offset'],optimizer_step=p['optimizer_step'])
    def step(self,batches,*,learning_rate):
        actual=sum(x.shape[0]*(x.shape[1]-1) for x in batches)
        if actual!=self.source_meta['progress']['targets_per_update']:raise ValueError('effective update size changed')
        loss,norm=self.core.step(batches,learning_rate=learning_rate)
        self.progress['committed_updates']+=1;self.progress['committed_targets']+=actual
        self.progress['source_offset']+=actual;self.progress['optimizer_step']+=1
        return loss,norm
    def snapshot(self):
        core,arrays=self.core.snapshot();arrays.update({n:v.copy() for n,v in self.rng.items()})
        meta=dict(schema=1,benchmark_identity=self.identity,source_provenance=self.provenance,benchmark_progress=dict(self.progress),core=core)
        validate_native(meta,arrays,benchmark_identity=self.identity,source_provenance=self.provenance)
        return meta,arrays


def publish(directory,meta,arrays,*,benchmark_identity,source_provenance,check=lambda:None):
    """Atomic receipt publication; old accepted file survives any precommit failure.

    Directory must be benchmark-owned; caller supplies exclusive ownership and
    disk/output bounds. At most one old native file and one pending replacement.
    """
    validate_native(meta,arrays,benchmark_identity=benchmark_identity,source_provenance=source_provenance)
    directory=Path(directory);directory.mkdir(exist_ok=True);check()
    receipt=directory/'accepted.json';old=json.loads(receipt.read_text()) if receipt.exists() else None
    if old is not None:read_native(directory,benchmark_identity=benchmark_identity,source_provenance=source_provenance)
    pending=directory/'pending.npz';pending_meta=directory/'pending.json'
    if pending.exists() or pending_meta.exists():raise ValueError('partial prior publication; explicit review required')
    with pending.open('xb') as f:np.savez(f,**arrays);f.flush();os.fsync(f.fileno())
    check();digest=neutral.checksum(pending);target=directory/(digest+'.npz')
    saved=dict(schema=1,file=target.name,bytes=pending.stat().st_size,sha256=digest,metadata=meta)
    saved['receipt_sha256']=hashlib.sha256(neutral.canonical(saved)).hexdigest()
    with pending_meta.open('x') as f:json.dump(saved,f,sort_keys=True);f.flush();os.fsync(f.fileno())
    if target.exists():
        if neutral.checksum(target)!=digest:raise ValueError('existing native file changed')
        pending.unlink()
    else:os.replace(pending,target)
    check();os.replace(pending_meta,receipt)
    fd=os.open(directory,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    if old is not None and old['file']!=target.name:(directory/old['file']).unlink()
    return saved


def read_native(directory,*,benchmark_identity,source_provenance):
    directory=Path(directory);path=directory/'accepted.json'
    if path.is_symlink():raise ValueError('receipt alias')
    receipt=json.loads(path.read_text());signature=receipt.pop('receipt_sha256')
    if hashlib.sha256(neutral.canonical(receipt)).hexdigest()!=signature or receipt['schema']!=1:raise ValueError('receipt changed')
    filename=receipt['file']
    if filename!=receipt['sha256']+'.npz' or Path(filename).name!=filename:raise ValueError('native file name')
    path=directory/filename
    if path.is_symlink() or path.stat().st_size!=receipt['bytes'] or neutral.checksum(path)!=receipt['sha256']:raise ValueError('native file bytes changed')
    with np.load(path,allow_pickle=False) as f:arrays={n:f[n] for n in f.files}
    meta=receipt['metadata'];validate_native(meta,arrays,benchmark_identity=benchmark_identity,source_provenance=source_provenance)
    return meta,arrays
