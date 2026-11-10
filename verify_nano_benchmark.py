"""Small CPU tests of qualification arithmetic and state comparison; no GPU allocation."""
import json
import tempfile
from pathlib import Path
import unittest

from cloud_training.nano_benchmark import BATCH, HORIZON, atomic_json, can_measure_update, digest_state, microbatches, schedule


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
