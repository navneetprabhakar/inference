"""Small CPU tests of qualification arithmetic and state comparison; no GPU allocation."""
import json
import tempfile
from pathlib import Path
import unittest

from cloud_training.nano_benchmark import BATCH, HORIZON, atomic_json, can_measure_update, digest_state, microbatches, schedule, snapshot_cpu, compare_state, deterministic_attention


class BenchmarkTests(unittest.TestCase):
    def test_microbatch_keeps_effective_batch(self):
        for m in microbatches('8,4,2,1'):
            self.assertEqual(m * 2048 * (BATCH // (m * 2048)), BATCH)
        for bad in ('0', '3', '-1', ''):
            with self.assertRaises(ValueError): microbatches(bad)

    def test_finite_data_stops_before_restart_reserve(self):
        from cloud_training.nano_data import PackedRows, write_rows
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'rows'
            write_rows(p, [[1, 2, 3]] * 12, sequence_length=2, vocab_size=4,
                       tokenizer_sha256='a'*64, split='train', source_manifest_sha256='b'*64,
                       packing='fixture', max_rows=12)
            reader = PackedRows(p, expected_tokenizer_sha256='a'*64, expected_split='train')
            measurements = 0
            while can_measure_update(reader, rows_per_update=2, reserve_updates=2):
                reader.read(2); measurements += 1
            self.assertEqual(measurements, 4)
            self.assertEqual(reader.next_row, 8)
            state = reader.state_dict()
            expected = reader.read(2)
            reader.load_state_dict(state)
            self.assertEqual(reader.read(2), expected)
            reader.read(2)
            with self.assertRaises(StopIteration): reader.read(1)
            self.assertEqual(reader.next_row, 12)

    def test_schedule_boundaries(self):
        self.assertAlmostEqual(schedule(0)[0], .025)
        self.assertEqual(schedule(39)[0], 1.)
        self.assertEqual(schedule(400)[1], .97)
        self.assertAlmostEqual(schedule(HORIZON)[0], .05)
        self.assertAlmostEqual(schedule(HORIZON)[1], .90)
        self.assertEqual(schedule(HORIZON)[2], 0.)
        self.assertEqual(BATCH * HORIZON, 10000269312)

    def test_atomic_json_and_nonfinite_rejection(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'a.json'
            atomic_json(p, {'ok': 1})
            with self.assertRaises(ValueError): atomic_json(p, {'bad': float('nan')})
            self.assertEqual(json.loads(p.read_text()), {'ok': 1})

    def test_component_comparison_quantifies_tensor_and_metadata_changes(self):
        import torch
        expected={'model':{'weight':torch.tensor([1.,2.],dtype=torch.bfloat16)},
                  'optimizer':{'state':{0:{'moment':torch.tensor([0.,1.])}},'lr':.1}}
        actual=snapshot_cpu(expected)
        actual['model']['weight'][1]=2.5
        actual['optimizer']['state'][0]['moment'][0]=.25
        actual['optimizer']['lr']=.2
        report=compare_state(expected,actual,chunk_elements=1)
        self.assertFalse(report['bitwise_equal'])
        self.assertEqual(report['tensor_mismatch_count'],2)
        self.assertEqual(report['numeric_mismatch_elements'],2)
        self.assertEqual(report['max_abs_difference'],.5)
        self.assertEqual(report['groups']['model']['tensor_mismatches'],1)
        self.assertEqual(report['groups']['optimizer']['tensor_mismatches'],1)
        self.assertEqual(report['metadata_mismatch_count'],1)
        self.assertEqual(report['metadata_mismatches'][0]['path'],'optimizer.lr')
        self.assertEqual(float(expected['model']['weight'][1]),2.) # snapshot is not aliased
        self.assertTrue(compare_state(expected,snapshot_cpu(expected))['bitwise_equal'])

    def test_bf16_ulp_and_rms_diagnostics(self):
        import torch
        expected={'gradients':{'weight':torch.tensor([1.,-1.],dtype=torch.bfloat16)}}
        actual={'gradients':{'weight':torch.nextafter(expected['gradients']['weight'],torch.tensor([2.,-2.],dtype=torch.bfloat16))}}
        report=compare_state(expected,actual,chunk_elements=1)
        tensor=report['top_tensor_mismatches'][0]
        self.assertEqual(tensor['max_bf16_ulp_distance'],1)
        self.assertEqual(tensor['rms_abs_difference'],.0078125)
        self.assertEqual(report['groups']['gradients']['numeric_mismatch_elements'],2)

    def test_non_tensor_structure_and_signed_zero_reported(self):
        import torch
        report=compare_state({'model':{'zero':torch.tensor([0.])},'optimizer':{'betas':(.8,.9)}},
                             {'model':{'zero':torch.tensor([-0.])},'optimizer':{'betas':[.8,.9]}})
        self.assertFalse(report['bitwise_equal'])
        self.assertEqual(report['tensor_mismatch_count'],1)
        self.assertEqual(report['numeric_mismatch_elements'],0)
        self.assertEqual(report['metadata_mismatch_count'],1)

    def test_deterministic_attention_flag_is_forwarded_explicitly(self):
        from types import SimpleNamespace
        def forward(q,k,v,deterministic=False):return deterministic
        attention=SimpleNamespace(USE_FA3=True,_fa3=SimpleNamespace(flash_attn_func=forward))
        deterministic_attention(attention)
        self.assertTrue(attention._fa3.flash_attn_func(None,None,None))
        with self.assertRaises(RuntimeError):deterministic_attention(SimpleNamespace(USE_FA3=False))

    def test_restored_state_digest_matches_before_any_new_update(self):
        import torch
        from cloud_training.nano_checkpoint import save_bundle,load_bundle
        model=torch.nn.Linear(2,2);opt=torch.optim.AdamW(model.parameters(),lr=.01)
        def update():
            model(torch.ones((1,2))).sum().backward();opt.step();opt.zero_grad(set_to_none=True)
        update();before=digest_state(model,opt)
        with tempfile.TemporaryDirectory() as t:
            save_bundle(Path(t)/'state',model=model,optimizer=opt,
                        metadata={'step':1,'identity':{'test':'pre-update'}},
                        data_state={'exact':True,'next_batch':1})
            update();self.assertNotEqual(digest_state(model,opt),before)
            load_bundle(Path(t)/'state',model=model,optimizer=opt,expected_identity={'test':'pre-update'})
            self.assertEqual(digest_state(model,opt),before)

    def test_state_digest_includes_optimizer_and_bf16(self):
        import torch
        m = torch.nn.Linear(2, 2, dtype=torch.bfloat16)
        opt = torch.optim.AdamW(m.parameters())
        a = digest_state(m, opt)
        m(torch.ones((1, 2), dtype=torch.bfloat16)).sum().backward(); opt.step(); opt.zero_grad()
        b = digest_state(m, opt)
        self.assertNotEqual(a, b)
        saved = opt.param_groups[0]['lr']
        opt.param_groups[0]['lr'] = saved * 2
        self.assertNotEqual(b, digest_state(m, opt))
        opt.param_groups[0]['lr'] = saved
        self.assertEqual(b, digest_state(m, opt))


if __name__ == '__main__':
    unittest.main()
