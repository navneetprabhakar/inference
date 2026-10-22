"""Six optimizer-suite checks; reuse captured, budgeted toy trajectories.

Trajectory records contain step, lr, before, gradients, moments_before,
after and moments_after. All tensor values are exported numpy arrays.
"""
import math
import numpy as np
from .accumulation import TargetAccumulator
from .numerical_gradients import compare_gradients
from .numerical_forward import discrepancy
from .numerical_oracles import record
from .monitor import cosine_rate


def accumulation_cases(batches,shapes,invoke):
    errors=[];tail=[]
    batch=batches['unequal'];count=int(np.asarray(batch['loss_mask']).sum())
    if count>=8192:raise ValueError('Partial-tail fixture required')
    for backend in ('mlx','torch'):
        loss,full=invoke(backend,batch,embedding_implementation='native-gather-v1')
        if backend=='mlx':
            import mlx.core as mx
            array=lambda a:mx.array(np.asarray(a,np.float32));export=lambda a:np.array(a)
        else:
            import torch
            array=lambda a:torch.tensor(a,dtype=torch.float32);export=lambda a:a.detach().numpy()
        acc=TargetAccumulator(shapes,backend);counts=[]
        for i,mask in enumerate(batch['loss_mask']):
            n=int(sum(mask));counts.append(n)
            part={k:[batch[k][i][:n]] for k in ('inputs','targets','loss_mask','padding_mask')}
            value,g=invoke(backend,part,embedding_implementation='native-gather-v1')
            acc.add(value,{k:array(v) for k,v in g.items()},n)
        if len(set(counts))<2:raise ValueError('Unequal supervision fixture required')
        value,g=acc.finish();g={k:export(v) for k,v in g.items()}
        errors.extend([discrepancy([value],[loss]),compare_gradients(g,full,shapes)])
        tail.extend([abs(acc.targets-count),discrepancy([value],[loss]),compare_gradients(g,full,shapes)])
    return {'accumulation_optimizer:unequal_target_weighting':record(errors),
            'accumulation_optimizer:partial_tail_batch':record(tail)}


def trajectory_cases(trajectories):
    if set(trajectories)!= {'mlx','torch'}:raise ValueError('Both backend trajectories required')
    moment_errors=[];update_errors=[];decay_errors=[];clipping_seen=set();matrix_seen=vector_seen=embedding_seen=False
    for backend,rows in trajectories.items():
        if len(rows)!=8:raise ValueError('Expected exactly eight shared toy updates')
        previous=None
        for step,row in enumerate(rows,1):
            if row['step']!=step or row['lr']!=.02:raise ValueError('Changed toy trajectory recipe')
            p,g=row['before'],row['gradients'];shapes={k:np.asarray(v).shape for k,v in p.items()}
            compare_gradients(p,p,shapes);compare_gradients(g,g,shapes);compare_gradients(row['after'],row['after'],shapes)
            if set(row['moments_after'])!=set(p) or (set(row['moments_before'])!=set(p) if step>1 else bool(row['moments_before'])):
                raise ValueError('Incomplete moment state')
            if previous:
                update_errors.append(compare_gradients(previous['after'],p,shapes))
                for k in p:
                    for ix in (0,1):moment_errors.append(discrepancy(previous['moments_after'][k][ix],row['moments_before'][k][ix]))
            norm=math.sqrt(sum(float(np.square(np.asarray(v,np.float64)).sum()) for v in g.values()))
            factor=min(1.,1./(norm+1e-6))
            if norm>1:clipping_seen.add(backend)
            for k,value in p.items():
                w=np.asarray(value,np.float64);clipped=np.asarray(g[k],np.float64)*factor
                old=row['moments_before'].get(k,(np.zeros_like(w),np.zeros_like(w)))
                m=.9*np.asarray(old[0],np.float64)+.1*clipped
                v=.95*np.asarray(old[1],np.float64)+.05*clipped**2
                actual=row['moments_after'][k]
                moment_errors.extend([discrepancy(actual[0],m),discrepancy(actual[1],v)])
                adaptive=.02*(m/(1-.9**step))/(np.sqrt(v/(1-.95**step))+1e-8)
                decay=.1 if w.ndim==2 else 0.
                expected=w*(1-.02*decay)-adaptive
                update_errors.append(discrepancy(row['after'][k],expected))
                decay_errors.append(discrepancy(np.asarray(row['after'][k],np.float64)+adaptive,w*(1-.02*decay)))
                matrix_seen |= w.ndim==2;vector_seen |= w.ndim==1;embedding_seen |= k=='embedding' and w.ndim==2
            previous=row
    return {'accumulation_optimizer:clip_after_accumulation':record(moment_errors+update_errors,clipping_seen=={'mlx','torch'}),
            'accumulation_optimizer:adam_first_second_moments':record(moment_errors),
            'accumulation_optimizer:matrix_only_decay_including_embedding':record(decay_errors,matrix_seen and vector_seen and embedding_seen)}


def schedule_case():
    cap=43409847;warmup=250000;peak=.0002;minimum=.00002
    points=(0,1,125000,250000,500000,2000000,(cap+warmup)//2,cap)
    errors=[]
    for n in points:
        expected=peak*n/warmup if n<=warmup else minimum+(peak-minimum)*(1+math.cos(math.pi*(n-warmup)/(cap-warmup)))/2
        errors.append(discrepancy([cosine_rate(n,cap)],[expected]))
    valid=True
    for n in (-1,cap+1):
        try:cosine_rate(n,cap)
        except ValueError:pass
        else:valid=False
    return {'accumulation_optimizer:target_count_lr_schedule':record(errors,valid and max(errors)<=1e-15)}
