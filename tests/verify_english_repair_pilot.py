import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from ganesh import english_pilot as pilot
from ganesh.model import GaneshConfig, GaneshGPT


class PilotChecks(unittest.TestCase):
    def test_turnwise_stop_and_denominator(self):
        good = {"passed": True, "status": "complete"}
        wrong = {"passed": False, "status": "complete"}
        blocked = {"passed": False, "status": "blocked"}
        self.assertTrue(pilot.regressed([good, wrong], [wrong, good]))
        self.assertTrue(pilot.regressed([wrong], [blocked]))
        self.assertFalse(pilot.regressed([blocked], [wrong]))
        receipt = json.loads(pilot.BASELINE.read_text())
        spec = json.loads(pilot.CONTRACT.read_text())
        self.assertEqual(receipt["contract_sha256"], pilot.sha(pilot.CONTRACT))
        self.assertEqual(len(receipt["rows"]), sum(len(s["turns"]) for s in spec["sessions"]))

    def test_saved_model_preserves_window_weights_and_refuses_corruption(self):
        model = GaneshGPT(GaneshConfig(vocab_size=128, n_embd=32, n_layer=2, n_head=2, n_kv_head=2))
        model.set_full_causal_attention()
        tokens = torch.arange(32)[None, :]
        with tempfile.TemporaryDirectory() as tmp, patch.object(pilot, "probe", lambda m: [m(tokens)]):
            directory = Path(tmp)
            receipt = pilot.verified_save(model, directory, "best", {"step": 1})
            path = directory / receipt["file"]
            restored = pilot.restore(path, receipt["sha256"], "cpu")
            self.assertEqual(restored.config.window_pattern, "LL")
            self.assertTrue(torch.equal(model(tokens), restored(tokens)))
            with self.assertRaises(FileExistsError):
                pilot.verified_save(model, directory, "best", {"step": 2})
            with self.assertRaisesRegex(ValueError, "checksum"):
                pilot.restore(path, "0" * 64, "cpu")

    @unittest.skipUnless(torch.backends.mps.is_available(), "local MPS fixture")
    def test_training_entry_stops_and_reloads_distinct_best_and_last(self):
        from contextlib import ExitStack
        from verify_ganesh_sft_repair import MockNanochatTokenizer

        dataset = pilot.ROOT / "reports/ganesh-sft-repair-v2"
        splits = {k: list(map(json.loads, (dataset / f"{k}.jsonl").read_text().splitlines()))
                  for k in ("train", "validation")}
        model = GaneshGPT(GaneshConfig(n_embd=32, n_layer=2, n_head=2, n_kv_head=2)).to("mps")
        baseline = json.loads(pilot.BASELINE.read_text())
        before = baseline["rows"]
        gain = [dict(r, passed=True, status="complete") if i == 0 else r for i, r in enumerate(before)]
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(pilot, "bind", return_value=baseline))
            stack.enter_context(patch.object(pilot, "evaluate", side_effect=[before, gain, before, gain, before]))
            tokens = torch.arange(12, device="mps")[None, :]
            stack.enter_context(patch.object(pilot, "probe", lambda m: [m(tokens)]))
            result = pilot.run(model, MockNanochatTokenizer(), splits, Path(tmp) / "fixture", dataset)
        self.assertEqual(result["updates"], 2)
        self.assertEqual(result["stop"], "behavior_regression")
        self.assertEqual(result["comparison"]["best"]["step"], 1)
        self.assertEqual(result["comparison"]["last"]["step"], 2)
        self.assertNotEqual(result["comparison"]["best"]["sha256"], result["comparison"]["last"]["sha256"])
