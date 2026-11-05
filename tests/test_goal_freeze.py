import fcntl,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_map
from benchmark_mlx import Model
from freeze_goal_layers import apply_freeze,frozen_digest
from sft_common import ROOT,masked_loss

class FrozenTrainingTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.lock=(ROOT/'runs/eight-hour-improvement-v1/.training.lock').open('a')
  fcntl.flock(cls.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 @classmethod
 def tearDownClass(cls):cls.lock.close()
 def test_real_adamw_update_preserves_frozen_master_weights(self):
  mx.random.seed(873);master=Model(64,2,64);compute=Model(64,2,64)
  info=apply_freeze(master,1,True);apply_freeze(compute,1,True)
  compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()))
  mx.eval(master.parameters(),compute.parameters())
  before=frozen_digest(master,info['frozen_keys']);upper_before=frozen_digest(master,['layers.1.q.weight'])
  grad=nn.value_and_grad(compute,masked_loss);loss,g=grad(compute,mx.random.randint(0,64,(1,65)),mx.ones((1,64)))
  opt=optim.AdamW(.001,weight_decay=.1);opt.update(master,g);mx.eval(loss,master.parameters(),opt.state)
  self.assertEqual(frozen_digest(master,info['frozen_keys']),before)
  self.assertNotEqual(frozen_digest(master,['layers.1.q.weight']),upper_before)
  self.assertIn('embed.weight',info['frozen_keys'])
  self.assertGreater(info['trainable_parameters'],0)
 def test_invalid_layer_plan_rejected(self):
  with self.assertRaises(ValueError):apply_freeze(Model(64,2,64),2,True)
if __name__=='__main__':unittest.main()
