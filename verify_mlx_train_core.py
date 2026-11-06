"""Frozen CPU-only compiled-core check; never executes a GPU or full model."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parent
REPORT=ROOT/'reports/mlx-own-base-compiled-core'


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def protocol(path):
    spec=json.loads(path.read_text())
    for name,h in spec['code_sha256'].items():
        if sha(ROOT/name)!=h:raise ValueError('frozen code changed: '+name)
    for seed,h in spec['fixture_sha256'].items():
        if sha(ROOT/f'reports/mlx-own-base-feasibility/torch-seed-{seed}.npz')!=h:
            raise ValueError('frozen random fixture changed')
    return spec


def save(path, meta, arrays):
    np.savez(path,**arrays)
    path.with_suffix('.json').write_text(json.dumps(dict(metadata=meta,sha256=sha(path)),indent=2)+'\n')


def load(path):
    receipt=json.loads(path.with_suffix('.json').read_text())
    if receipt['sha256']!=sha(path):raise ValueError('checkpoint checksum changed')
    with np.load(path,allow_pickle=False) as f:arrays={n:f[n] for n in f.files}
    return receipt['metadata'],arrays


def initial(seed):
    with np.load(ROOT/f'reports/mlx-own-base-feasibility/torch-seed-{seed}.npz',allow_pickle=False) as f:
        return {n:f[n] for n in f.files}


def batches(seed,spec):
    result=np.random.default_rng(seed+17).integers(spec['config']['vocabulary'],size=(spec['steps'],3,13),dtype=np.int32)
    result[:,:,3]=result[:,:,1]
    return result


def difference(a,b):return max(float(np.max(np.abs(a[n].astype('float64')-b[n].astype('float64')))) for n in a)


def worker(spec, out, resume=None):
    import mlx.core as mx
    mx.set_default_device(mx.cpu)
    import mlx_train_core as core
    cfg=core.Config(**spec['config'])
    assert core.parameter_count(cfg)<100_000
    assert mx.default_device()==mx.cpu
    if resume is not None:
        seed,beta=resume;key=f'{seed}-{beta}'
        meta,arrays=load(out/f'paused-{key}.npz')
        params={n.removeprefix('weight::'):v for n,v in arrays.items() if n.startswith('weight::')}
        trained=core.TrainCore(params,cfg,device=mx.cpu,betas=(.9,beta),compiled=True,restored=(meta,arrays))
        data=batches(seed,spec);trace=[]
        for step in range(meta['cursor']['step'],spec['steps']):
            sequence=mx.array(data[step]);loss,norm=trained.step([sequence[:1],sequence[1:]],learning_rate=spec['learning_rates'][step])
            trace.append(dict(step=step+1,loss=loss,norm=norm))
        final_meta,final=trained.snapshot();expected_meta,expected=load(out/f'final-{key}.npz')
        expected_trace=json.loads((out/f'trace-{key}.json').read_text())[spec['pause_step']:]
        result=dict(exact_arrays=all(np.array_equal(final[n],expected[n]) for n in final),
                    exact_metadata=final_meta==expected_meta,exact_trace=trace==expected_trace,
                    arrays=len(final),fresh_process=True,cursor=final_meta['cursor'])
        result['passed']=result['exact_arrays'] and result['exact_metadata'] and result['exact_trace']
        (out/f'resume-{key}.json').write_text(json.dumps(result,indent=2)+'\n')
        return result['passed']
    result=dict(device='cpu',gpu_operations=False,full_model_allocated=False,state='running',cases=[],
                note='FP32 only; CPU timings include explicit evaluation and are not Metal throughput estimates')
    start=time.monotonic()
    for seed in spec['seeds']:
        ref=initial(seed);params={n.removeprefix('initial::'):v for n,v in ref.items() if n.startswith('initial::')}
        sequence=mx.array(ref['sequence'].astype('int32'))
        # Independent fixed Torch reference at the original beta2=.95.
        first=core.TrainCore(params,cfg,device=mx.cpu,compiled=True,learning_rate=spec['reference_learning_rate'])
        logits=core.forward(first.params,sequence[:,:-1],cfg,device=mx.cpu)
        _,grad=core.accumulated_gradients(first.params,[sequence[:1],sequence[1:]],cfg,device=mx.cpu)
        mx.eval(logits,grad)
        loss,norm=first.step([sequence[:1],sequence[1:]],learning_rate=spec['reference_learning_rate'])
        _,state=first.snapshot()
        torch_stats=dict(logits=float(np.max(np.abs(np.array(logits)-ref['logits']))),loss=abs(loss-float(ref['loss'])),
                         gradients=max(float(np.max(np.abs(np.array(g)-ref['gradient::'+n]))) for n,g in grad.items()),
                         weights=max(float(np.max(np.abs(state['weight::'+n]-ref['updated::'+n]))) for n in params))
        assert all(torch_stats[n]<=spec['torch_tolerances'][n] for n in torch_stats),torch_stats
        for beta in spec['beta2_values']:
            key=f'{seed}-{beta}'
            compiled=core.TrainCore(params,cfg,device=mx.cpu,betas=(.9,beta),compiled=True)
            eager=core.TrainCore(params,cfg,device=mx.cpu,betas=(.9,beta),compiled=False)
            data=batches(seed,spec);updates=[];traces=[]
            for step in range(spec['steps']):
                sequence=mx.array(data[step]);micro=[sequence[:1],sequence[1:]]
                if step==0:
                    _,split=core.accumulated_gradients(compiled.params,micro,cfg,device=mx.cpu)
                    _,whole=mx.value_and_grad(lambda p:core.causal_loss(p,sequence,cfg,device=mx.cpu))(compiled.params)
                    mx.eval(split,whole)
                    accumulation=max(float(np.max(np.abs(np.array(split[n])-np.array(whole[n])))) for n in split)
                    assert accumulation<=spec['accumulation_tolerance']
                tick=time.monotonic();cl,cn=compiled.step(micro,learning_rate=spec['learning_rates'][step]);compiled_time=time.monotonic()-tick
                tick=time.monotonic();el,en=eager.step(micro,learning_rate=spec['learning_rates'][step]);eager_time=time.monotonic()-tick
                cm,ca=compiled.snapshot();em,ea=eager.snapshot()
                assert all(a.dtype==np.float32 for n,a in ca.items() if n.startswith(('weight::','m::','v::')))
                errors={kind:difference({n:a for n,a in ca.items() if n.startswith(kind+'::')},
                                        {n:a for n,a in ea.items() if n.startswith(kind+'::')}) for kind in ('weight','m','v')}
                errors.update(loss=abs(cl-el),norm=abs(cn-en))
                assert all(errors[n]<=spec['compiled_tolerances'][n] for n in errors),errors
                assert cm==em
                updates.append(dict(step=step+1,errors=errors,compiled_cpu_seconds=compiled_time,eager_cpu_seconds=eager_time))
                traces.append(dict(step=step+1,loss=cl,norm=cn))
                if step+1==spec['pause_step']:save(out/f'paused-{key}.npz',cm,ca)
            save(out/f'final-{key}.npz',cm,ca)
            (out/f'trace-{key}.json').write_text(json.dumps(traces,indent=2)+'\n')
            proc=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--protocol',str(out.parent/'protocol.json'),
                                 '--resume',str(seed),str(beta)],cwd=ROOT,timeout=60)
            resumed=json.loads((out/f'resume-{key}.json').read_text())
            assert proc.returncode==0 and resumed['passed']
            # Hyperparameter mismatch and missing moments must fail before work.
            pm,pa=load(out/f'paused-{key}.npz');pp={n.removeprefix('weight::'):v for n,v in pa.items() if n.startswith('weight::')}
            refusals=0
            for changed,betas in [(dict(pa),(.8,beta)),({n:a for n,a in pa.items() if n!='m::tokens.weight'},(.9,beta))]:
                try:core.TrainCore(pp,cfg,device=mx.cpu,betas=betas,restored=(pm,changed))
                except ValueError:refusals+=1
            assert refusals==2
            result['cases'].append(dict(seed=seed,beta2=beta,parameters=core.parameter_count(cfg),torch_reference=torch_stats,
                                       accumulation_error=accumulation,updates=updates,resume=resumed,refusal_checks=refusals,passed=True))
    result.update(state='passed',elapsed_cpu_seconds=time.monotonic()-start,peak_process_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(state=result['state'],cases=len(result['cases']),steps=spec['steps'],elapsed_cpu_seconds=result['elapsed_cpu_seconds'])))
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,default=REPORT/'protocol.json')
    parser.add_argument('--resume',nargs=2)
    args=parser.parse_args();spec=protocol(args.protocol)
    out=args.protocol.parent/'execution'
    if args.resume is None:
        out.mkdir(exist_ok=False)
    try:passed=worker(spec,out,(int(args.resume[0]),float(args.resume[1])) if args.resume else None)
    except BaseException as error:
        if args.resume is None:(out/'error.json').write_text(json.dumps(dict(error=f'{type(error).__name__}: {error}',gpu_operations=False),indent=2)+'\n')
        raise
    raise SystemExit(0 if passed else 1)

if __name__=='__main__':main()
