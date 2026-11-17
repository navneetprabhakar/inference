"""Synthetic single-rank optimizer plumbing probe. Never trains or alters Own weights."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent

def worker(mode,branch):
 import torch
 sys.path.insert(0,str(ROOT/'runs/nanochat-source'))
 from nanochat import optim
 torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
 originals={n:getattr(optim,n) for n in ['muon_step_fused','adamw_step_fused']}
 captured=[]
 def fingerprint(t):
  x=t.detach().cpu().contiguous()
  return {'shape':list(t.shape),'stride':list(t.stride()),'dtype':str(t.dtype),'storage_offset':t.storage_offset(),'sha256':hashlib.sha256(x.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()}
 def wrap(name):
  fn=originals[name] if mode=='compiled' else originals[name].__wrapped__
  def call(*args):
   before=[fingerprint(x) if isinstance(x,torch.Tensor) else x for x in args]
   fn(*args)
   captured.append({'kernel':name,'before':before,'after':[fingerprint(x) if isinstance(x,torch.Tensor) else x for x in args]})
  return call
 for n in originals:setattr(optim,n,wrap(n))
 torch.manual_seed(419)
 # Match failing projection group's wide geometry, at reduced synthetic shape.
 params=[torch.nn.Parameter(torch.randn(16,64)) for _ in range(3)]
 opt=optim.MuonAdamW([{'kind':'muon','params':params,'lr':.005,'momentum':.95,'beta2':.95,'weight_decay':0.,'ns_steps':5}])
 checkpoint=OUT/(mode+'-step1.pt')
 if branch=='restored':
  state=torch.load(checkpoint,weights_only=True)
  with torch.no_grad():
   for p,v in zip(params,state['params']):p.copy_(v)
  opt.load_state_dict(state['optimizer'])
 start=1 if branch=='restored' else 0
 for step in range(start,2):
  g=torch.Generator().manual_seed(1200+step)
  for p in params:p.grad=torch.randn(p.shape,generator=g)
  opt.step()
  if step==0:
   torch.save({'params':[p.detach().clone() for p in params],'optimizer':opt.state_dict()},checkpoint)
   captured.clear()
 torch.save({'params':[p.detach().clone() for p in params],'optimizer':opt.state_dict()},OUT/(mode+'-'+branch+'-final.pt'))
 (OUT/(mode+'-'+branch+'.json')).write_text(json.dumps({'torch':torch.__version__,'device':'cpu','compute_dtype':str(optim.COMPUTE_DTYPE),'mode':mode,'branch':branch,'calls':captured},indent=2))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--worker',choices=['eager','compiled']);ap.add_argument('--branch',choices=['uninterrupted','restored']);a=ap.parse_args()
 if a.worker:return worker(a.worker,a.branch)
 import torch
 results={}
 for mode in ['eager','compiled']:
  for branch in ['uninterrupted','restored']:
   env={**os.environ,'NANOCHAT_DTYPE':'bfloat16','TORCHINDUCTOR_CACHE_DIR':str(OUT/('cache-'+mode+'-'+branch))}
   p=subprocess.run([sys.executable,__file__,'--worker',mode,'--branch',branch],cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
   (OUT/(mode+'-'+branch+'.log')).write_text(p.stdout+p.stderr)
   if p.returncode:raise RuntimeError(f'{mode}/{branch} failed; inspect log')
  x=json.loads((OUT/(mode+'-uninterrupted.json')).read_text());y=json.loads((OUT/(mode+'-restored.json')).read_text())
  left=torch.load(OUT/(mode+'-uninterrupted-final.pt'),weights_only=True);right=torch.load(OUT/(mode+'-restored-final.pt'),weights_only=True)
  def equal(a,b):
   if isinstance(a,torch.Tensor):return torch.equal(a,b)
   if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
   if isinstance(a,(list,tuple)):return len(a)==len(b) and all(equal(v,w) for v,w in zip(a,b))
   return a==b
  results[mode]={'kernel_inputs_exact': [c['before'] for c in x['calls']]==[c['before'] for c in y['calls']], 'kernel_outputs_exact':[c['after'] for c in x['calls']]==[c['after'] for c in y['calls']], 'serialized_final_state_exact':equal(left,right)}
  # Comparator must detect a one-element perturbation.
  right['params'][0][0,0]+=1;assert not equal(left,right)
  print(mode,results[mode],flush=True)
 (OUT/'results.json').write_text(json.dumps({'scope':'Synthetic reduced-shape CPU plumbing only; not CUDA qualification, actual-gradient replay or English learning evidence','results':results,'negative_control_detected':True,'production_changes':False},indent=2))
if __name__=='__main__':main()
