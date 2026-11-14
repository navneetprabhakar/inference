import copy,tempfile,unittest
from pathlib import Path
import torch
from cloud_training.nano_checkpoint import save_bundle,capture_rng,restore_rng_state
from cloud_training.nano_restart_compare import compare_bundles
from verify_nano_sft import TinyLM

class RestartComparisonTests(unittest.TestCase):
    def test_equal_full_state_then_optimizer_drift_and_loop_change_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);m=TinyLM();o=torch.optim.AdamW(m.parameters());x=torch.tensor([[1,2]])
            m(x,x).backward();o.step();o.zero_grad();rng=capture_rng()
            def save(name,loop=None,step=2):
                restore_rng_state(rng);p=root/name
                save_bundle(p,model=m,optimizer=o,metadata={'step':step,'identity':{'fixture':True},'loop':loop or {'stopped':False}},data_state={'exact':True,'next_batch':step})
                return p
            a=save('a');b=save('b');self.assertEqual(compare_bundles(a,b)['status'],'pass')
            c=save('c',{'stopped':True});self.assertEqual(compare_bundles(a,c)['status'],'hold')
            with torch.no_grad():next(iter(o.state.values()))['exp_avg'].flatten()[0]+=1e-6
            d=save('d');self.assertEqual(compare_bundles(a,d)['status'],'hold')
            e=save('e',step=3)
            with self.assertRaisesRegex(ValueError,'identity or completed step'):compare_bundles(a,e)
    def test_corruption_rejected_before_deserialization(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);m=TinyLM();o=torch.optim.AdamW(m.parameters())
            save_bundle(root/'a',model=m,optimizer=o,metadata={'step':2,'identity':{'fixture':True}},data_state={'exact':True,'next_batch':2})
            (root/'a'/'payload.pt').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):compare_bundles(root/'a',root/'a')
if __name__=='__main__':unittest.main()
