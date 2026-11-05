"""Exercise candidate milestones, hard caps and crash recovery using a tiny CPU run."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import numpy as np
import torch

import checkpoint
from gpt2 import Config
import pretrain


def worker(mode, budget, path):
    torch.set_num_threads(1)
    tiny = Config(width=4, heads=1, depth=1, context=256)
    evaluate = pretrain.evaluate
    save = checkpoint.save
    status_writer = pretrain.atomic_status

    def evaluate_fixture(model, shards, tokenizer, check):
        step = json.loads((path / "status.json").read_text())["step"]
        if step == 0:
            # Execute the production evaluation path once, including contrast labels.
            result = evaluate(model, shards, tokenizer, check)
            assert len(result["contrast_logit_margins"]) == 4
        loss = 15.0 + step if mode.startswith("fail") else 15.0 - step
        return dict(validation={"fixture": loss}, samples={}, contrast_logit_margins=[])

    def interrupted_save(target, state):
        save(target, state)
        if mode == "interrupt" and state["step"] == 3:
            os._exit(17)
        if mode == "fail-interrupt" and state["terminal"]:
            os._exit(17)

    def interrupted_start(target, state):
        status_writer(target, state)
        if (mode == "lost-work" and target.name == "status.json"
                and state.get("step") == 3 and state.get("reserved_target_tokens") == 64):
            os._exit(17)

    with ExitStack() as mocks:
        for name, value in [("guards.thermal", 0), ("guards.swap_mib", 10),
                            ("guards.torch.mps.current_allocated_memory", 0)]:
            mocks.enter_context(patch(name, return_value=value))
        for name, value in [("LENGTH", 8), ("MICROBATCHES", 2), ("TOKENS_PER_STEP", 16),
                            ("evaluate", evaluate_fixture), ("atomic_status", interrupted_start)]:
            mocks.enter_context(patch.object(pretrain, name, value))
        mocks.enter_context(patch.object(checkpoint, "save", interrupted_save))
        passed = pretrain.run(budget, path, resume=mode.endswith("resume"), device="cpu", model_config=tiny)
        return 0 if passed else 3


def check():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        corpus = root / "data"
        corpus.mkdir()
        meta = {}
        rng = np.random.default_rng(100)
        for name in ("fixture-train", "fixture-validation"):
            raw = rng.integers(0, 100, 220, dtype="<u2")
            file = corpus / (name + ".u16")
            raw.tofile(file)
            meta[name] = dict(tokens=len(raw), sha256=checkpoint.checksum(file))
        manifest = corpus / "manifest.json"
        manifest.write_text(json.dumps(dict(shards=meta)))
        spec = dict(seed=100, target_tokens=192, active_seconds=180, elapsed_seconds=180,
                    warmup_steps=1, validation_rows_per_source=1, mix={"fixture": 2}, primary="fixture",
                    minimum_ce_improvement=.01, material_ce_regression=.1, corpus=str(corpus),
                    manifest_sha256=checkpoint.checksum(manifest))
        budget = root / "budget.json"
        budget.write_text(json.dumps(spec))

        def call(mode, name, expected):
            result = subprocess.run([sys.executable, __file__, mode, str(budget), str(root / name)])
            assert result.returncode == expected, (mode, result.returncode)

        call("full", "full", 0)
        call("interrupt", "restarted", 17)
        call("resume", "restarted", 0)
        config = json.loads((root / "full" / "config.json").read_text())
        a, b = [checkpoint.load(root / name, config) for name in ("full", "restarted")]
        assert (a["step"], a["target_tokens"], a["offsets"]) == (12, 192, {"fixture": 192})
        assert (b["step"], b["target_tokens"], b["offsets"]) == (12, 192, {"fixture": 192})
        assert torch.equal(a["cpu_rng"], b["cpu_rng"])
        assert all(torch.equal(v, b["model"][k]) for k, v in a["model"].items())
        assert a["optimizer"]["param_groups"] == b["optimizer"]["param_groups"]
        for i, tensors in a["optimizer"]["state"].items():
            assert all(torch.equal(v, b["optimizer"]["state"][i][k]) for k, v in tensors.items())
        assert a["history"] == b["history"]
        call("lost-work", "charged", 17)
        call("resume", "charged", 3)
        charged = json.loads((root / "charged" / "status.json").read_text())
        assert (charged["state"], charged["reserved_target_tokens"], charged["target_tokens"]) == ("stopped", 192, 176)
        call("fail-interrupt", "rejected", 17)
        call("fail-resume", "rejected", 3)
        failure = json.loads((root / "rejected" / "status.json").read_text())
        assert failure["state"] == "failed" and failure["step"] == 1
        print(json.dumps(dict(state="passed", device="cpu", bit_identical_candidate=True,
                              hard_token_cap=192, reserved_lost_work=16, failed_gate_preserved=True)))


if __name__ == "__main__":
    if len(sys.argv) == 4:
        raise SystemExit(worker(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])))
    check()
