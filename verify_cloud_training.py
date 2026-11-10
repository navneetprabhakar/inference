import tempfile
from pathlib import Path
import unittest
import numpy as np
import torch
from gpt2 import GPT2,Config
from cloud_training.runtime import Guard,optimizer,update,save,restore,sha

class Tests(unittest.TestCase):
    def test_restart_matches_uninterrupted(self):
        torch.set_num_threads(1);torch.manual_seed(19)
        config=Config(vocabulary=19,context=16,width=12,depth=2,heads=3)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);g=Guard(root,60,min_free=0)
            model=GPT2(config);opt=optimizer(model)
            rows=np.array([[1,2,3,4,5],[6,7,8,9,10]])
            update(model,opt,rows,device='cpu',microbatch=1,lr=6e-5,guard=g,bf16=False)
            path=root/'checkpoint.pt';receipt=save(path,model,opt,cursor=1,identity={'test':True,'torch':torch.__version__})
            self.assertEqual(sha(path),receipt['sha256'])
            update(model,opt,rows,device='cpu',microbatch=1,lr=6e-5,guard=g,bf16=False)
            other=GPT2(config);otheropt=optimizer(other)
            payload=torch.load(path,map_location='cpu',weights_only=True)
            restore(other,otheropt,payload,'cpu')
            update(other,otheropt,rows,device='cpu',microbatch=1,lr=6e-5,guard=g,bf16=False)
            for a,b in zip(model.parameters(),other.parameters()):torch.testing.assert_close(a,b,rtol=0,atol=0)
            for a,b in zip(opt.state.values(),otheropt.state.values()):
                for key in a:torch.testing.assert_close(a[key],b[key],rtol=0,atol=0)
            (root/'STOP').touch()
            with self.assertRaises(InterruptedError):g.check()

    def test_masked_accumulation(self):
        torch.manual_seed(9);config=Config(vocabulary=19,context=16,width=12,depth=1,heads=3)
        a=GPT2(config);b=GPT2(config);b.load_state_dict(a.state_dict())
        rows=np.array([[1,2,3,4],[5,6,7,8]])
        labels=np.array([[-100,3,4],[-100,-100,8]])
        with tempfile.TemporaryDirectory() as tmp:
            g=Guard(tmp,60,min_free=0)
            update(a,optimizer(a),rows,labels=labels,device='cpu',microbatch=1,lr=6e-5,guard=g,bf16=False)
            update(b,optimizer(b),rows,labels=labels,device='cpu',microbatch=2,lr=6e-5,guard=g,bf16=False)
            for x,y in zip(a.parameters(),b.parameters()):torch.testing.assert_close(x,y,rtol=1e-4,atol=1e-6)

    def test_context_pairs_prevent_entity_label_shortcut(self):
        from cloud_training.diagnostics import synthetic
        from tokenizer import load
        splits=synthetic(load())
        for cases in splits.values():
            self.assertEqual(len(cases),128)
            for a,b in zip(cases[::2],cases[1::2]):
                self.assertEqual(a['target'],b['target'])
                self.assertEqual(a['pair_id'],b['pair_id'])
                self.assertNotEqual(a['correct'],b['correct'])
                self.assertNotEqual(a['prefix'],b['prefix'])
        self.assertFalse({x['target'] for x in splits['train']} & {x['target'] for x in splits['entities']})

    def test_budget_reservations(self):
        from cloud_training.budget import reserve
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ledger.json'
            reserve(p,'first',3)
            for i in range(4): reserve(p,f'additional-{i}',3)
            with self.assertRaises(ValueError):reserve(p,'over-cap',3)
            with self.assertRaises(ValueError):reserve(p,'first',1)
            with self.assertRaises(ValueError):reserve(p,'bad',float('nan'))

if __name__=='__main__':unittest.main(verbosity=2)
