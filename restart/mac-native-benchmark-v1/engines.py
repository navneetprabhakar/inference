"""Reference MPS and Apple MLX-LM engines. No training loop lives here."""
import copy
import math
import sys
import time
import numpy as np
from support import UPSTREAM,mapping,moments,origin,rate,GIB

class TorchEngine:
    def __init__(self,micro=16):
        import torch
        sys.path.insert(0,str(UPSTREAM))
        from model import ModelArgs,Transformer
        self.torch=torch;torch.set_num_threads(4)
        self.origin=origin();self.micro=micro;self.base_step=self.origin['optimizer_step'];self.local_step=0
        self.model=Transformer(ModelArgs(**self.origin['model_args'])).to('mps')
        self.model.load_state_dict(self.origin['model'],strict=True)
        self.optimizer=self.model.configure_optimizers(.1,.0005,(.9,.95),'mps')
        self.optimizer.load_state_dict(self.origin['optimizer'])
        self.model.train();self.peak_driver=0
    def sync(self):self.torch.mps.synchronize()
    def memory(self):
        n=self.torch.mps.driver_allocated_memory();self.peak_driver=max(self.peak_driver,n)
        if n>12*GIB:raise RuntimeError('GPU_MEMORY_CAP')
        return dict(active_bytes=self.torch.mps.current_allocated_memory(),active_plus_cache_bytes=n,peak_active_or_driver_bytes=self.peak_driver)
    def validation(self,a):
        t=self.torch;self.model.eval()
        with t.no_grad():
            x=t.from_numpy(a[:,:-1].astype(np.int64)).to('mps');y=t.from_numpy(a[:,1:].astype(np.int64)).to('mps')
            self.model(x,y);v=float(self.model.last_loss)
        self.model.train();return v
    def gradient(self,a):
        t=self.torch;self.optimizer.zero_grad(set_to_none=True)
        x=t.from_numpy(a[:,:-1].astype(np.int64)).to('mps');y=t.from_numpy(a[:,1:].astype(np.int64)).to('mps')
        self.model(x,y);loss=self.model.last_loss;loss.backward();self.sync()
        return float(loss),{mapping()[n]:p.grad.detach().cpu().numpy().copy() for n,p in self.model.named_parameters()}
    def apply_gradients(self,grads):
        t=self.torch
        for n,p in self.model.named_parameters():p.grad=t.from_numpy(grads[mapping()[n]]).to('mps')
        norm=t.nn.utils.clip_grad_norm_(self.model.parameters(),1.0)
        for group in self.optimizer.param_groups:group['lr']=rate(self.base_step+self.local_step)
        self.optimizer.step();self.sync();self.local_step+=1
        return float(norm)
    def update(self,a,check):
        t=self.torch;self.optimizer.zero_grad(set_to_none=True);loss_total=t.zeros((),device='mps')
        accum=len(a)//self.micro
        if len(a)%self.micro:raise ValueError('Nonuniform microbatch')
        for index in range(0,len(a),self.micro):
            check()
            part=a[index:index+self.micro]
            x=t.from_numpy(part[:,:-1].astype(np.int64)).to('mps',non_blocking=True)
            y=t.from_numpy(part[:,1:].astype(np.int64)).to('mps',non_blocking=True)
            self.model(x,y);loss=self.model.last_loss/accum
            loss_total=loss_total+loss.detach();loss.backward()
        norm=t.nn.utils.clip_grad_norm_(self.model.parameters(),1.0)
        for group in self.optimizer.param_groups:group['lr']=rate(self.base_step+self.local_step)
        self.optimizer.step();self.sync();self.local_step+=1
        loss=float(loss_total);norm=float(norm)
        if not math.isfinite(loss) or not math.isfinite(norm):raise RuntimeError('NONFINITE_UPDATE')
        return loss,norm
    def weights(self):return {mapping()[n]:p.detach().cpu().numpy().copy() for n,p in self.model.named_parameters()}
    def checkpoint(self):
        t=self.torch
        def cpu(v):
            if isinstance(v,t.Tensor):return v.detach().cpu()
            if isinstance(v,dict):return {k:cpu(x) for k,x in v.items()}
            if isinstance(v,list):return [cpu(x) for x in v]
            return v
        state={**self.origin,'model':cpu(self.model.state_dict()),'optimizer':cpu(self.optimizer.state_dict())}
        return state

class MLXEngine:
    def __init__(self,precision='fp32',micro=16):
        import mlx.core as mx
        import mlx.nn as nn
        import mlx.optimizers as optim
        from mlx.utils import tree_unflatten
        from mlx_lm.models.llama import Model,ModelArgs
        from functools import partial
        self.mx=mx;self.nn=nn;self.precision=precision;self.micro=micro;self.local_step=0
        self.origin=origin();self.base_step=self.origin['optimizer_step']
        mx.set_cache_limit(512*1024**2);mx.set_memory_limit(12*GIB)
        self.dtype={'fp32':mx.float32,'bf16':mx.bfloat16,'fp16':mx.float16}[precision]
        self.scale=128.0 if precision=='fp16' else 1.0
        self.model=Model(ModelArgs(model_type='llama',hidden_size=288,num_hidden_layers=6,
             intermediate_size=768,num_attention_heads=6,num_key_value_heads=6,rms_norm_eps=1e-5,
             vocab_size=32000,max_position_embeddings=256,rope_traditional=True,tie_word_embeddings=True))
        self.params={new:mx.array(self.origin['model'][old].numpy(),dtype=mx.float32) for old,new in mapping().items()}
        if sum(v.size for v in self.params.values())!=15191712:raise RuntimeError('Architecture changed')
        states=moments(self.origin)
        self.matrix=[k for k,v in self.params.items() if v.ndim>=2];self.norm=[k for k,v in self.params.items() if v.ndim==1]
        self.om=optim.AdamW(.0005,betas=[.9,.95],eps=1e-8,weight_decay=.1,bias_correction=True)
        self.on=optim.AdamW(.0005,betas=[.9,.95],eps=1e-8,weight_decay=0.,bias_correction=True)
        for opt,names in [(self.om,self.matrix),(self.on,self.norm)]:
            opt.init({k:self.params[k] for k in names});opt.state['step']=mx.array(self.base_step,mx.uint64)
            for k in names:
                opt.state[k]['m']=mx.array(states[k]['m'],dtype=mx.float32)
                opt.state[k]['v']=mx.array(states[k]['v'],dtype=mx.float32)
        mx.eval(self.params,self.om.state,self.on.state)
        def loss_fn(params,x,y):
            # RMSNorm promotes its result to the weight dtype. Cast its compute
            # view too; native RMSNorm still accumulates its reduction in FP32.
            # FP32 master parameters and optimizer moments remain untouched.
            compute=[(k,v.astype(self.dtype)) for k,v in params.items()]
            self.model.update(tree_unflatten(compute))
            logits=self.model(x)
            return nn.losses.cross_entropy(logits.astype(mx.float32),y,reduction='mean')*self.scale
        self.loss_fn=mx.compile(loss_fn)
        self.grad_fn=mx.compile(mx.value_and_grad(loss_fn))
        @mx.compile
        def accumulate(acc,grad):return {k:acc[k]+grad[k].astype(mx.float32)/self.scale for k in acc}
        self.accumulate=accumulate
        capture=[self.om.state,self.on.state]
        @partial(mx.compile,inputs=capture,outputs=capture)
        def step(params,grad,lr):
            norm=mx.sqrt(sum(mx.sum(mx.square(v)) for v in grad.values()))
            factor=mx.minimum(mx.array(1.),mx.array(1.)/(norm+1e-6))
            grad={k:g*factor for k,g in grad.items()}
            self.om.learning_rate=lr;self.on.learning_rate=lr
            out={**self.om.apply_gradients({k:grad[k] for k in self.matrix},{k:params[k] for k in self.matrix}),
                 **self.on.apply_gradients({k:grad[k] for k in self.norm},{k:params[k] for k in self.norm})}
            return out,norm
        self.step_fn=step;self.peak_active_plus_cache=0
        # Audit graph dtypes without evaluating an extra model forward.
        self.model.update(tree_unflatten([(k,v.astype(self.dtype)) for k,v in self.params.items()]))
        audit_tokens=mx.zeros((1,256),dtype=mx.int32)
        embedding=self.model.model.embed_tokens(audit_tokens)
        normalized=self.model.model.layers[0].input_layernorm(embedding)
        projected=self.model.model.layers[0].self_attn.q_proj(normalized)
        logits=self.model(audit_tokens)
        self.dtype_proof=dict(compute=str(self.dtype),embedding=str(embedding.dtype),
            norm_output=str(normalized.dtype),matrix_weight=str(self.model.model.layers[0].self_attn.q_proj.weight.dtype),
            matrix_output=str(projected.dtype),logits=str(logits.dtype),master_weights=str(next(iter(self.params.values())).dtype),
            optimizer_moment=str(self.om.state[self.matrix[0]]['m'].dtype),audit_forward_evaluated=False,
            normalization_reduction='Native MLX RMSNorm FP32 accumulation')
        if any(value!=str(self.dtype) for key,value in self.dtype_proof.items() if key in ['embedding','norm_output','matrix_weight','matrix_output','logits']):
            raise RuntimeError('COMPUTE_DTYPE_PROMOTION')
    def sync(self):self.mx.synchronize()
    def memory(self):
        mx=self.mx;n=mx.get_active_memory()+mx.get_cache_memory();self.peak_active_plus_cache=max(self.peak_active_plus_cache,n)
        peak=mx.get_peak_memory()
        if n>12*GIB or peak>12*GIB:raise RuntimeError('GPU_MEMORY_CAP')
        return dict(active_bytes=mx.get_active_memory(),active_plus_cache_bytes=n,peak_active_or_driver_bytes=max(peak,self.peak_active_plus_cache))
    def validation(self,a):
        mx=self.mx;v=self.loss_fn(self.params,mx.array(a[:,:-1]),mx.array(a[:,1:]))/self.scale
        mx.eval(v);self.memory();return float(v)
    def gradient(self,a):
        mx=self.mx;v,g=self.grad_fn(self.params,mx.array(a[:,:-1]),mx.array(a[:,1:]))
        g={k:x.astype(mx.float32)/self.scale for k,x in g.items()};mx.eval(v,g);self.memory()
        return float(v)/self.scale,{k:np.array(x) for k,x in g.items()}
    def apply_gradients(self,g):
        mx=self.mx;grad={k:mx.array(v,dtype=mx.float32) for k,v in g.items()}
        self.params,norm=self.step_fn(self.params,grad,mx.array(rate(self.base_step+self.local_step)))
        mx.eval(self.params,self.om.state,self.on.state,norm);self.local_step+=1
        return float(norm)
    def update(self,a,check):
        mx=self.mx;acc={k:mx.zeros_like(v) for k,v in self.params.items()};loss_total=mx.array(0.,dtype=mx.float32)
        accum=len(a)//self.micro
        if len(a)%self.micro:raise ValueError('Nonuniform microbatch')
        for index in range(0,len(a),self.micro):
            check();part=a[index:index+self.micro]
            loss,g=self.grad_fn(self.params,mx.array(part[:,:-1]),mx.array(part[:,1:]))
            acc=self.accumulate(acc,g);loss_total=loss_total+loss/self.scale
            mx.eval(acc,loss_total);self.memory()
        acc={k:g/accum for k,g in acc.items()}
        self.params,norm=self.step_fn(self.params,acc,mx.array(rate(self.base_step+self.local_step)))
        mx.eval(self.params,self.om.state,self.on.state,norm,loss_total);self.local_step+=1
        value=float(loss_total)/accum;norm=float(norm)
        if not math.isfinite(value) or not math.isfinite(norm):raise RuntimeError('NONFINITE_UPDATE')
        return value,norm
    def weights(self):
        self.mx.eval(self.params)
        return {k:np.array(v) for k,v in self.params.items()}
    def checkpoint(self):
        import torch
        state=copy.deepcopy(self.origin)
        for old,new in mapping().items():state['model'][old]=torch.from_numpy(np.array(self.params[new]))
        state['model']['output.weight']=state['model']['tok_embeddings.weight']
        names=[k for k in state['model'] if k!='output.weight']
        for group in state['optimizer']['param_groups']:
            selected=[k for k in names if (state['model'][k].ndim>=2)==(group['weight_decay']>0)]
            opt=self.om if group['weight_decay'] else self.on
            group['lr']=rate(self.base_step+self.local_step-1)
            for key,index in zip(selected,group['params']):
                item=opt.state[mapping()[key]]
                state['optimizer']['state'][index]=dict(step=torch.tensor(float(self.base_step+self.local_step)),
                    exp_avg=torch.from_numpy(np.array(item['m'])),exp_avg_sq=torch.from_numpy(np.array(item['v'])))
        self.mx.eval(self.mx.random.state)
        state['mlx_rng_state']=[np.array(x) for x in self.mx.random.state]
        state['compute_precision']=self.precision
        return state
