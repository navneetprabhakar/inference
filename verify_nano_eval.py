"""Finite-evaluation correctness and tiny pinned-model inference tests; CPU only."""
import ast
import copy
import math
from pathlib import Path
import random
import sys
import tempfile
from types import SimpleNamespace
import unittest

import torch
import torch.nn.functional as F

from cloud_training.nano_data import write_rows
from cloud_training.nano_eval import evaluate_packed, verify_upstream, PINNED_REVISION

TOKENIZER = '1' * 64
SOURCE = '2' * 64


class TinyLossModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.config = SimpleNamespace(sequence_len=4, vocab_size=5)
        self.weight = torch.nn.Parameter(torch.tensor([.2, -.4, .8, .1, -.1]))
        self.dropout = torch.nn.Dropout(.5)
        self.flags = []
    def forward(self, x, targets, loss_reduction):
        self.flags.append((self.training, torch.is_grad_enabled()))
        logits = self.dropout(self.weight).expand(*x.shape, 5)
        return F.cross_entropy(logits.flatten(0, 1), targets.flatten(), reduction=loss_reduction)


class EvalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rows = [[0, 1, 2, 3, 4], [4, 3, 2, 1, 0], [2, 2, 2, 1, 1]]
        self.directory = self.root / 'validation'
        self.manifest = write_rows(self.directory, self.rows, sequence_length=4, vocab_size=5,
                                   tokenizer_sha256=TOKENIZER, split='validation',
                                   source_manifest_sha256=SOURCE, packing='test', max_rows=3)
        self.model = TinyLossModel()
    def evaluate(self, **kwargs):
        options = dict(tokenizer_sha256=TOKENIZER, token_budget=12,
                       batch_rows=2, actual_revision=PINNED_REVISION)
        options.update(kwargs)
        return evaluate_packed(self.model, self.directory, **options)

    def test_exact_token_weighted_loss_and_no_optimization(self):
        old = copy.deepcopy(self.model.state_dict())
        result = self.evaluate()
        targets = torch.tensor([row[1:] for row in self.rows])
        expected = F.cross_entropy(self.model.weight.expand(12, 5), targets.flatten()).item()
        self.assertAlmostEqual(result['cross_entropy_nats'], expected, places=6)
        self.assertEqual(result['target_tokens'], 12)
        self.assertEqual(result['rows'], 3)
        self.assertEqual(result['batches'], 2)
        self.assertTrue(all(flag == (False, False) for flag in self.model.flags))
        self.assertTrue(all(torch.equal(old[k], v) for k, v in self.model.state_dict().items()))
        self.assertTrue(all(p.grad is None for p in self.model.parameters()))

    def test_batch_partition_invariance(self):
        a = self.evaluate(batch_rows=1)
        b = self.evaluate(batch_rows=3)
        self.assertAlmostEqual(a['cross_entropy_nats'], b['cross_entropy_nats'], places=6)

    def test_modes_and_rng_preserved(self):
        self.model.train(); self.model.dropout.eval()
        rng = torch.get_rng_state().clone(); py_rng = random.getstate()
        self.evaluate()
        self.assertTrue(self.model.training); self.assertFalse(self.model.dropout.training)
        self.assertTrue(torch.equal(rng, torch.get_rng_state()))
        self.assertEqual(py_rng, random.getstate())

    def test_train_split_rejected(self):
        train = self.root / 'train'
        write_rows(train, self.rows, sequence_length=4, vocab_size=5, tokenizer_sha256=TOKENIZER,
                   split='train', source_manifest_sha256=SOURCE, packing='test', max_rows=3)
        self.directory = train
        with self.assertRaisesRegex(ValueError, 'split mismatch'): self.evaluate()

    def test_tokenizer_revision_and_manifest_mismatch_rejected(self):
        for options in ({'tokenizer_sha256': '3'*64}, {'actual_revision': 'other'},
                        {'expected_manifest_sha256': '4'*64}):
            with self.assertRaises(ValueError): self.evaluate(**options)

    def test_nonwhole_and_oversize_budget_rejected(self):
        for count in (0, 3, 16, True):
            with self.assertRaises(ValueError): self.evaluate(token_budget=count)

    def test_vocab_and_context_mismatch_rejected(self):
        self.model.config.vocab_size = 6
        with self.assertRaisesRegex(ValueError, 'vocabulary'): self.evaluate()
        self.model.config.vocab_size = 5; self.model.config.sequence_len = 3
        with self.assertRaisesRegex(ValueError, 'context'): self.evaluate()

    def test_nonfinite_restores_model_mode(self):
        with torch.no_grad(): self.model.weight.fill_(float('nan'))
        with self.assertRaisesRegex(ValueError, 'Nonfinite'): self.evaluate()
        self.assertTrue(self.model.training)

    def test_pinned_tiny_cached_vs_uncached(self):
        repo = Path('runs/nanochat-source')
        if not repo.exists(): self.skipTest('Pinned upstream checkout unavailable')
        verify_upstream(repo)
        sys.path.insert(0, str(repo.resolve()))
        from nanochat.gpt import GPT, GPTConfig
        from nanochat.common import COMPUTE_DTYPE
        if COMPUTE_DTYPE != torch.float32: self.skipTest('CPU test requires FP32 compute dtype')
        # Execute the exact reviewed KVCache class only: importing engine would
        # unnecessarily require the tokenizer/rustbpe and calculator execution code.
        module = ast.parse((repo/'nanochat/engine.py').read_text())
        selected = [n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'KVCache']
        ns = {'torch': torch}; exec(compile(ast.Module(body=selected, type_ignores=[]), 'pinned-KVCache', 'exec'), ns)
        model = GPT(GPTConfig(sequence_len=16, vocab_size=64, n_layer=2, n_head=1,
                              n_kv_head=1, n_embd=128, window_pattern='SL'))
        model.init_weights(); model.eval()
        with torch.no_grad():
            model.smear_lambda.fill_(.3)
            for name, p in model.named_parameters():
                if 'c_proj.weight' in name: p.normal_(0, .02)
        tokens = torch.tensor([[1, 8, 3, 12, 9, 2, 7, 5]])
        cache = ns['KVCache'](1, 1, 16, 128, 2, 'cpu', torch.float32)
        with torch.inference_mode():
            prefill = model(tokens[:, :2], kv_cache=cache)
            self.assertTrue(torch.allclose(prefill, model(tokens[:, :2]), atol=2e-6, rtol=2e-5))
            for pos in range(2, 8):
                actual = model(tokens[:, pos:pos+1], kv_cache=cache)
                expected = model(tokens[:, :pos+1])[:, -1:]
                self.assertTrue(torch.allclose(actual, expected, atol=2e-6, rtol=2e-5), str(pos))
        self.assertEqual(cache.get_pos(), 8)


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
