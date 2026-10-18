"""Exact full training-state import/export audit, separate from trajectory comparisons."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from safetensors.numpy import load_file
from slm.common.checkpoint import load
from slm.common.training import Trainer
from slm.eval.portability import environment,memory_snapshot,get_batches


def audit(checkpoint,fixture,output,backend='mlx',device='cpu'):
    checkpoint,output=Path(checkpoint),Path(output)
    if output.exists():raise FileExistsError(output)
    started=time.perf_counter();env=environment(backend,device)
    batches=get_batches(fixture)
    trainer=Trainer.resume(checkpoint,batches,backend,device)
    config,weights=load(checkpoint/'model')
    expected={f'weight:{k}':v for k,v in weights.items()}
    moments=load_file(str(checkpoint/'optimizer.safetensors'))
    expected.update(moments)
    tensors={f'weight:{k}':v for k,v in trainer.params.items()}
    tensors.update({f'{slot}:{k}':v[i] for k,v in trainer.moments.items() for i,slot in enumerate(('m','v'))})
    actual=trainer.impl.export(tensors)
    if actual.keys()!=expected.keys():raise ValueError('State tensor set differs')
    original,imported=hashlib.sha256(),hashlib.sha256()
    for name in sorted(expected):
        a,e=actual[name],expected[name]
        if a.shape!=e.shape or a.dtype!=e.dtype:raise ValueError('State shape/dtype differs')
        header=str((name,e.shape,e.dtype.str)).encode()
        original.update(header);imported.update(header)
        original.update(e.tobytes(order='C'));imported.update(a.tobytes(order='C'))
    if original.hexdigest()!=imported.hexdigest():raise AssertionError('State values differ after import/export')
    state=json.loads((checkpoint/'state.json').read_text())
    counters={'step':trainer.step,'cursor':trainer.cursor,'tokens':trainer.tokens,'supervised_tokens':trainer.supervised_tokens}
    if any(counters[k]!=state[k] for k in counters) or asdict(trainer.recipe)!=state['recipe']:
        raise ValueError('Training counters or recipe changed')
    report={'passed':True,'scope':'Exact state import/export; no optimizer update or trajectory equivalence claim',
            'parameters':config.parameter_count,'tensors_checked':len(expected),'values_checked':sum(v.size for v in expected.values()),
            'source_content_sha256':original.hexdigest(),'imported_content_sha256':imported.hexdigest(),
            'updates_performed':0,'counters':counters,'recipe':asdict(trainer.recipe),'environment':env,
            'seconds':time.perf_counter()-started,'memory':memory_snapshot(backend,device)}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:stream.write(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',required=True);p.add_argument('--fixture',required=True);p.add_argument('--output',required=True)
    p.add_argument('--backend',choices=['mlx','torch'],default='mlx');p.add_argument('--device',default='cpu')
    a=p.parse_args();print(json.dumps(audit(a.checkpoint,a.fixture,a.output,a.backend,a.device),indent=2))


if __name__=='__main__':main()
