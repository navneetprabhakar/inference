"""Semantic validation for a future scoped trainer's checkpoint.

This validates supplied arrays only. It neither initializes nor loads a model,
opens the training boundary, nor proves that a ledger/cursor matches the data.
"""
from dataclasses import asdict
from .monitor import Monitor
import copy
import math
import numpy as np


def validate(arrays, state, *, shapes, expected, cursor_targets, update_cursors):
    """cursor_targets is the frozen schedule's cumulative target count by cursor.

    Caller must independently bind this schedule and expected hashes to the run.
    Optimizer state is mandatory after step zero and forbidden at step zero.
    RNG is explicitly NumPy PCG64; no dropout or backend random sampling is allowed
    in a future training forward pass unless that RNG is separately captured.
    """
    required={'step','targets','data_cursor','rng','monitor','ledger_digest',
              'tokenizer_hash','code_hash','config_hash'}
    if not isinstance(state,dict) or not required<=state.keys():
        raise ValueError('Missing training metadata')
    if (not {'tokenizer_hash','code_hash','config_hash'}<=expected.keys()
            or any(state.get(k)!=v for k,v in expected.items())):
        raise ValueError('Unbound or changed training contract')
    for key in ('step','targets','data_cursor'):
        if type(state[key]) is not int or state[key]<0:
            raise ValueError('Invalid training counters')
    if (not cursor_targets or cursor_targets[0]!=0
            or any(type(x) is not int or x<0 for x in cursor_targets)
            or any(b<=a for a,b in zip(cursor_targets,cursor_targets[1:]))):
        raise ValueError('Invalid frozen target schedule')
    cursor=state['data_cursor']
    if cursor>=len(cursor_targets) or state['targets']!=cursor_targets[cursor]:
        raise ValueError('Cursor/target mismatch')
    if (not update_cursors or update_cursors[0]!=0
            or any(type(x) is not int or not 0<=x<len(cursor_targets) for x in update_cursors)
            or any(b<=a for a,b in zip(update_cursors,update_cursors[1:]))):
        raise ValueError('Invalid frozen update boundaries')
    if state['step']>=len(update_cursors) or update_cursors[state['step']]!=cursor:
        raise ValueError('Optimizer step inconsistent with frozen update boundary')
    if not shapes or any(not isinstance(k,str) or not k or ':' in k
            or not v or any(type(d) is not int or d<1 for d in v)
            for k,v in shapes.items()):
        raise ValueError('Invalid bound parameter shapes')
    prefixes=('parameter',) if state['step']==0 else ('parameter','first_moment','second_moment')
    keys={f'{prefix}:{name}' for prefix in prefixes for name in shapes}
    if set(arrays)!=keys:
        raise ValueError('Missing or extra parameter/optimizer buffers')
    for key,a in arrays.items():
        name=key.split(':',1)[1]
        if (not isinstance(a,np.ndarray) or a.dtype!=np.float32
                or a.shape!=tuple(shapes[name]) or not np.isfinite(a).all()):
            raise ValueError('Invalid parameter/optimizer array')
        if key.startswith('second_moment:') and np.any(a<0):
            raise ValueError('Negative optimizer second moment')
    rng=state['rng']
    if not isinstance(rng,dict) or rng.get('bit_generator')!='PCG64':
        raise ValueError('Missing exact PCG64 state; a seed is insufficient')
    try:
        restored=np.random.PCG64()
        restored.state=copy.deepcopy(rng)
        if restored.state!=rng:raise ValueError('RNG state changed on restore')
    except (TypeError,ValueError,KeyError,OverflowError) as exc:
        raise ValueError('Invalid PCG64 state') from exc
    monitor=state['monitor'];defaults=asdict(Monitor())
    if not isinstance(monitor,dict) or set(monitor)!=set(defaults) or monitor['terminal'] is not None:
        raise ValueError('Missing or terminal quality monitor')
    for key,default in defaults.items():
        value=monitor[key]
        if isinstance(default,list) and not isinstance(value,list):
            raise ValueError('Invalid monitor history')
        if type(default) is int and (type(value) is not int or value<0):
            raise ValueError('Invalid monitor counter')
    if len(monitor['losses'])!=state['step'] or len(monitor['gradients'])!=state['step']:
        raise ValueError('Monitor update history inconsistent with optimizer step')
    def check_json(value):
        if value is None or type(value) in (bool,str,int):return
        if type(value) is float and math.isfinite(value):return
        if isinstance(value,list):
            for item in value:check_json(item)
            return
        if isinstance(value,dict) and all(isinstance(k,str) for k in value):
            for item in value.values():check_json(item)
            return
        raise ValueError('Nonfinite or nonserializable metadata')
    check_json(state)
    return restored


def publish(root,name,arrays,state,*,identity,shapes,expected,cursor_targets,update_cursors,storage_cap=4*1024**3):
    from . import state as storage
    validate(arrays,state,shapes=shapes,expected=expected,cursor_targets=cursor_targets,update_cursors=update_cursors)
    return storage.publish(root,name,arrays,state,identity=identity,storage_cap=storage_cap)


def read(path,*,identity,shapes,expected,cursor_targets,update_cursors):
    from . import state as storage
    arrays,state=storage.read(path,identity=identity,expected=expected)
    validate(arrays,state,shapes=shapes,expected=expected,cursor_targets=cursor_targets,update_cursors=update_cursors)
    return arrays,state
