"""Thin native-state binding for sequential disposable experiments; no controller."""
from copy import deepcopy
import hashlib
import numpy as np
import mlx_own_base_adapter as bridge

class SequentialNative(bridge.DisposableCore):
 def __init__(self,meta,arrays,*,pinned,benchmark_identity,device,boundary=None,compiled=True):
  from mlx_sequential_train_core import SequentialTrainCore
  from mlx_train_core import Config
  cfg,cm,native,self.provenance=bridge.convert_neutral(meta,arrays,pinned=pinned)
  self.identity=deepcopy(benchmark_identity);self.source_meta=deepcopy(meta);self.rng={n:arrays[n].copy()for n in ('cpu_rng','mps_rng')}
  p=meta['progress'];self.progress=dict(committed_updates=0,committed_targets=0,source_offset=p['source_offset'],optimizer_step=p['optimizer_step'])
  self.core=SequentialTrainCore({n:native['weight::'+n]for n in meta['parameter_order']},Config(**cfg),device=device,boundary=boundary,compiled=compiled,learning_rate=float(native['group_lr::0']),betas=tuple(cm['betas']),epsilon=cm['epsilon'],matrix_decay=cm['matrix_decay'],clip=cm['clip'],restored=(cm,native))
 @classmethod
 def from_native(cls,meta,arrays,*,benchmark_identity,source_provenance,device,boundary=None,compiled=True):
  from mlx_sequential_train_core import SequentialTrainCore
  from mlx_train_core import Config
  bridge.validate_native(meta,arrays,benchmark_identity=benchmark_identity,source_provenance=source_provenance)
  obj=cls.__new__(cls);obj.identity=deepcopy(benchmark_identity);obj.provenance=deepcopy(source_provenance);obj.source_meta=deepcopy(source_provenance['source_neutral']);obj.progress=dict(meta['benchmark_progress']);obj.rng={n:arrays[n].copy()for n in ('cpu_rng','mps_rng')};cm=meta['core'];state={n:v for n,v in arrays.items()if n not in obj.rng}
  obj.core=SequentialTrainCore({n:arrays['weight::'+n]for n in obj.source_meta['parameter_order']},Config(**obj.source_meta['identity']['model']),device=device,boundary=boundary,compiled=compiled,learning_rate=float(arrays['group_lr::0']),betas=tuple(cm['betas']),epsilon=cm['epsilon'],matrix_decay=cm['matrix_decay'],clip=cm['clip'],restored=(cm,state));return obj
 def digest_state(self,check=lambda:None):
  if self.core.poisoned:raise RuntimeError('poisoned core cannot publish digest')
  import mlx.core as mx
  mx.eval(self.core.state);arrays={}
  def add(name,value):
   check();a=np.array(value,copy=True,order="C");h=hashlib.sha256();raw=memoryview(a).cast('B')
   for start in range(0,len(raw),1024**2):h.update(raw[start:start+1024**2]);check()
   arrays[name]=dict(dtype=str(a.dtype),shape=list(a.shape),sha256=h.hexdigest())
  for name,param in self.core.params.items():
   add('weight::'+name,param);group=self.core.optimizers[0 if param.ndim>=2 else 1]
   for kind in ('m','v'):add(kind+'::'+name,group.state[name][kind])
  for i,opt in enumerate(self.core.optimizers):
   for key in ('step','learning_rate'):add(f'group_{"step" if key=="step" else "lr"}::{i}',opt.state[key])
  for name,a in self.rng.items():add(name,a)
  cm=dict(cursor=dict(self.core.cursor),betas=list(self.core.betas),epsilon=self.core.epsilon,matrix_decay=self.core.matrix_decay,clip=self.core.clip)
  return dict(metadata=dict(schema=1,benchmark_identity=self.identity,source_provenance=self.provenance,benchmark_progress=dict(self.progress),core=cm),arrays=arrays)
