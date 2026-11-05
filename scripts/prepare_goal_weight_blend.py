"""One fixed, provenance-checked CPU weight interpolation; no gradient training."""
import hashlib,json,time
from pathlib import Path
import mlx.core as mx
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 mx.set_default_device(mx.cpu)
 goal=ROOT/'runs/eight-hour-improvement-v1';auth=json.loads((goal/'authorization.json').read_text())
 if time.time()>=auth['deadline_unix'] or (goal/'STOP').exists() or (goal/'confirmation-started.json').exists():raise RuntimeError('Goal closed or STOP')
 references=[json.loads((goal/name).read_text()) for name in ['best-development-candidate.json','best-tool-candidate.json']]
 paths=[ROOT/r['checkpoint']/'model.safetensors' for r in references]
 for p,r in zip(paths,references):assert sha(p)==r['checkpoint_sha256']
 arrays=[mx.load(str(p)) for p in paths];assert set(arrays[0])==set(arrays[1])
 merged={};count=0
 for key,left in arrays[0].items():
  right=arrays[1][key];assert left.shape==right.shape
  value=(left.astype(mx.float32)+right.astype(mx.float32))*0.5
  assert bool(mx.all(mx.isfinite(value)).item());merged[key]=value;count+=value.size
 assert count==97536768 and count<auth['max_parameters']
 out=ROOT/'runs/eight-hour-improvement-v22/checkpoint-blend';out.mkdir(parents=True,exist_ok=False)
 mx.save_safetensors(str(out/'model.safetensors'),merged)
 reloaded=mx.load(str(out/'model.safetensors'))
 for k,v in merged.items():assert bool(mx.all(reloaded[k]==v).item())
 for p,r in zip(paths,references):assert sha(p)==r['checkpoint_sha256']
 provenance={'kind':'fixed_weight_interpolation_no_training','sources':[{'checkpoint':r['checkpoint'],'sha256':r['checkpoint_sha256'],'weight':0.5} for r in references],'parameters':count,'output_sha256':sha(out/'model.safetensors'),'source_weights_unchanged':True,'saved_arrays_exactly_verified':True,'created_unix':time.time(),'reference':'https://proceedings.mlr.press/v162/wortsman22a.html','limitations':['Our related sequential SFT checkpoints are not the paper\'s independently fine-tuned vision setting.','Averaging does not guarantee quality or transfer either source\'s strengths.','One fixed blend, no alpha sweep. Must pass the same actual-output development review.']}
 (out.parent/'derivation.json').write_text(json.dumps(provenance,indent=2)+'\n');print(json.dumps(provenance,indent=2))
if __name__=='__main__':main()
