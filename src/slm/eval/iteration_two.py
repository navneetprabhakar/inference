"""Frozen source-balanced foundation/dialogue diagnostics for iteration two."""
# Creator: Navneet Prabhakar
from collections import Counter,defaultdict
from contextlib import nullcontext
import json
import numpy as np
from slm.data.schema import digest

SOURCES=('OpenAssistant/oasst2','databricks/databricks-dolly-15k')
SEED='iteration-two-validation-20261019-v1'


def select(index,bpe,per_source=32):
    if type(per_source) is not int or not 1<=per_source<=32:raise ValueError('Bounded group count required')
    train={g for g, in index.db.execute('SELECT DISTINCT gid FROM approved WHERE split="train"')};groups={}
    for data,gid in index.db.execute('SELECT data,gid FROM approved WHERE split="validation" ORDER BY eid'):
        if gid in train:raise ValueError('Validation group intersects train')
        row=json.loads(data)
        if row['source'] not in SOURCES or gid in groups:continue
        x,y,mask=bpe.serialize(row['messages'],objective='assistant')
        if not 1<=len(x)<=1024 or sum(mask)<16:continue
        groups[gid]=dict(source=row['source'],example_id=row['example_id'],group=gid,record_sha256=digest(row),
            x=x,y=y,assistant_mask=mask)
    chosen=[]
    for source in SOURCES:
        values=sorted((r for r in groups.values() if r['source']==source),key=lambda r:(digest([SEED,r['group']]),r['group']))[:per_source]
        if len(values)!=per_source:raise ValueError('Insufficient source-balanced validation groups')
        chosen.extend(values)
    return chosen


def summarize(groups,foundation,assistant):
    if not groups or len(groups)!=len(foundation) or len(groups)!=len(assistant):raise ValueError('Complete paired group losses required')
    by_source=defaultdict(lambda:defaultdict(list))
    for row,f,a in zip(groups,foundation,assistant):
        if row['source'] not in SOURCES or not np.isfinite([f,a]).all():raise ValueError('Finite source-bound NLL required')
        by_source[row['source']]['foundation'].append(float(f));by_source[row['source']]['assistant'].append(float(a))
    if set(by_source)!=set(SOURCES):raise ValueError('Both sources required')
    metrics={s:{k:float(np.mean(v)) for k,v in values.items()} for s,values in by_source.items()}
    return dict(source_balanced_foundation_nll=float(np.mean([v['foundation'] for v in metrics.values()])),
        source_balanced_assistant_nll=float(np.mean([v['assistant'] for v in metrics.values()])),
        sources=metrics,groups=dict(Counter(r['source'] for r in groups)),foundation_group_nll=list(map(float,foundation)),
        assistant_group_nll=list(map(float,assistant)))


def choose(results):
    if set(results)!={'lr-0003','lr-0010'}:raise ValueError('Both optimizer screens required')
    losses={k:v['source_balanced_foundation_nll'] for k,v in results.items()}
    if not np.isfinite(list(losses.values())).all():raise ValueError('Finite complete optimizer comparison required')
    return 'lr-0003' if losses['lr-0003']<=losses['lr-0010']+.01 else 'lr-0010'


def score(config,weights,groups,recipe,backend='mlx'):
    if backend=='mlx':
        import mlx.core as mx
        from slm.backends import mlx_backend as impl
        params=impl.load(config,weights);array=mx.array;context=nullcontext()
    elif backend=='torch':
        import torch
        from slm.backends import torch_backend as impl
        params=impl.load(config,weights,device='cpu');array=torch.tensor;context=torch.no_grad()
    else:raise ValueError('Local MLX or PyTorch CPU scoring only')
    foundation=[];assistant=[]
    with context:
        for row in groups:
            if any(type(v) is not int for k in ('x','y','assistant_mask') for v in row[k]):raise ValueError('Integer frozen tokens/masks required')
            x=np.asarray([row['x']],dtype=np.int32);y=np.asarray([row['y']],dtype=np.int32);mask=np.asarray([row['assistant_mask']],dtype=np.float32)
            if (x.shape!=y.shape or x.shape!=mask.shape or x.ndim!=2 or x.shape[0]!=1 or not 1<=x.shape[1]<=1024
                or min(x.min(),y.min())<0 or max(x.max(),y.max())>=config.vocab_size or not np.isin(mask,[0,1]).all() or mask.sum()<16):raise ValueError('Frozen validation tokens/masks differ')
            for target,loss_mask in ((foundation,np.ones_like(mask)),(assistant,mask)):
                value=float(impl.loss(params,config,array(x),array(y),array(loss_mask),
                    loss_implementation=recipe.loss_implementation,embedding_implementation=recipe.embedding_implementation))
                if not np.isfinite(value):raise ValueError('Nonfinite validation loss')
                target.append(value)
    return summarize(groups,foundation,assistant)
