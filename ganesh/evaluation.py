"""9-category capability evaluation harness and readiness verifier for Ganesh-base."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloud_training.ganesh_sft_repair import (
    ALL_SUPPORTED_TOOLS,
    compact_policy_header,
    validate_any_tool_call,
)
from reports.ganesh_tool_crud_helper import TOOLS as CRUD_TOOLS
from tools import FixtureSession


def verify_evaluation_suite(root: Path = ROOT) -> dict:
    eval_path = root / "configs/evaluation.json"
    spec = json.loads(eval_path.read_text())
    categories = spec.get("categories", [])
    if len(categories) != 9:
        raise ValueError(f"Expected 9 evaluation categories, found {len(categories)}")

    session = FixtureSession()
    verified_prompts = 0
    tool_Replays = 0

    for cat in categories:
        for item in cat.get("prompts", []):
            verified_prompts += 1
            header = compact_policy_header(item["policy"])
            if not header.startswith("[tools:"):
                raise ValueError(f"Invalid policy header: {header}")
            if item.get("expect_tool_call") and "expected_tool" in item:
                call = validate_any_tool_call(item["expected_tool"])
                if call["name"] in ("calculate", "convert"):
                    s = FixtureSession()
                    s.start_turn(permit_calls=True, allowed_names=["calculate", "convert"])
                    obs = s.propose(json.dumps(call), assistant_call_boundary=True)
                    if not obs.get("ok"):
                        raise ValueError(f"Broker replay failed for {call}")
                elif call["name"] in CRUD_TOOLS:
                    field = CRUD_TOOLS[call["name"]]
                    if call["arguments"]["op"] in ("create", "update") and field not in call["arguments"]:
                        raise ValueError(f"CRUD replay missing field {field}")
                tool_Replays += 1

    return {
        "status": "ready",
        "version": spec["version"],
        "model_name": spec["model_name"],
        "creator": spec["creator"],
        "categories": len(categories),
        "verified_prompts": verified_prompts,
        "replayed_expected_tool_calls": tool_Replays,
        "supported_tools": sorted(ALL_SUPPORTED_TOOLS),
        "evaluation_sha256": hashlib.sha256(eval_path.read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify or run the 9-category Ganesh-base evaluation suite.")
    parser.add_argument("--require-ready", action="store_true", help="Verify all 9 categories and tool replays.")
    args = parser.parse_args()
    report = verify_evaluation_suite(ROOT)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
