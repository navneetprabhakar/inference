"""Bounded CPU subprocess checks using real upstream Muon; no Own training."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(os.environ.get('OWN_CAPTURE_CHECK_DIR',str(Path(__file__).parent/'local-checks'))).resolve()
sys.path.insert(0,str(ROOT))

def worker(branch):
 import torch
 sys.path.insert(0,str(ROOT/'runs/nanochat-source'))
 from nanochat import optim
 from cloud_training.nano_optimizer_capture import capture_step
 torch.set_num_threads(1);torch.use_deterministic_algorithms(True);torch.manual_seed(213)
 # Two groups exercise non-target pass-through and exact target selection.
 ps=[torch.nn.Parameter(torch.randn(8,4)),*[torch.nn.Parameter(torch.randn(16,64)) for _ in range(3)]]
 groups=[dict(kind='muon',params=p,lr=.005,momentum=.95,beta2=.95,weight_decay=0.,ns_steps=5) for p in [[ps[0]],ps[1:]]]
 opt=optim.MuonAdamW(groups);names=['other','target','target2','target3']
 if branch=='restored':
  checkpoint=torch.load(OUT/'step1.pt',weights_only=True)
  with torch.no_grad():
   for p,v in zip(ps,checkpoint['params']):p.copy_(v)
  opt.load_state_dict(checkpoint['optimizer']);torch.set_rng_state(checkpoint['rng'])
 for step in range(1 if branch=='restored' else 0,2):
  generator=torch.Generator().manual_seed(1400+step)
  for p in ps:p.grad=torch.randn(p.shape,generator=generator)
  if step==1 and branch!='baseline':
   with capture_step(optim,opt,zip(names,ps),OUT/branch,step=step,parameter='target',identity={'fixture':'small_cpu_two_group','production_weights':False}):opt.step()
  else:
   opt.step()
   if step==0:torch.save({'params':[p.detach().clone() for p in ps],'optimizer':opt.state_dict(),'rng':torch.get_rng_state()},OUT/'step1.pt')
 torch.save({'params':[p.detach().clone() for p in ps],'optimizer':opt.state_dict()},OUT/(branch+'-final.pt'))

def main():
 p=argparse.ArgumentParser();p.add_argument('--worker',choices=['uninterrupted','restored','baseline']);a=p.parse_args()
 if a.worker:return worker(a.worker)
 OUT.mkdir(exist_ok=False)
 from cloud_training.nano_optimizer_capture import load_capture,exact
 results={}
 def run(label,args):
  env={**os.environ,'NANOCHAT_DTYPE':'bfloat16','TORCHINDUCTOR_CACHE_DIR':str(OUT/(label+'-cache'))}
  r=subprocess.run([sys.executable,*args],cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
  (OUT/(label+'.log')).write_text(r.stdout+r.stderr)
  if r.returncode:raise RuntimeError(label+' failed; see log')
  print(label,'complete',flush=True)
 for branch in ['uninterrupted','restored','baseline']:run(branch,[__file__,'--worker',branch])
 _,a,b=load_capture(OUT/'uninterrupted');_,c,d=load_capture(OUT/'restored')
 results['fresh_process_capture']={'inputs_exact':exact(a,c),'outputs_exact':exact(b,d)}
 assert all(results['fresh_process_capture'].values())
 import torch
 from cloud_training.nano_checkpoint import _exact_fingerprint
 captured=torch.load(OUT/'uninterrupted-final.pt',weights_only=True)
 baseline=torch.load(OUT/'baseline-final.pt',weights_only=True)
 results['capture_noninterference_exact']=_exact_fingerprint(captured)==_exact_fingerprint(baseline)
 assert results['capture_noninterference_exact']
 for mode in ['eager','compiled']:
  for trial in (1,2):
   label=mode+'-'+str(trial)
   run(label,['-m','cloud_training.nano_optimizer_capture','--capture',str(OUT/'uninterrupted'),'--repo',str(ROOT/'runs/nanochat-source'),'--mode',mode,'--output',str(OUT/label)])
   results[label]=json.loads((OUT/label/'result.json').read_text())
  import torch
  x=torch.load(OUT/(mode+'-1')/'first-output.pt',weights_only=True);y=torch.load(OUT/(mode+'-2')/'first-output.pt',weights_only=True)
  results[mode+'_fresh_process_exact']=exact(x,y)
 assert all(results[m+'_'+ 'fresh_process_exact'] for m in ['eager','compiled'])
 assert all(results[m+'-'+str(t)]['repeatable_exact'] for m in ['eager','compiled'] for t in (1,2))
 results['scope']='Synthetic reduced-shape CPU actual upstream calls; not actual failing A100 input tensors or English capability'
 (OUT/'results.json').write_text(json.dumps(results,indent=2));print('All CPU capture/replay checks complete',flush=True)
if __name__=='__main__':main()
