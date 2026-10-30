"""One isolated real-data update; never modifies the retained 100M checkpoint."""
import hashlib,json,tempfile
from pathlib import Path
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_map,tree_flatten,tree_unflatten
from benchmark_mlx import Model
from train_local import loss,save_checkpoint,atomic_json
from train_continuation import FreshCorpus

def main():
    root=Path(__file__).resolve().parents[1];pilot=root/'runs/local-campaign-v1/pilot'
    source=pilot/json.loads((pilot/'latest.json').read_text())['directory']
    before=hashlib.sha256((source/'model.safetensors').read_bytes()).hexdigest()
    original=json.loads((source/'state.json').read_text())
    master=Model(768,12,16384);master.load_weights(str(source/'model.safetensors'))
    compute=Model(768,12,16384);compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()))
    opt=optim.AdamW(3e-5,betas=[.9,.95],weight_decay=.1,bias_correction=True)
    opt.state=tree_unflatten(list(mx.load(str(source/'optimizer.npz')).items()));mx.eval(opt.state)
    assert int(opt.step)==original['steps']
    corpus=FreshCorpus(root/'data/continuation-v1');grad=nn.value_and_grad(compute,loss);acc=None;values=[]
    for _ in range(8):
        v,g=grad(compute,corpus.batch(),1024);g=tree_map(lambda x:x.astype(mx.float32)/8,g)
        acc=g if acc is None else tree_map(lambda x,y:x+y,acc,g);mx.eval(v,acc);values.append(float(v))
    acc,norm=optim.clip_grad_norm(acc,1.);opt.update(master,acc);mx.eval(master.parameters(),opt.state,norm)
    assert int(opt.step)==original['steps']+1
    with tempfile.TemporaryDirectory(dir=root/'runs/continuation-v1') as tmp:
        p=Path(tmp);save_checkpoint(p,master,opt,{'tokens':100008192,'fresh_corpus':corpus.state()})
        saved=p/json.loads((p/'latest.json').read_text())['directory']
        weights=mx.load(str(saved/'model.safetensors'))
        for name,v in tree_flatten(master.parameters()):assert bool(mx.array_equal(v,weights[name]))
        restored=mx.load(str(saved/'optimizer.npz'))
        for name,v in tree_flatten(opt.state):assert bool(mx.array_equal(v,restored[name]))
        c2=FreshCorpus(root/'data/continuation-v1',json.loads((saved/'state.json').read_text())['fresh_corpus'])
        assert bool(mx.array_equal(corpus.batch(),c2.batch()))
    assert hashlib.sha256((source/'model.safetensors').read_bytes()).hexdigest()==before
    atomic_json(root/'reports/continuation-v1/smoke.json',{'passed':True,'original_tokens':original['tokens'],'original_optimizer_step':original['steps'],'smoke_optimizer_step':int(opt.step),'isolated_update_tokens':8192,'loss':sum(values)/8,'gradient_norm':float(norm),'checkpoint_weights_and_optimizer_exact':True,'next_batch_after_resume_exact':True,'original_checkpoint_unchanged':True})
    print('Real-data checkpoint/optimizer/resume smoke passed',flush=True)

if __name__=='__main__':main()
