"""Bounded synthetic accumulation/resume mechanics; no language or trajectory gate."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import time
import numpy as np
from slm.common.config import Config,initialize
from slm.common.training import Batches,Recipe,Trainer
from slm.eval.portability import environment,memory_snapshot


def exact_state(a,b):
    for name in ('step','cursor','tokens','supervised_tokens'):
        if getattr(a,name)!=getattr(b,name):raise AssertionError('Resume counters differ')
    digest=hashlib.sha256();values=0
    for name in a.params:
        left=(a.params[name],)+a.moments[name];right=(b.params[name],)+b.moments[name]
        for slot,(x,y) in enumerate(zip(left,right)):
            x=a.impl.export({'value':x})['value'];y=b.impl.export({'value':y})['value']
            if not np.isfinite(x).all() or not np.array_equal(x,y):raise AssertionError(f'Own resumed state differs: {name}/{slot}')
            digest.update(f'{name}/{slot}'.encode());digest.update(x.tobytes());values+=x.size
    return {'exact':True,'values_checked':values,'canonical_state_sha256':digest.hexdigest(),
        'step':a.step,'cursor':a.cursor,'processed_tokens':a.tokens,'supervised_tokens':a.supervised_tokens}


def run(config,output,backend='mlx',device='cpu',embedding_implementation='native-gather-v1'):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    if config.max_seq_len<32:raise ValueError('Mechanics fixture requires context at least 32')
    env=environment(backend,device);rng=np.random.default_rng(841);items=[]
    for length in (16,32,24,8,12):
        x=rng.integers(0,config.vocab_size,(1,length),dtype=np.int64)
        y=np.roll(x,-1,axis=1);y[:,-1]=0
        mask=np.ones(x.shape,np.float32);mask[:,::3]=0
        items.append((x,y,mask))
    data=Batches(items,config.vocab_size)
    recipe=Recipe(lr=3e-4,warmup_tokens=128,accumulation_steps=2,embedding_implementation=embedding_implementation)
    def sync():
        if backend=='mlx':
            import mlx.core as mx
            mx.synchronize()
        elif device.startswith('cuda'):
            import torch
            torch.cuda.synchronize(device)
    started=time.perf_counter();a=Trainer(config,initialize(config,317),data,backend,device,recipe)
    sync();initialize_seconds=time.perf_counter()-started
    started=time.perf_counter();initial=a.update();sync();first_seconds=time.perf_counter()-started
    checks=[];history=[]
    with tempfile.TemporaryDirectory(prefix='slm-accumulation-check-') as temp:
        checkpoint=Path(temp)/'step1';started=time.perf_counter();a.save(checkpoint)
        save_seconds=time.perf_counter()-started;checkpoint_bytes=sum(p.stat().st_size for p in checkpoint.rglob('*') if p.is_file())
        manifest_sha256=hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest()
        started=time.perf_counter();b=Trainer.resume(checkpoint,data,backend,device)
        sync();load_seconds=time.perf_counter()-started
        checks.append(exact_state(a,b))
        while a.cursor<len(data.items):
            started=time.perf_counter();left=a.update();sync();left_seconds=time.perf_counter()-started
            started=time.perf_counter();right=b.update();sync();right_seconds=time.perf_counter()-started
            if left!=right:raise AssertionError('Own resume metrics differ')
            history.append({'metrics':left,'uninterrupted_seconds':left_seconds,'resumed_seconds':right_seconds})
            checks.append(exact_state(a,b))
    report={'passed':True,'synthetic_only':True,'architecture':config.to_dict(),'parameters':config.parameter_count,
        'environment':env,'recipe':asdict(recipe),'initialization_seed':317,'data_seed':841,
        'dataset_hash':data.fingerprint,'microbatch_lengths':[16,32,24,8,12],
        'microbatch_supervised_counts':[int(m.sum()) for _,_,m in items],
        'reference_optimizer_updates':a.step,'reference_consumed_microbatches':a.cursor,
        'reference_processed_positions':a.tokens,'reference_supervised_positions':a.supervised_tokens,
        'total_executed_updates':a.step+(b.step-1),'total_executed_positions':a.tokens+(b.tokens-initial['tokens']),
        'initialize_seconds':initialize_seconds,'first_update_seconds':first_seconds,'first_update':initial,
        'checkpoint_save_seconds':save_seconds,'checkpoint_load_seconds':load_seconds,
        'checkpoint_bytes':checkpoint_bytes,'checkpoint_manifest_sha256':manifest_sha256,'temporary_checkpoint_removed':True,
        'history':history,'own_trajectory_checks':checks,'memory':memory_snapshot(backend,device),
        'scope':'Three logical optimizer updates on opaque synthetic IDs; two simultaneous trainer states for exact own-resume checks. Short contexts only, not sustained throughput, language training, independent/cross-backend trajectory acceptance or production single-trainer memory.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:stream.write(json.dumps(report,indent=2)+'\n')
    return report


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--backend',choices=['torch','mlx'],default='mlx');p.add_argument('--device',default='cpu')
    p.add_argument('--embedding-implementation',choices=['native-gather-v1','dense-onehot-v1'],default='native-gather-v1')
    a=p.parse_args();r=run(Config(**json.loads(Path(a.config).read_text())),a.output,a.backend,a.device,a.embedding_implementation)
    print(json.dumps({k:r[k] for k in ('passed','parameters','reference_optimizer_updates','reference_processed_positions','memory')},indent=2))


if __name__=='__main__':main()
