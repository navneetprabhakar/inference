"""Freeze a declared feature stack; inference architecture remains unchanged."""
import hashlib
import numpy as np
from mlx.utils import tree_flatten

def apply_freeze(model, lower_layers, embeddings):
 if type(lower_layers) is not int or not 0 <= lower_layers < len(model.layers):
  raise ValueError('Invalid frozen lower-layer count')
 if type(embeddings) is not bool:raise ValueError('freeze_embeddings must be boolean')
 if embeddings:model.embed.freeze()
 for layer in model.layers[:lower_layers]:layer.freeze()
 trainable=dict(tree_flatten(model.trainable_parameters()))
 total=dict(tree_flatten(model.parameters()))
 frozen=sorted(set(total)-set(trainable))
 return {'trainable_parameters':sum(v.size for v in trainable.values()),'frozen_parameters':sum(total[k].size for k in frozen),'frozen_keys':frozen}

def frozen_digest(model, keys):
 tensors=dict(tree_flatten(model.parameters()));h=hashlib.sha256()
 for k in keys:
  a=np.array(tensors[k]);h.update(k.encode());h.update(str(a.dtype).encode());h.update(str(a.shape).encode());h.update(a.tobytes())
 return h.hexdigest()
