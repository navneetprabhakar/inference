"""Contract, guardrail, and milestone hash-binding validator for Ganesh-base."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ganesh import MODEL_IDENTITY, MODEL_IDENTITY_SHA256, verify_model_identity
from ganesh.model import GaneshConfig, GaneshGPT


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lookup_dotted(data: dict, dotted: str):
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def validate_contract(root: Path = ROOT) -> dict:
    project_path = root / "configs/project.json"
    guardrails_path = root / "configs/guardrails.json"
    project = json.loads(project_path.read_text())
    guardrails = json.loads(guardrails_path.read_text())

    # Layer 1: Enforce immutable model identity and creator provenance
    verify_model_identity(project.get("identity"))
    root_identity_path = root / "configs/MODEL_IDENTITY.json"
    if root_identity_path.is_file():
        root_id = json.loads(root_identity_path.read_text())
        if root_id.get("model_name") != MODEL_IDENTITY["model_name"] or root_id.get("creator") != MODEL_IDENTITY["creator"]:
            raise ValueError("MODEL_IDENTITY.json drift detected against immutable Ganesh-base identity")

    violations: list[str] = []
    for key, expected in guardrails.get("required", {}).items():
        actual = lookup_dotted(project, key)
        if actual != expected:
            violations.append(f"required[{key}]: expected {expected!r}, got {actual!r}")

    for key, min_val in guardrails.get("minimum", {}).items():
        actual = lookup_dotted(project, key)
        if actual is None or actual < min_val:
            violations.append(f"minimum[{key}]: expected >= {min_val!r}, got {actual!r}")

    for key, max_val in guardrails.get("maximum", {}).items():
        actual = lookup_dotted(project, key)
        if actual is None or actual > max_val:
            violations.append(f"maximum[{key}]: expected <= {max_val!r}, got {actual!r}")

    # Verify exact 536,871,738-parameter and 119-tensor model architecture on meta device
    with torch.device("meta"):
        cfg = GaneshConfig(
            sequence_len=project["candidate"]["sequence_len"],
            vocab_size=project["candidate"]["vocab_size"],
            n_layer=project["candidate"]["n_layer"],
            n_head=project["candidate"]["n_head"],
            n_kv_head=project["candidate"]["n_kv_head"],
            n_embd=project["candidate"]["n_embd"],
        )
        model = GaneshGPT(cfg)
        counts = model.num_scaling_params()
        tensor_count = len(list(model.state_dict().keys()))
    if counts["total"] != project["parameter_preference"]["exact_parameters"]:
        violations.append(f"model parameter count {counts['total']} != {project['parameter_preference']['exact_parameters']}")
    if tensor_count != project["parameter_preference"]["exact_tensors"]:
        violations.append(f"model tensor count {tensor_count} != {project['parameter_preference']['exact_tensors']}")

    if violations:
        raise ValueError("Contract validation failed:\n" + "\n".join(violations))

    return {
        "status": "valid",
        "model_name": project["identity"]["model_name"],
        "creator": project["identity"]["creator"],
        "parameters": counts["total"],
        "tensors": tensor_count,
        "parameter_breakdown": counts,
    }


def check_execution_state(root: Path = ROOT) -> dict:
    validate_Result = validate_contract(root)
    exec_path = root / "configs/execution.json"
    guardrails = json.loads((root / "configs/guardrails.json").read_text())
    execution = json.loads(exec_path.read_text())

    deps = guardrails["milestone_dependencies"]
    milestones = execution["milestones"]
    violations: list[str] = []

    for mid, mstate in milestones.items():
        if mstate["status"] in ("completed", "in_progress"):
            for req in deps.get(mid, []):
                if milestones[req]["status"] != "completed":
                    violations.append(f"Milestone {mid} is {mstate['status']} before dependency {req} completed")
        if mstate["status"] == "completed":
            for rel_path, expected_sha in mstate.get("evidence_sha256", {}).items():
                target = root / rel_path
                if not target.is_file():
                    violations.append(f"Milestone {mid} missing evidence file: {rel_path}")
                elif sha256_file(target) != expected_sha:
                    violations.append(f"Milestone {mid} SHA-256 mismatch for {rel_path}")

    if violations:
        raise ValueError("Execution check failed:\n" + "\n".join(violations))

    return {
        **validate_Result,
        "status": "ok",
        "active_milestone": execution["active_milestone"],
        "completed_milestones": [k for k, v in milestones.items() if v["status"] == "completed"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Ganesh-base contract, guardrails, and milestone state.")
    parser.add_argument("command", choices=["validate", "check"])
    args = parser.parse_args()
    if args.command == "validate":
        print(json.dumps(validate_contract(ROOT), indent=2))
    else:
        print(json.dumps(check_execution_state(ROOT), indent=2))


if __name__ == "__main__":
    main()
