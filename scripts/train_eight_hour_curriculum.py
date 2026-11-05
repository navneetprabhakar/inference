"""Deadline-guarded, resumable, length-bucketed trainer for the isolated goal."""
import argparse, fcntl, hashlib, json, math, os, shutil, signal, time
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten, tree_map, tree_unflatten
from benchmark_mlx import Model
from sft_common import ROOT, configure_memory, memory_stats, masked_loss
from train_local import atomic_json, health as host_health
from checkpoint_retention import prune

STOP=False
def stop(*_):
 global STOP;STOP=True
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def health():return {**host_health(),**memory_stats()}
def main(a):
 signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
 cfg_path=Path(a.config) if a.config else ROOT/'runs/eight-hour-improvement-v1/training-config.json'
 if not cfg_path.is_absolute(): cfg_path=ROOT/cfg_path
 cfg=json.loads(cfg_path.read_text());run_dir=ROOT/cfg.get('run_dir','runs/eight-hour-improvement-v1');out=run_dir/'training';out.mkdir(parents=True,exist_ok=True)
 lock=(out/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 global_lock=(ROOT/'runs/eight-hour-improvement-v1/.training.lock').open('a');fcntl.flock(global_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if time.time()>=cfg['deadline_unix']:raise RuntimeError('absolute deadline already passed')
 if (ROOT/'runs/eight-hour-improvement-v1/confirmation-started.json').exists():raise RuntimeError('Training closed: confirmation already started')
 data=ROOT/cfg['data_dir'];manifest=json.loads((data/'manifest.json').read_text());arr=dict(np.load(data/'episodes.npz'));order=json.loads((data/'order.json').read_text())['order']
 # Sort each small local block by length: no cross-example attention and less tail padding.
 batches=[]
 for j in range(0,len(order),64):
  block=sorted(order[j:j+64],key=lambda i:int(arr['length'][i]))
  batches += [block[k:k+cfg['batch_size']] for k in range(0,len(block),cfg['batch_size']) if len(block[k:k+cfg['batch_size']])==cfg['batch_size']]
 base=ROOT/cfg['base_checkpoint'];initial=health();configure_memory()
 state={'status':'initializing','steps':0,'cursor':0,'nonpadding_input_tokens':0,'supervised_assistant_tokens':0,'active_seconds':0.0,'started_unix':time.time(),'deadline_unix':cfg['deadline_unix'],'base_checkpoint':str(base.relative_to(ROOT)),'base_sha256':sha(base/'model.safetensors'),'data_manifest_sha256':sha(data/'manifest.json'),'initial_health':initial,'best_loss':None,'best_checkpoint':None}
 master=Model(768,12,16384);master.load_weights(str(base/'model.safetensors'));compute=Model(768,12,16384);compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()));opt=optim.AdamW(cfg['learning_rate'],betas=[.9,.95],weight_decay=.1,bias_correction=True)
 if a.resume:
  latest=json.loads((out/'latest.json').read_text())['directory'];saved=json.loads((out/latest/'state.json').read_text())
  for k in ['deadline_unix','base_sha256','data_manifest_sha256']:
   if saved[k]!=state[k]:raise RuntimeError('resume provenance mismatch '+k)
  state=saved;master.load_weights(str(out/latest/'model.safetensors'));opt.state=tree_unflatten(list(mx.load(str(out/latest/'optimizer.npz')).items()))
 # On resume the compute model must match the restored master BEFORE first loss.
 compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()))
 mx.eval(master.parameters(),compute.parameters(),opt.state);grad=nn.value_and_grad(compute,masked_loss);last=time.monotonic()
 def snapshot(status,force_best=False):
  nonlocal state
  dest=out/f'checkpoint-{state["nonpadding_input_tokens"]:012d}-{time.time_ns()}';tmp=out/(dest.name+'.partial');tmp.mkdir()
  mx.eval(master.parameters(),opt.state);master.save_weights(str(tmp/'model.safetensors'));mx.savez(str(tmp/'optimizer.npz'),**dict(tree_flatten(opt.state)))
  state.update(status=status,updated_unix=time.time(),health=health(),wallclock_elapsed_seconds=time.time()-state['started_unix'])
  state['model_sha256']=sha(tmp/'model.safetensors');atomic_json(tmp/'state.json',state);os.replace(tmp,dest);atomic_json(out/'latest.json',{'directory':dest.name,'model_sha256':state['model_sha256']})
  prior=state.get('best_checkpoint')
  if force_best or prior is None:state['best_checkpoint']=dest.name;atomic_json(out/'best.json',{'directory':dest.name,'loss':state.get('best_loss'),'model_sha256':state['model_sha256']})
  selected_path=out/'selected-best.json'
  if selected_path.exists():
   selected=json.loads(selected_path.read_text());selected_dir=out/selected['directory']
   if selected_dir.parent.resolve()!=out.resolve() or sha(selected_dir/'model.safetensors')!=selected['model_sha256']:raise RuntimeError('Selected best checkpoint provenance mismatch')
   state['best_checkpoint']=selected['directory'];atomic_json(out/'best.json',{**selected,'selection_basis':'development_review'})
  keep={dest.name,state.get('best_checkpoint')}
  prune(out,keep)
  atomic_json(out/'status.json',state)
 while state['cursor']<len(batches):
  h=health();why=None
  if STOP or (out/'STOP').exists() or (run_dir/'STOP').exists() or (ROOT/'runs/eight-hour-improvement-v1/STOP').exists():why='run_specific_stop'
  elif (ROOT/'runs/eight-hour-improvement-v1/confirmation-started.json').exists():why='confirmation_selection_closed_training'
  elif time.time()>=cfg['deadline_unix']:why='absolute_deadline'
  elif time.time()-state['started_unix']>=cfg['max_active_seconds']:why='active_time_cap'
  elif h['free_disk_bytes']<cfg['min_free_disk_bytes']:why='disk_reserve'
  elif h['mlx_allocator_bytes']>cfg['max_mlx_allocator_bytes']:why='mlx_memory'
  elif h.get('mlx_peak_bytes',0)>cfg['max_mlx_allocator_bytes']:why='mlx_peak_memory'
  elif h.get('thermal_state',0)>=3:why='critical_thermal'
  elif h.get('swap_used_mb') is not None and state['initial_health'].get('swap_used_mb') is not None and h['swap_used_mb']-state['initial_health']['swap_used_mb']>1024:why='swap_growth'
  if why:snapshot('stopped_'+why);return 0
  ix=batches[state['cursor']];width=max(int(arr['length'][i]) for i in ix);tokens=mx.array(arr['ids'][ix,:width]);mask=mx.array(arr['mask'][ix,:width-1]);loss,g=grad(compute,tokens,mask);mx.eval(loss,g);g,norm=optim.clip_grad_norm(g,1.0);mx.eval(norm)
  if not math.isfinite(float(loss)) or not math.isfinite(float(norm)):snapshot('stopped_nonfinite');return 2
  opt.update(master,tree_map(lambda x:x.astype(mx.float32),g));mx.eval(master.parameters(),opt.state);compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()));mx.eval(compute.parameters())
  state['cursor']+=1;state['steps']+=1;state['nonpadding_input_tokens']+=sum(int(arr['length'][i])-1 for i in ix);state['supervised_assistant_tokens']+=int(arr['mask'][ix,:width-1].sum());state['active_seconds']+=time.monotonic()-last;last=time.monotonic();value=float(loss)
  improved=state['best_loss'] is None or value<state['best_loss'];
  if improved:state['best_loss']=value
  if state['steps']%cfg['checkpoint_every_steps']==0:snapshot('running',improved)
  if state['nonpadding_input_tokens']>=cfg['max_nonpadding_input_tokens']:break
 snapshot('completed');return 0
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');p.add_argument('--config');raise SystemExit(main(p.parse_args()))
