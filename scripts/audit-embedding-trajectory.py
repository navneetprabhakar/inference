#!/usr/bin/env python3
# Creator: Navneet Prabhakar
"""Retain negative repeated-ID trajectory gates alongside the original golden control."""
import argparse
from pathlib import Path
import json
import numpy as np
from slm.common.config import Config,initialize
from slm.common.training import Batches,Trainer,Recipe
from slm.backends import mlx_backend as mb,torch_backend as tb
from slm.data.tokenized import sha


def run(output):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    c=Config();rng=np.random.default_rng(8)
    golden=(rng.integers(0,64,(2,12),dtype=np.int32),rng.integers(0,64,(2,12),dtype=np.int32),rng.integers(0,2,(2,12)).astype(np.float32))
    x=np.tile(np.array([[1,2,1,3,2,1,1,2]],np.int64),(2,1));stress=(x,np.roll(x,-1,axis=1),np.ones(x.shape,np.float32))
    controls={}
    for implementation in ('native-gather-v1','dense-onehot-v1'):
        for name,fixture,warmup in [('golden',golden,0),('repeated',stress,100)]:
            data=Batches([fixture]*100,64);recipe=Recipe(embedding_implementation=implementation,warmup_tokens=warmup)
            a=Trainer(c,initialize(c),data,'mlx',recipe=recipe);b=Trainer(c,initialize(c),data,recipe=recipe)
            first=None;peaks={'weight':0.,'m':0.,'v':0.}
            for step in range(1,101):
                a.update();b.update()
                pairs=[('weight',a.params,b.params,1e-5)]
                pairs.extend((label,{k:v[i] for k,v in a.moments.items()},{k:v[i] for k,v in b.moments.items()},1e-6) for i,label in enumerate(('m','v')))
                for group,aa,bb,atol in pairs:
                    aa=mb.export(aa);bb=tb.export(bb)
                    for k in aa:
                        delta=np.abs(aa[k]-bb[k]);peaks[group]=max(peaks[group],float(delta.max()))
                        violations=int((delta>atol+1e-4*np.abs(bb[k])).sum())
                        if violations and first is None:first={'step':step,'group':group,'tensor':k,'max_abs_delta':float(delta.max()),'violations':violations,'atol':atol,'rtol':1e-4}
            controls[implementation+'-'+name]={'passed':first is None,'first_failure':first,'maximum_abs_error':peaks,'updates':100,'warmup_tokens':warmup}
    report={'controls':controls,'tolerances_changed':False,'backend_sha256':{'mlx':sha(mb.__file__),'torch':sha(tb.__file__)},
        'stress_gate_accepted':all(v['passed'] for k,v in controls.items() if k.endswith('repeated')),
        'scope':'Existing golden fixture plus additional repeated-ID stress. Failed gates remain failed; dense mode is opt-in and is not a production selection.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args();r=run(a.output)
    print(json.dumps(r,indent=2))
    if not r['stress_gate_accepted']:raise SystemExit(1)
