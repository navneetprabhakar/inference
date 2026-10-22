"""Bind semantic checkpoints to persistent ledger history and frozen schedules.

Exports/returns arrays only; no model construction, backend loading or launch.
"""
import copy
from dataclasses import asdict
import numpy as np
from . import training_state
from .monitor import Monitor


def save(root,name,*,params,moments,backend,monitor,rng,step,targets,schedule,ledger,identity,expected):
    cursor=schedule.update_cursors[step]
    schedule.resume_position(step=step,cursor=cursor,targets=targets)
    snapshot=ledger.snapshot()
    if snapshot['updates_completed']<step or snapshot['targets_completed']<targets:
        raise ValueError('Checkpoint is ahead of completed ledger work')
    arrays={f'parameter:{k}':v for k,v in backend.export(params).items()}
    if moments:
        for ix,prefix in enumerate(('first_moment','second_moment')):
            arrays.update({f'{prefix}:{k}':v for k,v in backend.export({k:v[ix] for k,v in moments.items()}).items()})
    metadata=dict(step=step,targets=targets,data_cursor=cursor,rng=copy.deepcopy(rng.bit_generator.state),
        monitor=asdict(monitor),ledger_digest=snapshot['digest'],ledger_snapshot=snapshot,
        schedule_hash=schedule.sha256,**expected)
    return training_state.publish(root,name,arrays,metadata,identity=identity,
        shapes={k:tuple(v.shape) for k,v in params.items()},expected=expected|{'schedule_hash':schedule.sha256},
        cursor_targets=schedule.cursor_targets,update_cursors=schedule.update_cursors)


def restore(path,*,shapes,schedule,ledger,identity,expected):
    arrays,metadata=training_state.read(path,identity=identity,shapes=shapes,
        expected=expected|{'schedule_hash':schedule.sha256},cursor_targets=schedule.cursor_targets,
        update_cursors=schedule.update_cursors)
    snapshot=metadata.get('ledger_snapshot')
    if not isinstance(snapshot,dict) or metadata['ledger_digest']!=snapshot.get('digest'):
        raise ValueError('Checkpoint ledger digest missing or inconsistent')
    if snapshot.get('updates_completed',-1)<metadata['step'] or snapshot.get('targets_completed',-1)<metadata['targets']:
        raise ValueError('Checkpoint is ahead of completed ledger work')
    tail=ledger.verify_snapshot(snapshot)
    next_update=schedule.resume_position(step=metadata['step'],cursor=metadata['data_cursor'],targets=metadata['targets'])
    rng=np.random.Generator(np.random.PCG64());rng.bit_generator.state=copy.deepcopy(metadata['rng'])
    return {'arrays':arrays,'metadata':metadata,'monitor':Monitor(**copy.deepcopy(metadata['monitor'])),
            'rng':rng,'next_update':next_update,'charged_work_after_checkpoint':tail}
