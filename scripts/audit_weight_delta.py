"""Report an exact checkpoint weight delta without mutating either checkpoint."""
import argparse, hashlib, json
from pathlib import Path
import mlx.core as mx
from mlx.utils import tree_flatten
from benchmark_mlx import Model

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def resolved(path):
    path=Path(path)
    return path if (path/'model.safetensors').exists() else path/json.loads((path/'latest.json').read_text())['directory']
def weights(path):
    path=resolved(path)
    model=Model(768,12,16384); model.load_weights(str(path/'model.safetensors'))
    return dict(tree_flatten(model.parameters()))
def main(args):
    reference,candidate=resolved(args.reference),resolved(args.candidate)
    left,right=weights(reference),weights(candidate)
    squared=base=maximum=0.0; count=0
    for name,value in left.items():
        delta=(right[name].astype(mx.float32)-value.astype(mx.float32)); mx.eval(delta)
        squared+=float(mx.sum(delta*delta)); base+=float(mx.sum(value.astype(mx.float32)**2)); maximum=max(maximum,float(mx.max(mx.abs(delta)))); count+=value.size
    report={'kind':'read_only_checkpoint_delta','reference':str(reference),'candidate':str(candidate),'reference_sha256':digest(reference/'model.safetensors'),'candidate_sha256':digest(candidate/'model.safetensors'),'parameters':count,'l2_delta':squared**.5,'l2_reference':base**.5,'relative_l2_delta':(squared/base)**.5,'max_absolute_delta':maximum}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--reference',type=Path,required=True); p.add_argument('--candidate',type=Path,required=True); p.add_argument('--output',type=Path,required=True); main(p.parse_args())
