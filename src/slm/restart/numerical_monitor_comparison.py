"""Approved v2: compare replay metadata without executing any model.

Only post-replay loss/gradient history floats receive absolute tolerance 1e-5.
Published checkpoint roundtrip and every discrete semantic field remain exact.
"""
import math


def exact(left,right):
    if type(left) is not type(right):return False
    if isinstance(left,dict):return left.keys()==right.keys() and all(exact(left[k],right[k]) for k in left)
    if isinstance(left,(list,tuple)):return len(left)==len(right) and all(exact(a,b) for a,b in zip(left,right))
    if isinstance(left,float) and (not math.isfinite(left) or not math.isfinite(right)):return False
    return left==right


def compare(left,right):
    fields={'step','targets','data_cursor','rng','monitor','tokenizer_hash','code_hash','config_hash','schedule_hash'}
    if not fields.issubset(left) or not fields.issubset(right):raise ValueError('Missing semantic state')
    discrete=all(exact(left[k],right[k]) for k in fields-{'monitor'})
    a,b=left['monitor'],right['monitor']
    if not isinstance(a,dict) or not isinstance(b,dict) or a.keys()!=b.keys() or not {'losses','gradients'}.issubset(a):
        raise ValueError('Missing monitor state')
    discrete &= all(exact(a[k],b[k]) for k in a.keys()-{'losses','gradients'})
    errors=[]
    for key in ('losses','gradients'):
        x,y=a[key],b[key]
        if not isinstance(x,list) or not isinstance(y,list) or len(x)!=len(y):raise ValueError('Changed monitor history length')
        for i,(u,v) in enumerate(zip(x,y)):
            if any(type(n) not in (int,float) or not math.isfinite(n) for n in (u,v)):raise ValueError('Nonfinite/non-numeric monitor history')
            errors.append({'field':key,'index':i,'absolute_error':abs(u-v)})
    maximum=max((r['absolute_error'] for r in errors),default=0.)
    return {'passed':bool(discrete and maximum<=1e-5),'discrete_state_exact':bool(discrete),
            'maximum_absolute_error':maximum,'absolute_tolerance':1e-5,'relative_tolerance':0,
            'nonzero_differences':[r for r in errors if r['absolute_error']>0]}
