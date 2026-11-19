"""Compare the repair port against the pinned local reference before any SFT."""
from pathlib import Path
import unittest

import torch

from cloud_training.ganesh_sft_repair import load_base10b
from cloud_training.nano_package import TOKENIZER_SHA
from cloud_training.nano_serve import load_own_bundle

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local-readiness-v1/base10b"


class ParentParity(unittest.TestCase):
    @unittest.skipUnless(torch.backends.mps.is_available() and (BASE / "payload.pt").is_file(),
                         "requires local Base10B weights and MPS")
    @torch.inference_mode()
    def test_logits_match_across_short_window_boundary(self):
        reference, _, _ = load_own_bundle(
            ROOT / "runs/nanochat-source", BASE, ROOT / "runs/ownbase-v2-data/tokenizer",
            tokenizer_sha256=TOKENIZER_SHA, device="mps", allow_base=True,
        )
        candidate = load_base10b(BASE, "mps").eval()
        for length in (13, 641):
            with self.subTest(length=length):
                ids = (torch.arange(length, device="mps")[None, :] * 71 + 42) % 32759
                torch.testing.assert_close(candidate(ids), reference(ids), rtol=0, atol=0)
