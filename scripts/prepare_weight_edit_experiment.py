"""Create immutable direct-edit candidates on CPU from pinned source weights."""
import json,hashlib,time,os
from pathlib import Path
import numpy as np
from safetensors import safe_open
from safetensors.numpy import save_file
from weight_edit_ops import edited_tensor,bf16_codes
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/weight-edit-experiment-v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def guard():
 a=json.loads((RUN/'authorization.json').read_text())
 if time.time()>=a['deadline_unix'] or (RUN/'STOP').exists():raise RuntimeError('New run stopped/deadline')
 return a
if __name__=='__main__':
 auth=guard();plan=json.loads((RUN/'edit-plan.json').read_text());paths={k:ROOT/v['path'] for k,v in plan['sources'].items()}
 for k,p in paths.items():assert sha(p)==plan['sources'][k]['sha256']
 sources={k:safe_open(str(p),framework='numpy') for k,p in paths.items()}
 names=sorted(sources['v11'].keys());assert all(sorted(v.keys())==names for v in sources.values())
 for candidate in plan['candidates']:
  guard();dest=RUN/'candidates'/candidate['id'];dest.mkdir(parents=True,exist_ok=False);values={};details=[];sumdelta=sumbase=0.;changed=total=0
  for name in names:
   arrays={k:s.get_tensor(name) for k,s in sources.items()};shape=arrays['v11'].shape;assert all(a.shape==shape and a.dtype==np.float32 for a in arrays.values())
   out=edited_tensor(name,**arrays,method=candidate['method'],scale=candidate['scale']);assert np.isfinite(out).all();values[name]=np.ascontiguousarray(out)
   delta=(out-arrays['v11']).astype(np.float64);base=arrays['v11'].astype(np.float64);ds=float(np.sum(delta*delta));bs=float(np.sum(base*base));nchanged=int(np.count_nonzero(bf16_codes(out)!=bf16_codes(arrays['v11'])))
   sumdelta+=ds;sumbase+=bs;changed+=nchanged;total+=out.size;details.append({'name':name,'relative_l2':(ds/max(bs,1e-30))**.5,'bf16_changed':nchanged,'entries':out.size})
  assert total==97536768 and total<=auth['max_parameters'];guard();save_file(values,str(dest/'model.safetensors'))
  saved=safe_open(str(dest/'model.safetensors'),framework='numpy')
  for name in names:assert np.array_equal(values[name],saved.get_tensor(name))
  proof={**candidate,'parameters':total,'sha256':sha(dest/'model.safetensors'),'relative_l2_vs_v11':(sumdelta/sumbase)**.5,'bf16_changed_fraction':changed/total,'tensors':details,'source_hashes':{k:v['sha256'] for k,v in plan['sources'].items()},'no_training':True,'saved_arrays_verified':True,'created_unix':time.time()}
  (dest/'derivation.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({k:proof[k] for k in ['id','relative_l2_vs_v11','bf16_changed_fraction','sha256']}),flush=True);del values
 for k,p in paths.items():assert sha(p)==plan['sources'][k]['sha256']
 (RUN/'preparation-complete.json').write_text(json.dumps({'sources_unchanged':True,'candidates':[x['id'] for x in plan['candidates']],'finished_unix':time.time()},indent=2)+'\n')
