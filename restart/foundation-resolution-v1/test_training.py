"""CPU tests that deliberately corrupt full-state metadata and optimizer arrays."""
import unittest
import numpy as np
from train import exact
class FullState(unittest.TestCase):
 def test_corrupt_metadata_is_detected(self):
  import copy
  a={'model':{'w':np.array([1.,2.])},'optimizer':{'step':3145},'rng':[np.array([3,4])],'cursor':{'microbatches':3145*32}}
  exact(a,copy.deepcopy(a))
  for section,key,value in [('optimizer','step',3146),('cursor','microbatches',1)]:
   b=copy.deepcopy(a);b[section][key]=value
   with self.assertRaises(AssertionError):exact(a,b)
  b=copy.deepcopy(a);b['model']['w'][1]=3.
  with self.assertRaises(AssertionError):exact(a,b)
  b=copy.deepcopy(a);b['rng'][0][0]=9
  with self.assertRaises(AssertionError):exact(a,b)
if __name__=='__main__':unittest.main()
