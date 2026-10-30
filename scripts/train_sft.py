"""Full-weight local SFT; exactly 5M processed input slots per arm."""
import argparse,fcntl,hashlib,json,math,os,signal,time
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_map,tree_unflatten
from benchmark_mlx import Model
from train_local import atomic_json,health,save_checkpoint
from sft_common import ROOT,masked_loss
STOP=False
LIMIT=5_000_000
MILESTONES=[1_000_000,3_000_000,5_000_000]
def stop(*_):
 global STOP
 STOP=True

def lr_at(tokens,peak):
 if tokens<250000:return peak*max(tokens,8192)/250000
 return 1e-6+(peak-1e-6)*.5*(1+math.cos(math.pi*min(1,(tokens-250000)/4750000)))

def batch_slots(arrays,order,cursor):
 indices=order[cursor:cursor+2]
 assert len(indices)==2,'Exposure order exhausted'
 return 2*int(max(arrays['train_length'][indices])-1)

def batch(arrays,order,cursor,valid):
 indices=order[cursor:cursor+2]
 slots=batch_slots(arrays,order,cursor);width=slots//2
 valid=min(valid,slots)
 ids=arrays['train_ids'][indices,:width+1];mask=arrays['train_mask'][indices,:width].copy();mask.reshape(-1)[valid:]=0
 nonpad=sum(min(max(int(arrays['train_length'][idx])-1,0),max(0,valid-j*width)) for j,idx in enumerate(indices))
 return mx.array(ids),mx.array(mask),int(mask.sum()),int(nonpad)

def dev_loss(model,arrays):
 indices=[]
 for s in [0,1,2]:indices.extend(np.flatnonzero(arrays['dev_source']==s)[:24].tolist())
 totals={}
 for src in [0,1,2]:
  subset=[i for i in indices if arrays['dev_source'][i]==src];num=den=0
  for k in range(0,len(subset),2):
   ix=subset[k:k+2];m=arrays['dev_mask'][ix];n=float(m.sum());v=masked_loss(model,mx.array(arrays['dev_ids'][ix]),mx.array(m));mx.eval(v);num+=float(v)*n;den+=n
  totals[['chat','tool','grounded'][src]]=num/max(1,den)
 return totals

def main(a):
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 data=ROOT/'data/sft-v2';out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);lock=(out/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert a.lr in [1e-5,3e-5]
 manifest=json.loads((data/'manifest.json').read_text())
 for n,h in manifest['files'].items():assert hashlib.sha256((data/n).read_bytes()).hexdigest()==h,n
 arrays=dict(np.load(data/'episodes.npz'));order=np.load(data/'order.npy');pins={n:hashlib.sha256((ROOT/'scripts'/n).read_bytes()).hexdigest() for n in ['train_sft.py','sft_common.py','benchmark_mlx.py','train_local.py']};data_hash=hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest()
 if (out/'latest.json').exists() and not a.resume:raise RuntimeError('Existing output requires --resume')
 origin=a.checkpoint.resolve();state={'tokens':0,'steps':0,'cursor':0,'supervised_tokens':0,'nonpadding_input_tokens':0,'active_seconds':0.,'peak_lr':a.lr,'limit':LIMIT,'data_sha256':data_hash,'code_pins':pins,'base_checkpoint':str(origin),'base_model_sha256':hashlib.sha256((origin/'model.safetensors').read_bytes()).hexdigest(),'power_policy':'continue_on_battery','initial_health':health()}
 master=Model(768,12,16384);opt=optim.AdamW(a.lr,betas=[.9,.95],weight_decay=.1,bias_correction=True)
 if a.resume:
  origin=out/json.loads((out/'latest.json').read_text())['directory'];state=json.loads((origin/'state.json').read_text());assert state['code_pins']==pins and state['data_sha256']==data_hash and state['peak_lr']==a.lr
  opt.state=tree_unflatten(list(mx.load(str(origin/'optimizer.npz')).items()))
 master.load_weights(str(origin/'model.safetensors'));compute=Model(768,12,16384);compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()));mx.eval(master.parameters(),compute.parameters(),opt.state)
 grad=nn.value_and_grad(compute,masked_loss)
 def snapshot(status):
  state.update(status=status,updated_at=time.time(),pid=os.getpid(),health=health());atomic_json(out/'status.json',state);return dict(state)
 def checkpoint(status):return save_checkpoint(out,master,opt,snapshot(status))
 state['initial_dev_loss']=state.get('initial_dev_loss') or dev_loss(compute,arrays);snapshot('running');print('SFT initialized',a.lr,state['tokens'],flush=True)
 last=time.monotonic();last_health=0;last_log=last;last_checkpoint=last;start_tokens=state['tokens'];start_active=state['active_seconds']
 while state['tokens']<LIMIT:
  if STOP or (out/'STOP').exists() or (out.parent/'STOP').exists():checkpoint('stopped');return 2
  if time.monotonic()-last_health>15:
   h=health();last_health=time.monotonic()
   if h['thermal_state']>=3:
    checkpoint('paused_critical_thermal')
    while h['thermal_state']>=3 and not STOP and not (out/'STOP').exists() and not (out.parent/'STOP').exists():time.sleep(10);h=health()
    last=time.monotonic();continue
   if h['free_disk_bytes']<15*2**30 or h['mlx_peak_bytes']>12*2**30 or h['swap_used_mb']-state['initial_health']['swap_used_mb']>1024:checkpoint('stopped_resource_limit');return 3
  endpoint=next(x for x in MILESTONES if x>state['tokens']);count=min(8192,endpoint-state['tokens']);batches=[];used=0;total_targets=0;nonpad=0
  while used<count:
   valid=min(batch_slots(arrays,order,state['cursor']),count-used);t,m,n,p=batch(arrays,order,state['cursor'],valid);state['cursor']+=2;batches.append((t,m,n));total_targets+=n;nonpad+=p;used+=valid
  acc=None;weighted=0.
  for t,m,n in batches:
   if n==0:continue
   v,g=grad(compute,t,m);g=tree_map(lambda x:x.astype(mx.float32)*(n/total_targets),g);acc=g if acc is None else tree_map(lambda x,y:x+y,acc,g);mx.eval(v,acc);weighted+=float(v)*n
  if total_targets:
   acc,norm=optim.clip_grad_norm(acc,1.);mx.eval(norm);v=weighted/total_targets
   if not math.isfinite(v) or not math.isfinite(float(norm)):checkpoint('stopped_nonfinite');return 4
   opt.learning_rate=lr_at(state['tokens'],a.lr);opt.update(master,acc);mx.eval(master.parameters(),opt.state);compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()));mx.eval(compute.parameters());state['steps']+=1;state.update(last_loss=v,gradient_norm=float(norm))
  state['tokens']+=count;state['supervised_tokens']+=total_targets;state['nonpadding_input_tokens']+=nonpad;now=time.monotonic();state['active_seconds']+=now-last;last=now
  if now-last_log>=60:
   state['tokens_per_second']=(state['tokens']-start_tokens)/max(.001,state['active_seconds']-start_active);snapshot('running')
   with (out/'metrics.jsonl').open('a') as f:f.write(json.dumps({k:state[k] for k in ['tokens','supervised_tokens','nonpadding_input_tokens','tokens_per_second','last_loss','updated_at']})+'\n')
   print('progress',state['tokens'],state['tokens_per_second'],flush=True);last_log=now
  if now-last_checkpoint>=300:checkpoint('running');last_checkpoint=time.monotonic()
  if state['tokens'] in MILESTONES:
   state['dev_loss']=dev_loss(compute,arrays);dest=out/'milestones'/str(state['tokens']);dest.parent.mkdir(parents=True,exist_ok=True)
   tmp=dest.with_name(dest.name+'.partial');tmp.mkdir(exist_ok=True);master.save_weights(str(tmp/'model.safetensors'));atomic_json(tmp/'state.json',snapshot('milestone'));os.replace(tmp,dest)
   checkpoint('running');print('milestone',state['tokens'],state['dev_loss'],flush=True)
  if state['active_seconds']>8*3600:checkpoint('stopped_8h_limit');return 5
 checkpoint('completed');atomic_json(out/'result.json',{**state,'status':'completed','cloud_spend_usd':0,'paid_api_spend_usd':0});return 0
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--lr',type=float,required=True);p.add_argument('--resume',action='store_true');raise SystemExit(main(p.parse_args()))
