"""Bounded random-weight training throughput probe; no corpus or saved weights."""
import argparse,json,time,platform
from pathlib import Path
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten

class Block(nn.Module):
    def __init__(self,d,heads):
        super().__init__();self.heads=heads;self.dim=d//heads
        self.n1=nn.RMSNorm(d);self.n2=nn.RMSNorm(d);self.rope=nn.RoPE(self.dim)
        self.q=nn.Linear(d,d,bias=False);self.k=nn.Linear(d,d,bias=False);self.v=nn.Linear(d,d,bias=False);self.o=nn.Linear(d,d,bias=False)
        self.gate=nn.Linear(d,d*8//3,bias=False);self.up=nn.Linear(d,d*8//3,bias=False);self.down=nn.Linear(d*8//3,d,bias=False)
    def __call__(self,x):
        y=self.n1(x);b,t,d=y.shape
        q,k,v=[f(y).reshape(b,t,self.heads,self.dim).transpose(0,2,1,3) for f in [self.q,self.k,self.v]]
        z=mx.fast.scaled_dot_product_attention(self.rope(q),self.rope(k),v,scale=self.dim**-.5,mask='causal')
        x=x+self.o(z.transpose(0,2,1,3).reshape(b,t,d));y=self.n2(x)
        return x+self.down(nn.silu(self.gate(y))*self.up(y))
class Model(nn.Module):
    def __init__(self,d,layers,vocab):
        super().__init__();self.embed=nn.Embedding(vocab,d);self.layers=[Block(d,d//64) for _ in range(layers)];self.norm=nn.RMSNorm(d)
    def __call__(self,x):
        x=self.embed(x)
        for layer in self.layers:x=layer(x)
        return self.embed.as_linear(self.norm(x))
def main():
    p=argparse.ArgumentParser();p.add_argument('--hidden',type=int,default=512);p.add_argument('--layers',type=int,default=8);p.add_argument('--seconds',type=float,default=60);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert 1<=a.seconds<=600 and a.hidden%64==0
    mx.random.seed(42);model=Model(a.hidden,a.layers,16384);model.set_dtype(mx.bfloat16)
    opt=optim.AdamW(learning_rate=1e-4)
    def loss(m,x,y):return nn.losses.cross_entropy(m(x).astype(mx.float32),y).mean()
    grad=nn.value_and_grad(model,loss); batch=2;seq=512
    def step():
        tokens=mx.random.randint(0,16384,(batch,seq+1));v,g=grad(model,tokens[:,:-1],tokens[:,1:]);opt.update(model,g);mx.eval(v,model.parameters(),opt.state);return float(v)
    for _ in range(3):step()
    start=time.monotonic();n=0;first=None
    while time.monotonic()-start<a.seconds:
        value=step();n+=1
        if first is None:first=value
    seconds=time.monotonic()-start
    result={'kind':'synthetic_random_weight_training_probe_not_quality_test','parameters':sum(v.size for _,v in tree_flatten(model.parameters())),'hidden':a.hidden,'layers':a.layers,'vocab':16384,'batch':batch,'sequence':seq,'dtype':'bfloat16','measured_steps':n,'seconds':seconds,'tokens_per_second':n*batch*seq/seconds,'first_loss':first,'last_loss':value,'peak_memory_bytes':mx.get_peak_memory(),'platform':platform.platform(),'caveats':['Short probe: not thermally sustained throughput.','Random tokens, no data I/O or checkpoint overhead.','Standard multi-head attention, not final GQA recipe.','No pretrained weights, data download, or cloud use.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
