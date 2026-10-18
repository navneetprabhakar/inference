"""Synthetic fixed-batch learning smoke check; not language/capability evaluation."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
import numpy as np
from slm.common.config import Config,initialize
from slm.common.training import Batches,Recipe,Trainer
from slm.eval.portability import environment,memory_snapshot


def run(config,output,backend='mlx',device='cpu',updates=100,recipe=None):
    if updates<1 or config.max_seq_len<4:raise ValueError('Positive updates and context >=4 required')
    env=environment(backend,device)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    recipe=recipe or Recipe(eps=1e-6)
    rng=np.random.default_rng(53)
    length=min(12,config.max_seq_len)
    x=rng.integers(0,config.vocab_size,(2,length),dtype=np.int64)
    y=np.roll(x,-1,axis=1);y[:,-1]=0
    mask=np.ones(x.shape,dtype=np.float32);mask[:,:3]=0
    microbatches=updates*recipe.accumulation_steps
    batches=Batches([(x,y,mask)]*microbatches,config.vocab_size)
    np.savez(output/'batches.npz',**{f'{name}{i}':value for i in range(microbatches)
              for name,value in (('x',x),('y',y),('mask',mask))})
    (output/'fixture.json').write_text(json.dumps({'vocab_size':config.vocab_size,'batch_count':microbatches,'optimizer_updates':updates,
        'architecture':config.to_dict(),'seed':53,'initialization_seed':311,'repeated_batch':True},indent=2)+'\n')
    trainer=Trainer(config,initialize(config,311),batches,backend,device,recipe)
    def measure():
        value=trainer.impl.loss(trainer.params,config,trainer.array(x),trainer.array(y),trainer.array(mask),
                                loss_implementation=recipe.loss_implementation)
        scalar=float(value.detach()) if backend=='torch' else float(value)
        logits=trainer.impl.export({'logits':trainer.impl.forward(trainer.params,config,trainer.array(x))[0]})['logits']
        if not np.isfinite(scalar) or not np.isfinite(logits).all():raise FloatingPointError('Nonfinite overfit probe')
        return scalar,float(((logits.argmax(-1)==y)*mask).sum()/mask.sum())
    initial_loss,initial_accuracy=measure()
    report={'passed':False,'parameters':config.parameter_count,'architecture':config.to_dict(),
            'environment':env,'recipe':asdict(recipe),'synthetic_only':True,'batch_seed':53,'initialization_seed':311,
            'dataset_hash':batches.fingerprint,'updates':updates,'initial_loss':initial_loss,
            'initial_supervised_accuracy':initial_accuracy,'history':[],
            'scope':'Repeated opaque token IDs, not English training; trainer includes host gradient validation.'}
    started=time.perf_counter()
    try:
        for _ in range(updates):report['history'].append(trainer.update())
        if backend=='torch' and device.startswith('cuda'):
            import torch
            torch.cuda.synchronize(device)
        report['update_loop_seconds']=time.perf_counter()-started
        final_loss,accuracy=measure()
        report.update(final_loss=final_loss,final_supervised_accuracy=accuracy,
            processed_tokens=trainer.tokens,supervised_tokens=trainer.supervised_tokens,
            unique_batch_positions=x.size,repeated_exposures=microbatches)
        trainer.save(output/'checkpoint')
        report['passed']=final_loss<initial_loss*.25 and accuracy>=.95
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        report['memory']=memory_snapshot(backend,device)
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--backend',choices=['mlx','torch'],default='mlx');p.add_argument('--device',default='cpu')
    p.add_argument('--updates',type=int,default=100)
    p.add_argument('--recipe',help='Explicit training recipe, including loss version')
    a=p.parse_args();recipe=Recipe(**json.loads(Path(a.recipe).read_text())) if a.recipe else None
    report=run(Config(**json.loads(Path(a.config).read_text())),a.output,a.backend,a.device,a.updates,recipe)
    print(json.dumps({k:v for k,v in report.items() if k!='history'},indent=2))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
