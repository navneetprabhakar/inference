import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
from weight_edit_ops import edited_tensor,top_fraction,bf16_codes
class WeightEditTests(unittest.TestCase):
 def test_trim_exact_ties_and_sign(self):
  d=np.array([-2,2,2,1,0],np.float32);np.testing.assert_array_equal(top_fraction(d,.4),[-2,2,0,0,0])
 def test_scope_and_algebra(self):
  v=np.ones((2,2),np.float32);p=np.zeros_like(v);donor=3*v
  def edit(name,method):return edited_tensor(name,v,p,donor,p,donor,method,.25)
  np.testing.assert_array_equal(edit('layers.0.q.weight','global_rollback'),.75*v)
  np.testing.assert_array_equal(edit('layers.0.q.weight','embedding_norm_rollback'),v)
  np.testing.assert_array_equal(edit('embed.weight','embedding_norm_rollback'),.75*v)
  np.testing.assert_array_equal(edit('layers.0.n1.weight','clean_matrix_transfer'),v)
  np.testing.assert_array_equal(edit('embed.weight','clean_matrix_transfer'),v)
  np.testing.assert_array_equal(edit('layers.0.q.weight','clean_matrix_transfer'),1.75*v)
 def test_bf16_effective_change(self):
  x=np.array([1,1.00001,1.01,-1,-1.01],np.float32);c=bf16_codes(x);self.assertEqual(c[0],c[1]);self.assertNotEqual(c[0],c[2]);self.assertNotEqual(c[3],c[4])
if __name__=='__main__':unittest.main()
