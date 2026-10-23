import unittest,math
import numpy as np
from common import check_clock,original_rate
from scorer import suffix_score,continuation,causal_mask,controls,kappa
class Fixtures(unittest.TestCase):
 def test_suffix_shift(self):
    # Three position-dependent distributions; only rows1,2 predict suffix2,1.
    p=np.array([[.9,.05,.05],[.1,.2,.7],[.1,.8,.1]])
    self.assertAlmostEqual(suffix_score(np.log(p),[0,1,2,1],2),math.log(.7)+math.log(.8))
    p[0]=[.01,.01,.98]
    self.assertAlmostEqual(suffix_score(np.log(p),[0,1,2,1],2),math.log(.7)+math.log(.8))
 def test_causal(self):
    # Independent explicit attention fixture: changing a future value cannot
    # influence earlier outputs after application of the production mask.
    mask=causal_mask(4);weights=np.exp(mask);weights/=weights.sum(axis=-1,keepdims=True)
    self.assertTrue(np.isneginf(mask[0,1:] ).all());self.assertTrue((np.diag(mask)==0).all())
    a=weights@np.array([2,4,6,8]);b=weights@np.array([2,4,6,800])
    np.testing.assert_array_equal(a[:3],b[:3]);self.assertNotEqual(a[3],b[3])
 def test_joint_encoding(self):
    class Tok:
      def encode(self,s,bos,eos):return ([0] if bos else [])+[ord(x) for x in s]
    ids,p=continuation(Tok(),'ab',' c');self.assertEqual(ids,[0,97,98,32,99]);self.assertEqual(p,3)
 def test_clock_all_phases(self):
    for phase,cap in [('R0',2700),('R1',10800),('R2',10800)]:
      c=dict(schema_version=1,phase=phase,started_epoch=10,deadline_epoch=10+cap,wall_seconds_cap=cap,shutdown_reserve_seconds=300)
      check_clock(c,phase,now=11)
      with self.assertRaises(TimeoutError):check_clock(c,phase,now=10+cap-300)
      with self.assertRaises(AssertionError):check_clock(c,'wrong',now=11)
 def test_lr(self):
    self.assertAlmostEqual(original_rate(2889),.0004995509721941322)
 def test_kappa(self):self.assertEqual(kappa([0,1],[0,1]),1)
if __name__=='__main__':unittest.main()
