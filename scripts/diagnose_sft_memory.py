"""Bounded, disposable real-data memory probe. Never writes campaign checkpoints."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_map,tree_unflatten
from benchmark_mlx import Model
from sft_common import ROOT,masked_loss
from train_sft import batch,batch_slots,lr_at
from train_local import health
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['default-trim','capped-trim','default-fixed'],required=True);p.add_argument('--updates',type=int,default=12);a=p.parse_args();assert 1<=a.updates<=40
out=ROOT/'reports/sft-v2/memory-investigation'/a.mode;out.mkdir(exist_ok=True)
base=ROOT/'runs/sft-v2/100m-lr1e-5';cp=base/json.loads((base/'latest.json').read_text())['directory'];state=json.loads((cp/'state.json').read_text());original_hash=hashlib.sha256((cp/'model.safetensors').read_bytes()).hexdigest()
limit=mx.get_memory_limit();previous_cache=mx.set_cache_limit(256*2**20 if a.mode=='capped-trim' else limit)
start=time.monotonic();baseline=health();events=[];losses=[];steps=0;cursor=state['cursor'];tokens=state['tokens'];reason='completed'
def sample(stage,**extra):
 h=health();active=mx.get_active_memory();cache=mx.get_cache_memory();r={'stage':stage,'seconds':time.monotonic()-start,'active_bytes':active,'cache_bytes':cache,'allocator_bytes':active+cache,'peak_active_bytes':mx.get_peak_memory(),'swap_mb':h['swap_used_mb'],'thermal':h['thermal_state'],**extra};events.append(r)
 with (out/'events.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
 if active+cache>8*2**30:raise RuntimeError('diagnostic_8GiB_allocator_ceiling')
 if h['swap_used_mb']-baseline['swap_used_mb']>512:raise RuntimeError('diagnostic_512MiB_swap_growth_ceiling')
 if h['thermal_state']>=3:raise RuntimeError('critical_thermal')
 if time.monotonic()-start>180:raise RuntimeError('diagnostic_180_second_ceiling')
arrays=dict(np.load(ROOT/'data/sft-v2/episodes.npz'));order=np.load(ROOT/'data/sft-v2/order.npy')
master=Model(768,12,16384);master.load_weights(str(cp/'model.safetensors'));compute=Model(768,12,16384);compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()));opt=optim.AdamW(1e-5,betas=[.9,.95],weight_decay=.1,bias_correction=True);opt.state=tree_unflatten(list(mx.load(str(cp/'optimizer.npz')).items()));mx.eval(master.parameters(),compute.parameters(),opt.state);grad=nn.value_and_grad(compute,masked_loss)
try:
 sample('loaded')
 for step in range(a.updates):
  batches=[];used=den=0
  while used<8192:
   valid=min(batch_slots(arrays,order,cursor),8192-used);t,m,n,_=batch(arrays,order,cursor,valid);cursor+=2;used+=valid
   if a.mode=='default-fixed':
    pad=513-t.shape[1];t=mx.pad(t,[(0,0),(0,pad)],constant_values=1);m=mx.pad(m,[(0,0),(0,pad)])
   batches.append((t,m,n));den+=n
  acc=None;weighted=0.
  for micro,(t,m,n) in enumerate(batches):
   if not n:continue
   v,g=grad(compute,t,m);g=tree_map(lambda x:x.astype(mx.float32)*(n/den),g);acc=g if acc is None else tree_map(lambda x,y:x+y,acc,g);mx.eval(v,acc);weighted+=float(v)*n
   sample('micro',step=step,micro=micro,width=t.shape[1]-1)
  acc,norm=optim.clip_grad_norm(acc,1.);mx.eval(norm);opt.learning_rate=lr_at(tokens,1e-5);opt.update(master,acc);mx.eval(master.parameters(),opt.state);compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()));mx.eval(compute.parameters());tokens+=8192;steps+=1;losses.append(weighted/den);sample('update',step=step,loss=weighted/den)
except RuntimeError as e:reason=str(e)
pre_clear={'active':mx.get_active_memory(),'cache':mx.get_cache_memory()};mx.clear_cache();post_clear={'active':mx.get_active_memory(),'cache':mx.get_cache_memory()}
assert hashlib.sha256((cp/'model.safetensors').read_bytes()).hexdigest()==original_hash
result={'mode':a.mode,'checkpoint':str(cp),'checkpoint_unchanged':True,'requested_updates':a.updates,'completed_updates':steps,'discarded_diagnostic_input_slots':steps*8192,'reason':reason,'seconds':time.monotonic()-start,'default_memory_limit':limit,'original_cache_limit':previous_cache,'cache_limit':256*2**20 if a.mode=='capped-trim' else limit,'initial_health':baseline,'max_active_bytes':max(e['active_bytes'] for e in events),'max_cache_bytes':max(e['cache_bytes'] for e in events),'max_allocator_bytes':max(e['allocator_bytes'] for e in events),'max_swap_growth_mb':max(e['swap_mb'] for e in events)-baseline['swap_used_mb'],'losses':losses,'before_clear_cache':pre_clear,'after_clear_cache':post_clear,'unique_widths':len({e['width'] for e in events if 'width' in e}),'note':'Diagnostic updates discarded. Production training remains stopped.'}
(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
