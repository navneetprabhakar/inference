"""Bounded synthetic reference-trainer timing; not a pretraining-quality result."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
import numpy as np
from slm.common.config import Config,initialize
from slm.common.training import Batches,Recipe,Trainer
from slm.eval.portability import environment,memory_snapshot


def run(config,output,backend='torch',device='cuda',length=1024,warmup=2,steps=5,accumulation_steps=1):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    if not 1<=length<=config.max_seq_len or warmup<0 or steps<1:
        raise ValueError('Invalid reference benchmark workload')
    recipe=Recipe(lr=3e-4,warmup_tokens=max(1,warmup*length*accumulation_steps),eps=1e-6,accumulation_steps=accumulation_steps)
    env=environment(backend,device)
    rng=np.random.default_rng(617);items=[]
    for _ in range((warmup+steps)*recipe.accumulation_steps):
        x=rng.integers(0,config.vocab_size,(1,length),dtype=np.int64)
        y=rng.integers(0,config.vocab_size,x.shape,dtype=np.int64)
        items.append((x,y,np.ones(x.shape,dtype=np.float32)))
    data=Batches(items,config.vocab_size)
    trainer=Trainer(config,initialize(config,193),data,backend,device,recipe)
    def synchronize():
        if backend=='torch' and device.startswith('cuda'):
            import torch
            torch.cuda.synchronize(device)
        elif backend=='mlx':
            import mlx.core as mx
            mx.synchronize()
    for _ in range(warmup):trainer.update()
    synchronize()
    if backend=='torch' and device.startswith('cuda'):
        import torch
        torch.cuda.reset_peak_memory_stats(device)
    started=time.perf_counter();history=[]
    for _ in range(steps):history.append(trainer.update())
    synchronize();seconds=time.perf_counter()-started
    report={'passed':True,'synthetic_only':True,'parameters':config.parameter_count,
        'environment':env,'recipe':asdict(recipe),'batch_size':1,'sequence_length':length,
        'warmup_updates':warmup,'measured_updates':steps,'measured_token_positions':steps*length*accumulation_steps,
        'microbatches_per_update':accumulation_steps,'effective_positions_per_update':length*accumulation_steps,
        'measured_seconds':seconds,'token_positions_per_second':steps*length*accumulation_steps/seconds,
        'history':history,'memory':memory_snapshot(backend,device),'dataset_hash':data.fingerprint,
        'scope':'Unfused FP32 reference trainer with host gradient checks; synthetic data, no quality or production-cost guarantee.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:stream.write(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--backend',choices=['torch','mlx'],default='torch');p.add_argument('--device',default='cuda')
    p.add_argument('--length',type=int,default=1024);p.add_argument('--warmup',type=int,default=2);p.add_argument('--steps',type=int,default=5)
    p.add_argument('--accumulation-steps',type=int,default=1)
    a=p.parse_args();r=run(Config(**json.loads(Path(a.config).read_text())),a.output,a.backend,a.device,a.length,a.warmup,a.steps,a.accumulation_steps)
    print(json.dumps(r,indent=2))


if __name__=='__main__':main()
