"""Scheduled update transaction. Caller owns scoped authorization and checkpointing.

This module does not initialize/load a model or bypass the legacy entrypoint guard.
Failed computation leaves its reservation charged and makes this monitor terminal.
"""
import copy
import math
import numpy as np
from .accumulation import TargetAccumulator


def execute(update, *, store, ledger, monitor, params, moments, backend, backend_name,
            config, reservation_id, now, pilot_barrier, evaluation_barrier):
    monitor.alive()
    evaluation_barrier.require_update(update)
    evaluation_barrier.require_monitor(monitor)
    pilot_barrier.require_update(start_targets=update.cumulative_targets-update.targets,
                                 end_targets=update.cumulative_targets)
    spans=[span for micro in update.microbatches for span in micro]
    if sum(last-first for _,first,last in spans)!=update.targets:
        raise ValueError('Schedule target mismatch')
    # No data reconstruction, gradient computation or optimizer before reservation.
    ledger.reserve(reservation_id,spans,now=now)
    proposed_monitor=copy.deepcopy(monitor)
    try:
        acc=TargetAccumulator({k:tuple(v.shape) for k,v in params.items()},backend_name)
        for micro in update.microbatches:
            x,y,mask,padding,identities=store.microbatch(micro)
            count=int(mask.sum())
            if (identities!=list(micro) or count!=sum(b-a for _,a,b in micro)
                    or not np.array_equal(padding,mask>0)):
                raise ValueError('Reader supervision differs from reservation')
            if backend_name=='mlx':
                import mlx.core as mx
                arrays=[mx.array(v) for v in (x,y,mask,padding)]
            elif backend_name=='torch':
                import torch
                arrays=[torch.as_tensor(v) for v in (x,y,mask,padding)]
            else:raise ValueError('Unsupported execution backend')
            value,gradient=backend.value_and_grad(params,config,*arrays[:3],padding_mask=arrays[3],
                loss_implementation=backend.STABLE_LOSS_IMPLEMENTATION)
            if hasattr(value,'detach'):value=value.detach()
            acc.add(value,gradient,count)
        if acc.targets!=update.targets:raise ValueError('Accumulated target mismatch')
        loss,gradient=acc.finish()
        gradients=backend.export(gradient)
        norm=math.sqrt(sum(float(np.square(v.astype(np.float64)).sum()) for v in gradients.values()))
        proposed,proposed_moments=backend.adamw(params,gradient,moments,update.step,update.lr,
            beta1=.9,beta2=.95,eps=1e-8,decay=.1,clip=1.)
        before=backend.export(params);after=backend.export(proposed)
        if set(after)!=set(before) or set(proposed_moments)!=set(before):raise ValueError('Optimizer inventory changed')
        first=backend.export({k:v[0] for k,v in proposed_moments.items()})
        second=backend.export({k:v[1] for k,v in proposed_moments.items()})
        for collection in (after,first,second):
            for key,value in collection.items():
                if (value.shape!=before[key].shape or value.dtype!=np.float32 or not np.isfinite(value).all()):
                    raise ValueError('Invalid proposed optimizer state')
        if any(np.any(v<0) for v in second.values()):raise ValueError('Negative second moment')
        delta=sum(float(np.square(after[k].astype(np.float64)-before[k]).sum()) for k in before)
        scale=sum(float(np.square(v.astype(np.float64)).sum()) for v in before.values())
        ratio=math.sqrt(delta)/max(math.sqrt(scale),1e-12)
        proposed_monitor.update(loss=loss,gradient_norm=norm,update_ratio=ratio,
                                targets=update.cumulative_targets,all_state_finite=True)
        ledger.complete(reservation_id)
        evaluation_barrier.completed_update(update)
    except BaseException as error:
        monitor.terminal='scheduled update failed: '+type(error).__name__+': '+str(error)
        raise
    # Caller installs all returned state together; a crash here still retains charges.
    return {'params':proposed,'moments':proposed_moments,'monitor':proposed_monitor,
            'step':update.step,'targets':update.cumulative_targets,
            'metrics':{'loss':loss,'gradient_norm':norm,'update_ratio':ratio,
                       'microbatches':acc.microbatches,'supervised_targets':acc.targets}}
