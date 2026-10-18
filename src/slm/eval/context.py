"""Full-depth context boundary and cached-decoding reference probes."""
import argparse
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from safetensors.numpy import save_file, load_file
from slm.common.checkpoint import load
from slm.eval.portability import environment, memory_snapshot, compare


def probe(model, output, backend='mlx', device='cpu', length=None, reference=None):
    started=time.perf_counter()
    model, output=Path(model),Path(output)
    env=environment(backend,device)
    config,weights=load(model)
    length=config.max_seq_len if length is None else length
    if not 2 <= length <= config.max_seq_len: raise ValueError('Context probe length outside model window')
    positions=sorted({0,min(127,length-1),min(1023,length-1),length//2,length-1})
    tokens=np.random.default_rng(731).integers(0,config.vocab_size,(1,length),dtype=np.int64)
    identity={'architecture':config.to_dict(),'parameters':config.parameter_count,'length':length,
              'positions':positions,'tokens_sha256':hashlib.sha256(tokens.tobytes()).hexdigest(),
              'source_model_manifest_sha256':hashlib.sha256((model/'manifest.json').read_bytes()).hexdigest()}
    if backend=='torch':
        import torch
        from slm.backends import torch_backend as impl
        params=impl.load(config,weights,device)
        array=lambda x:torch.tensor(np.array(x),device=device)
        context=torch.inference_mode()
    else:
        import mlx.core as mx
        from slm.backends import mlx_backend as impl
        params=impl.load(config,weights)
        array=mx.array;context=nullcontext()
    del weights
    output.mkdir(parents=True,exist_ok=False)
    report={'passed':False,'environment':env,**identity,'cross_backend_reference':reference is not None}
    try:
        with context:
            logits,_,layers=impl.forward(params,config,array(tokens))
            if backend=='torch':
                finite=bool(torch.isfinite(logits).all()) and all(bool(torch.isfinite(v).all()) for v in layers)
            else:
                finite=bool(mx.all(mx.stack([mx.all(mx.isfinite(v)) for v in [logits,*layers]])))
            if not finite:raise FloatingPointError('Nonfinite full-context logits or layer states')
            report['all_logits_layers_finite']=True
            selected={'logits':logits[:,positions,:]}
            selected.update({f'layer:{i}':value[:,positions,:] for i,value in enumerate(layers)})
            raw=impl.export(selected)
            del logits,layers,selected
            prefix,cache,_=impl.forward(params,config,array(tokens[:,:-1]))
            prefix_positions=[p for p in positions if p<length-1]
            prior=impl.export({'logits':prefix[:,prefix_positions,:]})['logits']
            np.testing.assert_allclose(prior,raw['logits'][:,:-1],atol=1e-5,rtol=1e-4,equal_nan=False)
            del prefix,prior
            tail,_,_=impl.forward(params,config,array(tokens[:,-1:]),cache=cache)
            raw['cached_logits']=impl.export({'last':tail})['last']
            np.testing.assert_allclose(raw['cached_logits'],raw['logits'][:,-1:],atol=1e-5,rtol=1e-4,equal_nan=False)
        report['cache_max_abs_error']=float(np.abs(raw['cached_logits']-raw['logits'][:,-1:]).max())
        save_file(raw,str(output/'context-probes.safetensors'))
        report['probes_sha256']=hashlib.sha256((output/'context-probes.safetensors').read_bytes()).hexdigest()
        if reference is not None:
            reference=Path(reference)
            expected=json.loads((reference/'report.json').read_text())
            if not expected['passed'] or any(expected[k]!=v for k,v in identity.items()):
                raise ValueError('Context reference identity differs')
            if hashlib.sha256((reference/'context-probes.safetensors').read_bytes()).hexdigest()!=expected['probes_sha256']:
                raise ValueError('Context reference checksum differs')
            report['checks']=compare(raw,load_file(str(reference/'context-probes.safetensors')))
        report['passed']=True
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        report.update(seconds=time.perf_counter()-started,memory=memory_snapshot(backend,device))
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True);p.add_argument('--output',required=True)
    p.add_argument('--backend',choices=['mlx','torch'],default='mlx');p.add_argument('--device',default='cpu')
    p.add_argument('--length',type=int);p.add_argument('--reference')
    a=p.parse_args();report=probe(a.model,a.output,a.backend,a.device,a.length,a.reference)
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},indent=2))


if __name__=='__main__':main()
