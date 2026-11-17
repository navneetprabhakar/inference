"""Opt-in, bounded Muon fused-input evidence. No training/quality acceptance claims.

Storage/view relationships are reconstructed without copying unreferenced storage
bytes. Unsupported layouts and mixed-dtype storage aliases fail closed.
"""
import argparse, contextlib, hashlib, inspect, json, os
from pathlib import Path
import torch

VERSION = 1
MAX_BYTES = 2 * 1024**3

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write_json(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.flush(); os.fsync(f.fileno())

def environment(module):
    cuda = torch.cuda.is_available()
    return dict(torch=str(torch.__version__), cuda=torch.version.cuda,
                harness_sha256=sha(__file__),
                compute_dtype=str(module.COMPUTE_DTYPE), threads=torch.get_num_threads(),
                interop_threads=torch.get_num_interop_threads(), default_dtype=str(torch.get_default_dtype()),
                bf16_reduced_precision=torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction,
                fp16_reduced_precision=torch.backends.cuda.matmul.allow_fp16_reduced_precision_reduction, source_sha256=sha(inspect.getfile(module)),
                deterministic=torch.are_deterministic_algorithms_enabled(),
                deterministic_warn_only=torch.is_deterministic_algorithms_warn_only_enabled(),
                matmul_precision=torch.get_float32_matmul_precision(),
                matmul_tf32=torch.backends.cuda.matmul.allow_tf32,
                cudnn_tf32=torch.backends.cudnn.allow_tf32,
                cudnn_benchmark=torch.backends.cudnn.benchmark,
                cudnn_deterministic=torch.backends.cudnn.deterministic,
                cublas_workspace=os.environ.get('CUBLAS_WORKSPACE_CONFIG'),
                gpu=torch.cuda.get_device_name() if cuda else None,
                capability=list(torch.cuda.get_device_capability()) if cuda else None)

def layout(args):
    groups = {}; specs = []; sizes = []
    for arg in args:
        if not torch.is_tensor(arg):
            if type(arg) not in (int, float, bool): raise ValueError('Unsupported kernel argument')
            specs.append({'scalar': arg}); continue
        if arg.layout != torch.strided or arg.is_conj() or arg.is_neg() or arg.numel() == 0:
            raise ValueError('Unsupported tensor layout')
        if any(s < 0 for s in arg.stride()) or torch._debug_has_internal_overlap(arg) != 0:
            raise ValueError('Overlapping/ambiguous tensor layout')
        storage = arg.untyped_storage()
        key = (str(arg.device), storage.data_ptr())
        if key not in groups:
            groups[key] = (len(sizes), arg.dtype); sizes.append(0)
        group, dtype = groups[key]
        if dtype != arg.dtype: raise ValueError('Mixed-dtype storage alias')
        end = arg.storage_offset() + 1 + sum((n-1)*s for n,s in zip(arg.shape,arg.stride()))
        if end * arg.element_size() > storage.nbytes(): raise ValueError('View exceeds storage')
        sizes[group] = max(sizes[group], storage.nbytes())
        specs.append(dict(group=group, shape=list(arg.shape), stride=list(arg.stride()),
                          offset=arg.storage_offset(), dtype=str(arg.dtype), device=str(arg.device),
                          storage_bytes=storage.nbytes()))
    return specs, sizes

def snapshot(args, max_bytes):
    specs, sizes = layout(args)
    if sum(sizes) > max_bytes: raise ValueError('Capture byte bound exceeded')
    stores = [None] * len(sizes)
    for arg, spec in zip(args, specs):
        if 'scalar' in spec: continue
        i = spec['group']
        if stores[i] is None: stores[i] = torch.zeros(sizes[i]//arg.element_size(), dtype=arg.dtype)
        stores[i].as_strided(spec['shape'],spec['stride'],spec['offset']).copy_(arg.detach().cpu())
    return {'specs':specs, 'stores':stores}

def restore(snap):
    devices = {}
    for spec in snap['specs']:
        if 'group' in spec: devices[spec['group']] = spec['device']
    stores = [t.to(devices[i]).clone() for i,t in enumerate(snap['stores'])]
    return [s['scalar'] if 'scalar' in s else stores[s['group']].as_strided(s['shape'],s['stride'],s['offset']) for s in snap['specs']]

def exact(a,b):
    if a['specs'] != b['specs']: return False
    # Compare byte representations, including signed zero/NaN payloads.
    return len(a['stores']) == len(b['stores']) and all(torch.equal(x.view(torch.uint8),y.view(torch.uint8)) for x,y in zip(a['stores'],b['stores']))

def config(args):
    step=getattr(args,'capture_muon_step',None)
    if step is None: return None
    if type(step) is not int or step not in (0,1): raise ValueError('Capture step must be0 or1')
    if not getattr(args,'fit_diagnostic',False): raise ValueError('Muon capture requires isolated fit diagnostic')
    if getattr(args,'trace_updates',0) <= step: raise ValueError('Muon capture requires matching update traces')
    return {'version':VERSION,'absolute_step':step,'parameter':getattr(args,'capture_muon_param','transformer.h.0.mlp.c_proj.weight'), 'max_bytes':MAX_BYTES}

@contextlib.contextmanager
def capture_step(module, optimizer, named_parameters, path, *, step, parameter, identity, max_bytes=MAX_BYTES):
    """Wrap exactly one selected single-rank Muon group for one optimizer.step()."""
    if type(max_bytes) is not int or not 0 < max_bytes <= MAX_BYTES: raise ValueError('Invalid capture byte bound')
    if torch.distributed.is_initialized() and torch.distributed.get_world_size()!=1:
        raise ValueError('Capture supports single-rank only')
    if getattr(module,'_own_capture_active',False): raise ValueError('Nested/concurrent capture forbidden')
    names={id(p):name for name,p in named_parameters}; groups=[g for g in optimizer.param_groups if g.get('kind')=='muon']
    selected=[i for i,g in enumerate(groups) if parameter in [names.get(id(p)) for p in g['params']]]
    if len(selected)!=1: raise ValueError('Target must identify exactly one Muon group')
    index=selected[0];group=groups[index]
    if any(id(p) not in names for p in group['params']): raise ValueError('Unmapped optimizer parameter')
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    original=module.muon_step_fused;calls=0;captured=0
    meta=dict(version=VERSION,kernel='muon_step_fused',captured_callable_compiled=hasattr(original,'_torchdynamo_orig_callable'),step=step,parameter_names=[names[id(p)] for p in group['params']],
              group_index=index,group={k:v for k,v in group.items() if k!='params'},identity=identity,
              environment=environment(module),max_bytes=max_bytes,
              scope='Raw fused-call evidence; not CUDA qualification or model acceptance')
    write_json(path/'context.json',meta)
    def wrapped(*args):
        nonlocal calls,captured
        current=calls;calls+=1
        if current!=index: return original(*args)
        if captured: raise ValueError('More than one capture requested')
        # Before+after storage and serialization overhead must fit the declared cap.
        _,sizes=layout(args)
        if 2*sum(sizes)+2*1024**2 > max_bytes: raise ValueError('Capture byte bound exceeded')
        before=snapshot(args,max_bytes//2)
        torch.save(before,path/'before.pt')
        result=original(*args)
        after=snapshot(args,max_bytes//2)
        torch.save(after,path/'after.pt')
        files={n:{'sha256':sha(path/n),'bytes':(path/n).stat().st_size} for n in ('context.json','before.pt','after.pt')}
        if sum(v['bytes'] for v in files.values())>max_bytes: raise ValueError('Serialized capture exceeded bound')
        for n in files:
            with (path/n).open('rb') as f: os.fsync(f.fileno())
        write_json(path/'manifest.json',{'version':VERSION,'files':files})
        captured+=1
        return result
    module._own_capture_active=True;module.muon_step_fused=wrapped
    try:
        yield
        if calls!=len(groups) or captured!=1: raise ValueError('Incomplete/changed optimizer call schedule')
        write_json(path/'COMMITTED',{'manifest_sha256':sha(path/'manifest.json')})
        fd=os.open(path,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        module.muon_step_fused=original;del module._own_capture_active

def load_capture(path):
    path=Path(path)
    if path.is_symlink(): raise ValueError('Capture symlink forbidden')
    for n in ('COMMITTED','manifest.json','context.json','before.pt','after.pt'):
        if (path/n).is_symlink(): raise ValueError('Capture symlink forbidden')
    commit=json.loads((path/'COMMITTED').read_text())
    if sha(path/'manifest.json')!=commit['manifest_sha256']: raise ValueError('Manifest hash mismatch')
    m=json.loads((path/'manifest.json').read_text())
    if m.get('version')!=VERSION or set(m['files'])!={'context.json','before.pt','after.pt'}: raise ValueError('Capture manifest schema')
    if sum(f['bytes'] for f in m['files'].values())>MAX_BYTES: raise ValueError('Capture exceeds size bound')
    for n,v in m['files'].items():
        if (path/n).stat().st_size!=v['bytes'] or sha(path/n)!=v['sha256']: raise ValueError('Capture integrity mismatch: '+n)
    return json.loads((path/'context.json').read_text()),*[torch.load(path/n,map_location='cpu',weights_only=True) for n in ('before.pt','after.pt')]

def replay(path, module, mode, output):
    """Fresh process per invocation; repeats use fresh input clones, not warmed state."""
    meta,before,after=load_capture(path)
    if environment(module)!=meta['environment']: raise ValueError('Replay environment/source mismatch')
    if mode not in ('eager','compiled'): raise ValueError('Unknown replay mode')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    fn=module.muon_step_fused if mode=='compiled' else module.muon_step_fused.__wrapped__
    results=[];first=None
    for iteration in range(3):
        args=restore(before)
        if not exact(snapshot(args,MAX_BYTES),before): raise ValueError('Input reconstruction changed values/layout/aliases')
        fn(*args);got=snapshot(args,MAX_BYTES)
        results.append({'iteration':iteration,'phase':'first_call' if iteration==0 else 'warm_repeat',
                        'matches_captured_output_exact':exact(got,after),
                        'matches_first_replay_exact':True if first is None else exact(got,first)})
        if first is None: first=got;torch.save(got,output/'first-output.pt')
    result={'mode':mode,'calls':results,'repeatable_exact':all(r['matches_first_replay_exact'] for r in results),
            'capture_manifest_sha256':sha(Path(path)/'manifest.json'),'environment':environment(module),
            'scope':'Kernel replay only. Cross-mode differences do not by themselves prove a restart defect.'}
    write_json(output/'result.json',result);return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',required=True);p.add_argument('--repo',required=True)
    p.add_argument('--mode',choices=('eager','compiled'),required=True);p.add_argument('--output',required=True)
    args=p.parse_args()
    import sys
    sys.path.insert(0,str(Path(args.repo).resolve()))
    meta,before,after=load_capture(args.capture);del before,after
    e=meta['environment']
    os.environ['NANOCHAT_DTYPE']=e['compute_dtype'].removeprefix('torch.')
    torch.set_num_threads(e['threads']);torch.set_num_interop_threads(e['interop_threads'])
    torch.set_default_dtype(getattr(torch,e['default_dtype'].removeprefix('torch.')))
    torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction=e['bf16_reduced_precision']
    torch.backends.cuda.matmul.allow_fp16_reduced_precision_reduction=e['fp16_reduced_precision']
    if args.mode=='compiled':
        cache=Path(args.output).resolve().with_name(Path(args.output).name+'-compiler-cache')
        cache.mkdir(parents=True,exist_ok=False)
        os.environ['TORCHINDUCTOR_CACHE_DIR']=str(cache)
    from nanochat import optim
    # Restore declared numerical flags before comparing the full environment identity.
    torch.use_deterministic_algorithms(e['deterministic'],warn_only=e['deterministic_warn_only'])
    torch.set_float32_matmul_precision(e['matmul_precision'])
    torch.backends.cuda.matmul.allow_tf32=e['matmul_tf32'];torch.backends.cudnn.allow_tf32=e['cudnn_tf32']
    torch.backends.cudnn.benchmark=e['cudnn_benchmark'];torch.backends.cudnn.deterministic=e['cudnn_deterministic']
    print(json.dumps(replay(args.capture,optim,args.mode,args.output),indent=2))

if __name__=='__main__':main()
