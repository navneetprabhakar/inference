import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_map,tree_flatten
from train_local import Corpus,make_model,loss,save_checkpoint,load_checkpoint
class TrainingTest(unittest.TestCase):
    def test_sampler_resume(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for s in ['fineweb','tinystories']:np.arange(30000,dtype=np.uint16).tofile(p/f'{s}-train.bin')
            first=Corpus(p,11)
            for _ in range(5):first.batch()
            restored=Corpus(p,11,json.loads(json.dumps(first.state())))
            for _ in range(80):
                sa,a=first.batch();sb,b=restored.batch();self.assertEqual(sa,sb);self.assertTrue(bool(mx.array_equal(a,b)))
    def test_checkpoint_restores_next_update(self):
        master,compute=make_model(64,2,128,7);opt=optim.AdamW(1e-4,bias_correction=True)
        tokens=mx.random.randint(0,128,(2,513))
        def step(m,c,o):
            _,g=nn.value_and_grad(c,loss)(c,tokens,1024);o.update(m,tree_map(lambda x:x.astype(mx.float32),g));mx.eval(m.parameters(),o.state);c.update(tree_map(lambda x:x.astype(mx.bfloat16),m.parameters()))
        step(master,compute,opt)
        with tempfile.TemporaryDirectory() as d:
            save_checkpoint(Path(d),master,opt,{'tokens':1024})
            m2,c2=make_model(64,2,128,99);o2=optim.AdamW(1e-4,bias_correction=True)
            self.assertEqual(load_checkpoint(Path(d),m2,o2)['tokens'],1024)
            c2.update(tree_map(lambda x:x.astype(mx.bfloat16),m2.parameters()))
            for name,a in tree_flatten(opt.state):
                name2=name;b=dict(tree_flatten(o2.state))[name]
                self.assertEqual(name,name2);self.assertTrue(bool(mx.array_equal(a,b)),name)
            for (name,a),(name2,b) in zip(tree_flatten(master.parameters()),tree_flatten(m2.parameters())):
                self.assertEqual(name,name2);self.assertTrue(bool(mx.array_equal(a,b)),name)
            # BF16 tied-embedding backward uses parallel accumulation; freeze the
            # gradient to test exact optimizer continuation rather than GPU ordering.
            _,g=nn.value_and_grad(compute,loss)(compute,tokens,1024)
            g=tree_map(lambda x:x.astype(mx.float32),g);mx.eval(g)
            opt.update(master,g);o2.update(m2,g);mx.eval(master.parameters(),m2.parameters())
            for (name,a),(name2,b) in zip(tree_flatten(master.parameters()),tree_flatten(m2.parameters())):
                self.assertEqual(name,name2);self.assertTrue(bool(mx.array_equal(a,b)),name)
    def test_partial_final_batch_masks_unused_targets(self):
        _,m=make_model(64,2,128,1);a=mx.random.randint(0,128,(2,513));b=mx.concatenate([a[:,:257],mx.random.randint(0,128,(2,256))],axis=1)
        self.assertTrue(bool(mx.allclose(loss(m,a,256),loss(m,b,256))))
if __name__=='__main__':unittest.main()
