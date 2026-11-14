import ast,copy,tempfile,unittest,json
from unittest.mock import patch
from pathlib import Path
import torch
from cloud_training.nano_checkpoint import save_bundle,capture_rng,restore_rng_state
from cloud_training.nano_restart_compare import compare_bundles,compare_and_record
from verify_nano_sft import TinyLM

class RestartComparisonTests(unittest.TestCase):
    def test_future_fault_worker_records_both_comparisons(self):
        tree=ast.parse(Path('reports/recovery-fix-v1/fault_worker.py').read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        self.assertFalse(any(n.func.id=='compare_bundles' for n in calls))
        recorded=[n for n in calls if n.func.id=='compare_and_record']
        self.assertEqual(len(recorded),2)
        self.assertEqual({n.args[2].right.value for n in recorded},
                         {'signal-rollback-comparison.json','signal-resume-comparison.json'})
    def test_failed_comparison_is_durable_before_gate_and_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'comparison.json'
            failure={'status':'hold','full_state':{'numeric_mismatch_elements':220}}
            with patch('cloud_training.nano_restart_compare.compare_bundles',return_value=failure):
                with self.assertRaisesRegex(ValueError,'Exact restart gate failed'):
                    compare_and_record('reference','resumed',path)
            self.assertEqual(json.loads(path.read_text()),failure)
            with patch('cloud_training.nano_restart_compare.compare_bundles') as compare:
                with self.assertRaises(FileExistsError):compare_and_record('reference','resumed',path)
                compare.assert_not_called()
    def test_validation_exception_is_recorded_and_receipt_failure_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'comparison.json'
            with patch('cloud_training.nano_restart_compare.compare_bundles',side_effect=ValueError('Corrupt bundle')):
                with self.assertRaisesRegex(ValueError,'Exact restart gate failed'):
                    compare_and_record('a','b',path)
            self.assertIn('Corrupt bundle',json.loads(path.read_text())['comparison_error'])
            with patch('cloud_training.nano_restart_compare.compare_bundles',return_value={'status':'pass'}):
                with self.assertRaises(OSError):compare_and_record('a','b',Path(t)/'missing'/'receipt.json')
                self.assertEqual(compare_and_record('a','b',Path(t)/'pass.json'),{'status':'pass'})
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
