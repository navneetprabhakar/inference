"""Sequentially materialized FP32 accumulation. Explicit device; no controller.

A failed boundary poisons this instance. Restore an accepted boundary in a fresh
instance rather than snapshotting or resuming a partially observed update.
"""
import math
import mlx.core as mx
from mlx_train_core import TrainCore,causal_loss,clip_gradients


def check_memory(*,active,peak,cache,rss,gpu_limit=12*1024**3,cache_limit=1024**3,rss_limit=18*1024**3):
    """Pure prospective guard; telemetry collection is the caller's responsibility."""
    for name,value in dict(active=active,peak=peak,cache=cache,rss=rss).items():
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:
            raise RuntimeError('missing/nonfinite memory telemetry: '+name)
    if active>=gpu_limit or peak>=gpu_limit or cache>cache_limit or rss>rss_limit:
        raise RuntimeError('sequential memory ceiling exceeded')


class SequentialTrainCore(TrainCore):
    def __init__(self,arrays,config,*,device,compiled=True,boundary=None,**kwargs):
        if device==mx.gpu and boundary is None:
            raise ValueError('GPU requires explicit synchronized resource-boundary callback')
        super().__init__(arrays,config,device=device,compiled=False,**kwargs)
        self.boundary=boundary;self.poisoned=False
        # Parameters are explicit inputs, and weight/LR are scalar array values.
        one=mx.value_and_grad(lambda params,batch,weight:causal_loss(params,batch,self.config,device=self.device)*weight)
        self._micro=mx.compile(one) if compiled else one
        self._apply=mx.compile(self._apply_update,inputs=self.state,outputs=self.state) if compiled else self._apply_update

    def _apply_update(self,gradients,learning_rate):
        clipped,norm=clip_gradients(gradients,self.clip,device=self.device)
        for index,opt in enumerate(self.optimizers):
            opt.state['learning_rate']=learning_rate
            group={n:p for n,p in self.params.items() if (p.ndim>=2)==(index==0)}
            self.params.update(opt.apply_gradients({n:clipped[n] for n in group},group))
        return norm

    def _boundary(self,stage,index):
        if self.boundary is not None:self.boundary(stage,index)

    def step(self,batches,*,learning_rate):
        if self.poisoned:raise RuntimeError('failed sequential instance requires fresh accepted restore')
        if not math.isfinite(learning_rate) or learning_rate<=0:raise ValueError('invalid learning rate')
        if not batches or any(x.ndim!=2 or x.shape[0]<=0 or x.shape[1]<2 for x in batches):
            raise ValueError('nonempty rank-2 microbatches with causal targets required')
        total=sum(x.shape[0]*(x.shape[1]-1) for x in batches)
        try:
            with mx.stream(self.device):
                loss=None;accumulator=None
                for index,batch in enumerate(batches):
                    weight=mx.array(batch.shape[0]*(batch.shape[1]-1)/total,dtype=mx.float32)
                    value,current=self._micro(self.params,batch,weight)
                    loss=value if loss is None else loss+value
                    accumulator=current if accumulator is None else {n:accumulator[n]+current[n] for n in accumulator}
                    # Outside compilation: complete this graph before constructing another.
                    mx.eval(accumulator,loss)
                    del current,value,weight
                    self._boundary('microbatch',index)
                self._boundary('before_optimizer',len(batches))
                norm=self._apply(accumulator,mx.array(learning_rate,dtype=mx.float32))
                mx.eval(self.state,loss,norm)
                del accumulator
                self._boundary('after_optimizer',len(batches))
                loss_value,norm_value=float(loss.item()),float(norm.item())
                if not math.isfinite(loss_value) or not math.isfinite(norm_value):
                    raise FloatingPointError('nonfinite sequential update')
            self.cursor['step']+=1;self.cursor['trained_tokens']+=total
            return loss_value,norm_value
        except BaseException:
            self.poisoned=True
            raise

    def snapshot(self):
        if self.poisoned:raise RuntimeError('cannot publish partially observed sequential update')
        return super().snapshot()
