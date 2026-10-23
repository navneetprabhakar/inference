import numpy as np
def exact(a,b,path='state'):
 import torch
 if isinstance(a,torch.Tensor):
  assert isinstance(b,torch.Tensor) and a.dtype==b.dtype and a.shape==b.shape and torch.equal(a,b),path
 elif isinstance(a,np.ndarray):assert np.array_equal(a,b),path
 elif isinstance(a,dict):
  assert a.keys()==b.keys(),path
  for k in a:exact(a[k],b[k],path+'.'+str(k))
 elif isinstance(a,(list,tuple)):
  assert type(a)==type(b) and len(a)==len(b),path
  for i,(x,y) in enumerate(zip(a,b)):exact(x,y,path+f'[{i}]')
 else:assert a==b,path

