"""Explicit-device own GPT-2 training core; not a campaign runner or migrator.

FP32 master weights and moments only. The CPU verification does not establish
Metal performance or mixed-precision stability. Callers own budgets and guards.
"""
import math
import numpy as np
import mlx.core as mx
import mlx.optimizers as optim
from mlx_base import Config, parameter_shapes, parameter_count


def forward(params, token_ids, config, *, device):
    with mx.stream(device):
        batch, length = token_ids.shape
        if not 0 < length <= config.context:
            raise ValueError('sequence length outside trained architecture')
        hidden = params['tokens.weight'][token_ids] + params['positions.weight'][mx.arange(length)]
        def norm(x, name):
            return mx.fast.layer_norm(x,params[name+'.weight'],params[name+'.bias'],1e-5,stream=device)
        def linear(x, name):
            return x @ params[name+'.weight'].T + params[name+'.bias']
        for index in range(config.depth):
            prefix = f'blocks.{index}.'
            projected = linear(norm(hidden,prefix+'before_attention'),prefix+'qkv')
            heads = projected.reshape(batch,length,3,config.heads,config.width//config.heads).transpose(2,0,3,1,4)
            attention = mx.fast.scaled_dot_product_attention(heads[0],heads[1],heads[2],
                            scale=(config.width//config.heads)**-.5,mask='causal',stream=device)
            hidden = hidden + linear(attention.transpose(0,2,1,3).reshape(hidden.shape),prefix+'attention_out')
            x = linear(norm(hidden,prefix+'before_mlp'),prefix+'mlp.0')
            x = .5*x*(1+mx.tanh(math.sqrt(2/math.pi)*(x+.044715*x**3)))
            hidden = hidden + linear(x,prefix+'mlp.2')
        return norm(hidden,'final_norm') @ params['tokens.weight'].T


def causal_loss(params, sequence, config, *, device):
    with mx.stream(device):
        logits = forward(params,sequence[:,:-1],config,device=device)
        target = mx.take_along_axis(logits,sequence[:,1:,None],axis=-1).squeeze(-1)
        return mx.mean(mx.logsumexp(logits,axis=-1)-target)


def accumulated_gradients(params, batches, config, *, device):
    """Normalize by actual target count, including unequal microbatch sizes."""
    if not batches or any(x.ndim!=2 or x.shape[0]<=0 or x.shape[1]<2 for x in batches):
        raise ValueError('nonempty rank-2 microbatches with causal targets required')
    total = sum(x.shape[0]*(x.shape[1]-1) for x in batches)
    with mx.stream(device):
        loss = None; gradients = None
        for batch in batches:
            weight = batch.shape[0]*(batch.shape[1]-1)/total
            value, current = mx.value_and_grad(lambda p: causal_loss(p,batch,config,device=device)*weight)(params)
            loss = value if loss is None else loss+value
            gradients = current if gradients is None else {name:gradients[name]+current[name] for name in gradients}
        return loss, gradients


def clip_gradients(gradients, maximum, *, device):
    with mx.stream(device):
        norm = mx.sqrt(sum(mx.sum(g*g) for g in gradients.values()))
        scale = mx.minimum(mx.array(1.,dtype=mx.float32),maximum/(norm+1e-6))
        return {name:g*scale for name,g in gradients.items()}, norm


class TrainCore:
    def __init__(self, arrays, config, *, device, learning_rate=1e-3, betas=(.9,.95),
                 epsilon=1e-8, matrix_decay=.1, clip=1., compiled=True, restored=None):
        if not (device == mx.cpu or device == mx.gpu):
            raise ValueError('an explicit CPU or GPU device is required')
        if learning_rate <= 0 or not math.isfinite(learning_rate) or epsilon <= 0 or clip <= 0 or matrix_decay < 0:
            raise ValueError('invalid optimizer values')
        shapes = parameter_shapes(config)
        if set(arrays)!=set(shapes):raise ValueError('parameter inventory mismatch')
        for name,shape in shapes.items():
            a=np.asarray(arrays[name])
            if a.shape!=shape or a.dtype!=np.float32 or not np.isfinite(a).all():
                raise ValueError('parameters must be finite architecture-compatible FP32 arrays')
        self.config=config;self.device=device;self.betas=tuple(betas)
        self.epsilon=epsilon;self.matrix_decay=matrix_decay;self.clip=clip
        self.cursor=dict(step=0,trained_tokens=0)
        with mx.stream(device):
            self.params={name:mx.array(value,dtype=mx.float32) for name,value in arrays.items()}
            self.optimizers=[optim.AdamW(learning_rate,betas=betas,eps=epsilon,
                                    weight_decay=decay,bias_correction=True) for decay in (matrix_decay,0.)]
            for index,opt in enumerate(self.optimizers):
                opt.init({n:p for n,p in self.params.items() if (p.ndim>=2)==(index==0)})
            if restored is not None:self._restore(restored)
            self.state=[self.params,*[o.state for o in self.optimizers]]
            mx.eval(self.state)
            self._execute=mx.compile(self._update,inputs=self.state,outputs=self.state) if compiled else self._update

    def _update(self, batches, learning_rate):
        loss,gradients=accumulated_gradients(self.params,batches,self.config,device=self.device)
        clipped,norm=clip_gradients(gradients,self.clip,device=self.device)
        for index,opt in enumerate(self.optimizers):
            opt.state['learning_rate']=learning_rate
            group={n:p for n,p in self.params.items() if (p.ndim>=2)==(index==0)}
            self.params.update(opt.apply_gradients({n:clipped[n] for n in group},group))
        return loss,norm

    def step(self, batches, *, learning_rate):
        if not math.isfinite(learning_rate) or learning_rate<=0:raise ValueError('invalid learning rate')
        with mx.stream(self.device):
            loss,norm=self._execute(batches,mx.array(learning_rate,dtype=mx.float32))
            # Timing must include completed state/loss, not just lazy graph building.
            mx.eval(self.state,loss,norm)
        loss_value,norm_value=float(loss.item()),float(norm.item())
        if not math.isfinite(loss_value) or not math.isfinite(norm_value):
            raise FloatingPointError('nonfinite step: discard updated state and stop the caller')
        self.cursor['step']+=1
        self.cursor['trained_tokens']+=sum(x.shape[0]*(x.shape[1]-1) for x in batches)
        return loss_value,norm_value

    def snapshot(self):
        """Return native optimizer state as NumPy arrays, for tiny feasibility only."""
        mx.eval(self.state)
        arrays={'weight::'+n:np.array(p) for n,p in self.params.items()}
        for index,opt in enumerate(self.optimizers):
            arrays[f'group_step::{index}']=np.array(opt.state['step'])
            arrays[f'group_lr::{index}']=np.array(opt.state['learning_rate'])
            for name in self.params:
                if name in opt.state:
                    for kind in ('m','v'):arrays[kind+'::'+name]=np.array(opt.state[name][kind])
        return dict(cursor=dict(self.cursor),betas=list(self.betas),epsilon=self.epsilon,
                    matrix_decay=self.matrix_decay,clip=self.clip),arrays

    def _restore(self, restored):
        meta,arrays=restored
        if (meta['betas']!=list(self.betas) or meta['epsilon']!=self.epsilon
                or meta['matrix_decay']!=self.matrix_decay or meta['clip']!=self.clip):
            raise ValueError('restored optimizer hyperparameters differ')
        cursor=meta['cursor']
        if type(cursor['step'])!=int or cursor['step']<0 or type(cursor['trained_tokens'])!=int or cursor['trained_tokens']<0:
            raise ValueError('invalid restored cursor')
        expected={kind+'::'+name for name in self.params for kind in ('weight','m','v')}
        expected|={f'group_{field}::{i}' for i in (0,1) for field in ('step','lr')}
        if set(arrays)!=expected:raise ValueError('restored state inventory mismatch')
        for name,p in self.params.items():
            for kind in ('weight','m','v'):
                a=arrays[kind+'::'+name]
                if a.dtype!=np.float32 or a.shape!=p.shape or not np.isfinite(a).all():
                    raise ValueError('invalid restored tensor')
            if not np.array_equal(np.array(p),arrays['weight::'+name]):
                raise ValueError('constructor and restored weights differ')
            if (arrays['v::'+name]<0).any():raise ValueError('negative restored second moment')
        for index,opt in enumerate(self.optimizers):
            step=arrays[f'group_step::{index}'];lr=arrays[f'group_lr::{index}']
            if step.shape!=() or step.dtype!=np.uint64 or int(step)!=cursor['step']:
                raise ValueError('optimizer step differs from cursor')
            if lr.shape!=() or lr.dtype!=np.float32 or not np.isfinite(lr) or float(lr)<=0:
                raise ValueError('invalid restored learning rate')
            state={'step':mx.array(step),'learning_rate':mx.array(lr)}
            for name,p in self.params.items():
                if (p.ndim>=2)==(index==0):
                    state[name]={kind:mx.array(arrays[kind+'::'+name]) for kind in ('m','v')}
            opt.state=state
            opt.init({n:p for n,p in self.params.items() if (p.ndim>=2)==(index==0)})
        self.cursor=dict(cursor)
