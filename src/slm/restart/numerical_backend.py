"""Budgeted numerical-suite operations on already-authorized supplied parameters.

No initializer/checkpoint loader or training-permission bypass is provided.
"""
import time
import numpy as np
from .numerical_budget import perform

class NumericalBackend:
    def __init__(self,name,params,config,budget,*,clock=time.time):
        if name not in ('mlx','torch'):raise ValueError('Unsupported numerical backend')
        self.name=name;self.params=params;self.config=config;self.budget=budget;self.clock=clock
        if name=='mlx':
            import mlx.core as mx
            from slm.backends import mlx_backend
            self.module=mx;self.impl=mlx_backend
        else:
            import torch
            from slm.backends import torch_backend
            self.module=torch;self.impl=torch_backend

    def _array(self,value):
        a=np.asarray(value)
        if self.name=='mlx':return self.module.array(a)
        return self.module.as_tensor(a)

    def _export(self,value):
        if self.name=='mlx':
            self.module.eval(value);result=np.array(value)
        else:result=value.detach().cpu().numpy().copy()
        if not np.isfinite(result).all():raise ValueError('Nonfinite numerical backend result')
        return result

    def _run(self,kind,positions,operation):
        if type(positions) is not int or positions<1:raise ValueError('Exact positive work-position count required')
        # Persistent ordinal includes unfinished work, so IDs are not reused on reopen.
        number=len(self.budget.events(require_complete=False))+1
        return perform(self.budget,f'{self.name}:{number}:{kind}',backend=self.name,kind=kind,
            positions=positions,now=self.clock(),operation=operation,settle=lambda value:None)
        # Each operation below exports/evaluates all results inside the charged call.

    def forward(self,tokens,*,padding_mask=None,cache=None):
        values=np.asarray(tokens,dtype=np.int32)
        def operation():
            mask=None if padding_mask is None else self._array(np.asarray(padding_mask,dtype=bool))
            if self.name=='torch':
                with self.module.no_grad():out,cached,traces=self.impl.forward(self.params,self.config,self._array(values),mask,cache)
            else:out,cached,traces=self.impl.forward(self.params,self.config,self._array(values),mask,cache)
            exported=self._export(out);layers=[self._export(x) for x in traces]
            if self.name=='mlx':self.module.eval(cached)
            return exported,cached,layers
        return self._run('forward',values.size,operation)

    def gradient(self,batch,*,embedding_implementation='native-gather-v1'):
        x=np.asarray(batch['inputs'],dtype=np.int32)
        def operation():
            values=[self._array(a) for a in (x,np.asarray(batch['targets'],dtype=np.int32),np.asarray(batch['loss_mask'],dtype=np.float32))]
            padding=self._array(np.asarray(batch['padding_mask'],dtype=bool))
            value,g=self.impl.value_and_grad(self.params,self.config,*values,padding_mask=padding,
                loss_implementation=self.impl.STABLE_LOSS_IMPLEMENTATION,embedding_implementation=embedding_implementation)
            exported=self.impl.export(g)
            if any(not np.isfinite(v).all() for v in exported.values()):raise ValueError('Nonfinite numerical gradient')
            return float(self._export(value)),exported
        return self._run('gradient',x.size,operation)

    def cross_entropy(self,logits,targets):
        x=np.asarray(logits,dtype=np.float32);y=np.asarray(targets,dtype=np.int32)
        def operation():
            labels=self._array(y)
            if self.name=='mlx':
                value,g=self.module.value_and_grad(lambda a:self.module.mean(self.impl.cross_entropy_logits(a,labels)))(self._array(x))
            else:
                values=self._array(x).clone().requires_grad_(True)
                value=self.impl.cross_entropy_logits(values,labels).mean();g=self.module.autograd.grad(value,values)[0]
            return float(self._export(value)),self._export(g)
        return self._run('ce_gradient',y.size,operation)

    def tied_embedding(self,batch):
        x=np.asarray(batch['inputs'],dtype=np.int32)
        def operation():
            tokens=self._array(x);targets=self._array(np.asarray(batch['targets'],np.int32))
            mask=self._array(np.asarray(batch['loss_mask'],np.float32));padding=self._array(np.asarray(batch['padding_mask'],bool))
            def loss(embedding,path):
                weights=dict(self.params);weights['embedding']=embedding
                logits,_,traces=self.impl.forward(weights,self.config,tokens,padding_mask=padding)
                if path!='full':
                    residual=traces[-1]
                    if self.name=='mlx':
                        hidden=residual*self.module.rsqrt(self.module.mean(self.module.square(residual),axis=-1,keepdims=True)+self.config.norm_eps)*weights['final_norm']
                        hidden=self.module.stop_gradient(hidden) if path=='output' else hidden
                        head=self.module.stop_gradient(embedding) if path=='input' else embedding
                    else:
                        hidden=residual*self.module.rsqrt(residual.square().mean(-1,keepdim=True)+self.config.norm_eps)*weights['final_norm']
                        hidden=hidden.detach() if path=='output' else hidden
                        head=embedding.detach() if path=='input' else embedding
                    logits=hidden@head.T
                per=self.impl.cross_entropy_logits(logits,targets)
                return (per*mask).sum()/mask.sum()
            gradients=[]
            for path in ('full','input','output'):
                if self.name=='mlx':g=self.module.grad(lambda e:loss(e,path))(self.params['embedding'])
                else:g=self.module.autograd.grad(loss(self.params['embedding'],path),self.params['embedding'])[0]
                gradients.append(self._export(g))
            return tuple(gradients)
        return self._run('gradient',3*x.size,operation)

    def loss64(self,batch,name,index,replacement):
        if self.name!='torch':raise ValueError('FP64 oracle requires CPU PyTorch')
        x=np.asarray(batch['inputs'],dtype=np.int32)
        def operation():
            # Clone every tensor; never mutate or retag the supplied FP32 state.
            weights={k:v.detach().to(dtype=self.module.float64).clone() for k,v in self.params.items()}
            if name not in weights or not np.isfinite(replacement):raise ValueError('Invalid finite-difference coordinate')
            weights[name][index]=replacement
            tokens=self._array(x);targets=self._array(np.asarray(batch['targets'],np.int64))
            mask=self.module.as_tensor(batch['loss_mask'],dtype=self.module.float64)
            padding=self._array(np.asarray(batch['padding_mask'],bool))
            with self.module.no_grad():
                logits,_,_=self.impl.forward(weights,self.config,tokens,padding_mask=padding)
                # Independent native CE oracle, rather than the custom loss formula.
                per=self.module.nn.functional.cross_entropy(logits.reshape(-1,logits.shape[-1]),targets.reshape(-1),reduction='none').reshape(targets.shape)
                value=(per*mask).sum()/mask.sum()
            return float(self._export(value))
        return self._run('fp64_loss',x.size,operation)

    def optimize(self,gradients,moments,*,step,positions):
        """Fixed toy recipe; gradients are exported arrays from charged computation."""
        def operation():
            if type(step) is not int or not 1<=step<=8:raise ValueError('Toy trajectory step outside fixed plan')
            before=self.impl.export(self.params)
            if set(gradients)!=set(before):raise ValueError('Incomplete optimizer gradients')
            for key,g in gradients.items():
                a=np.asarray(g)
                if a.shape!=before[key].shape or a.dtype!=np.float32 or not np.isfinite(a).all():
                    raise ValueError('Invalid optimizer gradient')
            def export_moments(state):
                return {k:tuple(self._export(v) for v in pair) for k,pair in state.items()}
            old=export_moments(moments)
            proposed,new_moments=self.impl.adamw(self.params,{k:self._array(v) for k,v in gradients.items()},moments,step,.02,
                beta1=.9,beta2=.95,eps=1e-8,decay=.1,clip=1.)
            after={k:self._export(v) for k,v in proposed.items()};new=export_moments(new_moments)
            if set(after)!=set(before) or set(new)!=set(before):raise ValueError('Optimizer inventory changed')
            for k in before:
                if after[k].shape!=before[k].shape or after[k].dtype!=np.float32 or len(new[k])!=2:
                    raise ValueError('Invalid optimizer state')
                if any(v.shape!=before[k].shape or v.dtype!=np.float32 for v in new[k]) or np.any(new[k][1]<0):
                    raise ValueError('Invalid optimizer moments')
            record={'step':step,'lr':.02,'before':before,'gradients':{k:np.array(v,copy=True) for k,v in gradients.items()},
                    'moments_before':old,'after':after,'moments_after':new}
            return proposed,new_moments,record
        params,new_moments,capture=self._run('optimizer',positions,operation)
        self.params=params
        return new_moments,capture
