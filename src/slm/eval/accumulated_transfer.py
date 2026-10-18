"""Accumulated-state fixture and finite continuation, separate from trajectory gates."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from slm.common.config import Config,initialize
from slm.common.training import Batches,Recipe,Trainer
from slm.eval.portability import environment,get_batches,memory_snapshot,validate_bundle,write_manifest


def create(destination,config,backend='mlx',device='cpu'):
    if config.max_seq_len<32:raise ValueError('Transfer fixture needs context >=32')
    root=Path(destination);root.mkdir(parents=True,exist_ok=False)
    env=environment(backend,device);rng=np.random.default_rng(841);arrays={}
    lengths=(16,32,24,8,12,20,10)
    for i,length in enumerate(lengths):
        x=rng.integers(0,config.vocab_size,(1,length),dtype=np.int64)
        y=np.roll(x,-1,axis=1);y[:,-1]=0
        mask=np.ones(x.shape,np.float32);mask[:,::3]=0
        arrays.update({f'x{i}':x,f'y{i}':y,f'mask{i}':mask})
    np.savez(root/'batches.npz',**arrays)
    (root/'fixture.json').write_text(json.dumps({'vocab_size':config.vocab_size,'batch_count':len(lengths),
        'architecture':config.to_dict(),'data_seed':841,'initialization_seed':317,'lengths':lengths,
        'scope':'Opaque synthetic token fixture, no public or teacher examples'},indent=2)+'\n')
    recipe=Recipe(lr=3e-4,warmup_tokens=128,accumulation_steps=2)
    trainer=Trainer(config,initialize(config,317),get_batches(root),backend,device,recipe)
    first=trainer.update();trainer.save(root/'initial')
    (root/'origin.json').write_text(json.dumps(env,indent=2)+'\n');write_manifest(root)
    return {'passed':True,'bundle':str(root),'bundle_hash':validate_bundle(root),'parameters':config.parameter_count,
        'environment':env,'recipe':asdict(recipe),'first_update':first,'memory':memory_snapshot(backend,device),
        'scope':'One source update and portable v2 state; no cross-backend trajectory comparison'}


def continue_(fixture,checkpoint,output,backend='torch',device='cuda',updates=2):
    if type(updates) is not int or not 1<=updates<=3:raise ValueError('Bounded positive continuation required')
    fixture,checkpoint,output=Path(fixture),Path(checkpoint),Path(output)
    if output.exists():raise FileExistsError(output)
    bundle_hash=validate_bundle(fixture);env=environment(backend,device)
    data=get_batches(fixture);trainer=Trainer.resume(checkpoint,data,backend,device)
    available=(len(data.items)-trainer.cursor+trainer.recipe.accumulation_steps-1)//trainer.recipe.accumulation_steps
    if updates>available:raise ValueError('Continuation exceeds remaining data')
    source={'step':trainer.step,'cursor':trainer.cursor,'tokens':trainer.tokens,'supervised_tokens':trainer.supervised_tokens}
    started=time.perf_counter();history=[]
    for _ in range(updates):history.append(trainer.update())
    # A finite final state is a mechanics condition, not a numerical-equivalence test.
    digest=hashlib.sha256();values=0
    for name,w in trainer.params.items():
        for slot,tensor in enumerate((w,)+trainer.moments[name]):
            a=trainer.impl.export({'value':tensor})['value']
            if not np.isfinite(a).all():raise FloatingPointError('Nonfinite continued state')
            digest.update(f'{name}/{slot}'.encode());digest.update(a.tobytes());values+=a.size
    output.mkdir(parents=True,exist_ok=False);trainer.save(output/'checkpoint')
    report={'passed':True,'fixture_bundle_sha256':bundle_hash,'parameters':trainer.config.parameter_count,
        'environment':env,'recipe':asdict(trainer.recipe),'source_counters':source,'history':history,
        'final_counters':{'step':trainer.step,'cursor':trainer.cursor,'tokens':trainer.tokens,'supervised_tokens':trainer.supervised_tokens},
        'updates_performed':updates,'all_final_values_finite':True,'values_checked':values,
        'final_state_sha256':digest.hexdigest(),'seconds':time.perf_counter()-started,'memory':memory_snapshot(backend,device),
        'scope':'Finite optimizer continuation and portable checkpoint; no independent/cross-backend trajectory acceptance or language-quality claim'}
    (output/'continuation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    new=sub.add_parser('create');new.add_argument('--config',required=True)
    next_=sub.add_parser('continue');next_.add_argument('--fixture',required=True);next_.add_argument('--checkpoint',required=True)
    next_.add_argument('--updates',type=int,default=2)
    for child in (new,next_):
        child.add_argument('--output',required=True);child.add_argument('--backend',choices=['torch','mlx'],required=True)
        child.add_argument('--device',default='cpu')
    a=p.parse_args()
    r=create(a.output,Config(**json.loads(Path(a.config).read_text())),a.backend,a.device) if a.action=='create' else continue_(a.fixture,a.checkpoint,a.output,a.backend,a.device,a.updates)
    print(json.dumps(r,indent=2))


if __name__=='__main__':main()
