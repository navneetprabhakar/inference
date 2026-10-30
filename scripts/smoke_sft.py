"""One isolated real masked-gradient update; no experiment/base files overwritten."""
import hashlib,json,tempfile
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_map,tree_flatten
from benchmark_mlx import Model
from sft_common import ROOT,masked_loss
from train_sft import batch
from train_local import atomic_json,save_checkpoint
p=ROOT/'runs/continuation-v1/200m';cp=p/json.loads((p/'latest.json').read_text())['directory'];before=hashlib.sha256((cp/'model.safetensors').read_bytes()).hexdigest();a=dict(np.load(ROOT/'data/sft-v2/episodes.npz'));order=np.load(ROOT/'data/sft-v2/order.npy')
master=Model(768,12,16384);master.load_weights(str(cp/'model.safetensors'));compute=Model(768,12,16384);compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()));opt=optim.AdamW(1e-5,betas=[.9,.95],weight_decay=.1,bias_correction=True);grad=nn.value_and_grad(compute,masked_loss)
batches=[batch(a,order,i*2,1024) for i in range(8)];den=sum(x[2] for x in batches);acc=None;weighted=0
for t,m,n,_ in batches:
 v,g=grad(compute,t,m);g=tree_map(lambda x:x.astype(mx.float32)*n/den,g);acc=g if acc is None else tree_map(lambda x,y:x+y,acc,g);mx.eval(v,acc);weighted+=float(v)*n
acc,norm=optim.clip_grad_norm(acc,1.);opt.update(master,acc);mx.eval(master.parameters(),opt.state,norm);assert int(opt.step)==1 and bool(mx.isfinite(norm))
with tempfile.TemporaryDirectory(dir=ROOT/'runs/sft-v2') as tmp:
 out=Path(tmp);save_checkpoint(out,master,opt,{'tokens':sum(x[0].shape[0]*(x[0].shape[1]-1) for x in batches),'cursor':16});saved=out/json.loads((out/'latest.json').read_text())['directory'];w=mx.load(str(saved/'model.safetensors'));o=mx.load(str(saved/'optimizer.npz'))
 for k,v in tree_flatten(master.parameters()):assert bool(mx.array_equal(v,w[k]))
 for k,v in tree_flatten(opt.state):assert bool(mx.array_equal(v,o[k]))
assert hashlib.sha256((cp/'model.safetensors').read_bytes()).hexdigest()==before
atomic_json(ROOT/'reports/sft-v2/smoke.json',{'passed':True,'isolated_input_tokens':sum(x[0].shape[0]*(x[0].shape[1]-1) for x in batches),'supervised_targets':den,'masked_loss':weighted/den,'gradient_norm':float(norm),'fresh_optimizer_step':int(opt.step),'base_checkpoint_unchanged':True,'saved_weights_and_optimizer_exact':True,'note':'Single-update integration check, not a memorization or generalization claim.'});print('SFT smoke passed',flush=True)
