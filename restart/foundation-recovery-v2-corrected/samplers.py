"""Pure CPU mixture ordering/cursor schema used by bounded continuation."""
import copy,hashlib
import numpy as np

class BroadStream:
 def __init__(self,blocks,state=None):
  self.blocks=blocks;self.n=len(blocks);assert self.n>0
  self.rng=np.random.default_rng(20261024);self.epoch=0;self.cursor=0;self.permutation=self.rng.permutation(self.n);self.exposures=np.zeros(self.n,np.uint8)
  if state is not None:
   assert state['schema_version']==1 and state['n_blocks']==self.n,'UNKNOWN_MIXED_CURSOR'
   self.epoch=state['epoch'];self.cursor=state['cursor'];self.permutation=np.array(state['permutation'],dtype=np.int64);self.exposures=np.array(state['exposures'],np.uint8);self.rng.bit_generator.state=copy.deepcopy(state['rng'])
   assert sorted(self.permutation.tolist())==list(range(self.n)) and 0<=self.cursor<=self.n
 def batch(self,n):
  rows=[]
  for _ in range(n):
   if self.cursor==self.n:self.epoch+=1;self.cursor=0;self.permutation=self.rng.permutation(self.n)
   i=int(self.permutation[self.cursor]);assert self.exposures[i]<3,'BROAD_EXPOSURE_CAP'
   self.cursor+=1;self.exposures[i]+=1;rows.append(self.blocks[i])
  return np.array(rows,np.int32)
 def state(self):return dict(schema_version=1,n_blocks=self.n,epoch=self.epoch,cursor=self.cursor,permutation=self.permutation.tolist(),exposures=self.exposures.tolist(),rng=copy.deepcopy(self.rng.bit_generator.state))

def mix(native,replacement=None):
 assert native.shape==(512,257)
 shared=native[:256];other=native[256:] if replacement is None else replacement;assert other.shape==(256,257)
 rows=[];hashes=[]
 for i in range(0,256,16):
  hashes.append(hashlib.sha256(shared[i:i+16].tobytes()).hexdigest());rows.extend([shared[i:i+16],other[i:i+16]])
 return np.concatenate(rows),hashes
