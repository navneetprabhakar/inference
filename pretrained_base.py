"""Verify local pretraining ancestry before transferring student model weights."""
from dataclasses import asdict
import json
from pathlib import Path
import re

import torch

import checkpoint
from gpt2 import Config
from tokenizer import ASSETS

ROOT = Path(__file__).resolve().parent
PRE_SFT_REPORT = ROOT / "reports/astra-feasibility/pretraining.json"
PRE_SFT_REPORT_SHA256 = "120cc3af4b7ffb566bd7fdc5104783a9886ef2c7414b0611303acb4b653e74b8"
PRE_SFT_RUN = ROOT / "runs/astra-candidate-01"


def load_base(base, sha, *, terminal=None):
    """Return weights only. A continuation also requires the exact passing terminal step."""
    base = Path(base)
    if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
        raise ValueError("invalid base SHA-256")
    if base.is_symlink() or checkpoint.checksum(base) != sha:
        raise ValueError("base hash mismatch")
    parent = base.parent
    protected = json.loads((parent / "protected.json").read_text())
    status = json.loads((parent / "status.json").read_text())
    if base.name not in protected or status.get("stage") != "extended pretraining" or status["state"] != "passed":
        raise ValueError("base must be protected by a passing extended pretraining run")
    saved = torch.load(base, map_location="cpu", mmap=True, weights_only=True)
    identity = json.loads((parent / "config.json").read_text())
    if saved["identity"] != identity:
        raise ValueError("base lineage differs from its run configuration")
    if identity["model"] != asdict(Config()) or saved["step"] <= 0:
        raise ValueError("base is untrained or differs from the 124M architecture")
    if identity.get("tokenizer") != ASSETS:
        raise ValueError("base tokenizer mismatch")
    if terminal is not None:
        if (not saved.get("protected") or (saved.get("terminal") or {}).get("state") != "passed"
                or saved["step"] != terminal["step"] or status["step"] != terminal["step"]
                or saved["target_tokens"] != terminal["target_tokens"] or status["target_tokens"] != terminal["target_tokens"]
                or saved["target_tokens"] != identity["spec"]["target_tokens"]
                or identity["dtype"] != "fp32" or any(t.dtype != torch.float32 for t in saved["model"].values())):
            raise ValueError("base differs from its passing terminal checkpoint")
    return saved["model"]


def continuation_parent(spec, model_config):
    """Resolve only the reported, protected local pre-SFT base. Relative paths use the repo root."""
    supplied = spec.get("parent_checkpoint")
    if supplied is None:
        if "parent_checkpoint" in spec:
            raise ValueError("omit parent_checkpoint for random initialization")
        return None
    if type(spec.get("budget_name")) is not str or not spec["budget_name"].strip():
        raise ValueError("continuation requires a named fresh budget")
    if type(supplied) is not dict or supplied.keys() != {"path","sha256"} or not isinstance(supplied["path"], str):
        raise ValueError("parent_checkpoint requires a local path and SHA-256")
    if model_config != Config():
        raise ValueError("continuation requires the GPT-2 small architecture")
    if checkpoint.checksum(PRE_SFT_REPORT) != PRE_SFT_REPORT_SHA256:
        raise ValueError("pre-SFT acceptance report hash mismatch")
    report = json.loads(PRE_SFT_REPORT.read_text())
    entry = report["base"]
    base = ROOT / supplied["path"]
    expected = PRE_SFT_RUN / entry["file"]
    if (not supplied["path"] or base.is_symlink() or base.resolve() != expected.resolve()
            or supplied["sha256"] != entry["sha256"] or entry["file"] not in report["protected_checkpoints"]
            or report["model_parameters"] != 124_439_808 or report["state"]["stage"] != "extended pretraining"
            or report["state"]["state"] != "passed"):
        raise ValueError("continuation requires the exact reported local pre-SFT base")
    return dict(path=str(expected), sha256=entry["sha256"], bytes=entry["bytes"],
                step=report["state"]["step"], target_tokens=report["state"]["target_tokens"],
                acceptance_report_sha256=PRE_SFT_REPORT_SHA256)
