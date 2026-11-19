"""Local development-only English fit pilot. All probes are exposed."""
from dataclasses import asdict
import json
import math
from pathlib import Path
import tempfile

import torch

from cloud_training import ganesh_sft_repair as sft
from cloud_training.nano_package import TOKENIZER_SHA, sha
from ganesh.model import GaneshConfig, GaneshGPT

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs/english_repair_pilot.json"
BASELINE = ROOT / "reports/ganesh-sft-repair-v2/english-baseline.json"


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def evaluate(model, tokenizer, spec):
    """Greedy native logits, with no bans, penalties, broker or answer substitution."""
    controls = sft.token_contract(tokenizer)
    device = next(model.parameters()).device
    results = []
    model.eval()
    with torch.inference_mode():
        for session in spec["sessions"]:
            history_ids = []
            blocked = False
            for prompt, expected in session["turns"]:
                row = dict(family=session["family"], prompt=prompt, expected=expected,
                           ids=[], text="", status="blocked", passed=False)
                results.append(row)
                if blocked:
                    continue
                policy = dict(permit_calls=session["tools"], allowed_names=["calculate"] if session["tools"] else [])
                frame = sft.encode_conversation(tokenizer, [dict(role="user", content=prompt)],
                    policies=[policy], for_generation=True, reply_budget=spec["reply_budget"])["ids"]
                prefix = history_ids + frame[1:] if history_ids else frame
                if len(prefix) + spec["reply_budget"] > model.config.sequence_len:
                    raise ValueError("Bound multi-turn probe exceeds context")
                for _ in range(spec["reply_budget"]):
                    logits = model(torch.tensor([prefix + row["ids"]], device=device))[0, -1]
                    if not torch.isfinite(logits).all():
                        raise ValueError("Nonfinite raw logits")
                    token = int(logits.argmax().item())
                    row["ids"].append(token)
                    if token in controls.values():
                        break
                tokens = row["ids"]
                ended = tokens[-1] == controls["<|assistant_end|>"]
                row["text"] = tokenizer.decode(tokens[:-1] if tokens[-1] in controls.values() else tokens)
                blocked = not ended or not row["text"].strip()
                row["status"] = ("complete" if not blocked else "invalid_control" if tokens[-1] in controls.values()
                                 else "budget_exhausted")
                if not blocked:
                    row["passed"] = row["text"].strip() == expected
                    history_ids = prefix + tokens
    return results


def probe(model):
    device = next(model.parameters()).device
    with torch.inference_mode():
        return [model(((torch.arange(n, device=device)[None, :] * 71 + 42) % 32759)).cpu()
                for n in (13, 641)]


def restore(path, digest, device):
    if sha(path) != digest:
        raise ValueError("Pilot checkpoint checksum mismatch")
    payload = torch.load(path, weights_only=True, mmap=True, map_location="cpu")
    from ganesh import verify_model_identity
    verify_model_identity(payload["model_identity"], payload["model_identity_sha256"])
    with torch.device("meta"):
        model = GaneshGPT(GaneshConfig(**payload["metadata"]["config"]))
    model.load_state_dict(payload["model"], assign=True, strict=True)
    return model.to(device).eval()


def verified_save(model, directory, name, bindings):
    """Publish only a fresh checkpoint whose reloaded, finite probe logits match exactly."""
    path = directory / (name + ".pt")
    with tempfile.TemporaryDirectory(dir=directory) as tmp:
        staged = Path(tmp) / "model.pt"
        sft.save_ganesh_checkpoint(model, staged, extra_metadata=dict(bindings, config=asdict(model.config)))
        digest = sha(staged)
        restored = restore(staged, digest, next(model.parameters()).device)
        for before, after in zip(probe(model), probe(restored), strict=True):
            if not torch.isfinite(before).all() or not torch.equal(before, after):
                raise ValueError("Checkpoint round-trip logits differ or are nonfinite")
        path.hardlink_to(staged)
    return dict(file=path.name, sha256=digest, exact_logit_lengths=[13, 641])


def regressed(best, current):
    return any((a["passed"] and not b["passed"]) or
               (a["status"] == "complete" and b["status"] != "complete")
               for a, b in zip(best, current, strict=True))


def score(rows):
    return sum(r["passed"] for r in rows), sum(r["status"] == "complete" for r in rows)


def bind(model, tokenizer, spec):
    if spec["parent_manifest"] != sft.active_parent()["manifest_sha256"]:
        raise ValueError("Unexpected pilot parent")
    rows = evaluate(model, tokenizer, spec)
    return dict(contract_sha256=sha(CONTRACT), parent=spec["parent_manifest"], tokenizer=TOKENIZER_SHA,
                device=str(next(model.parameters()).device), torch_version=str(torch.__version__), rows=rows)


def run(model, tokenizer, splits, directory, dataset_dir):
    """Execute only the bound local diagnostic; never resume or promote automatically."""
    spec = json.loads(CONTRACT.read_text())
    from ganesh.plan import check_execution_state
    check_execution_state(ROOT)
    if next(model.parameters()).device.type != "mps":
        raise ValueError("The recorded pilot baseline requires MPS")
    rows = {}
    for key in ("train", "validation"):
        if sha(dataset_dir / f"{key}.jsonl") != spec[f"{key}_sha256"]:
            raise ValueError("Unbound curriculum")
        rows[key] = [splits[key][i] for i in spec[f"{key}_indices"]]
        if any("tool_call" in m for r in rows[key] for m in r["messages"]):
            raise ValueError("Positive tool example in English fit pilot")
    steps = spec["epochs"] * math.ceil(len(rows["train"]) / spec["batch_size"])
    if steps != spec["max_updates"] or not 1 <= steps <= 4:
        raise ValueError("Pilot exceeds its update bound")
    baseline = bind(model, tokenizer, spec)
    if baseline != json.loads(BASELINE.read_text()):
        raise ValueError("Live raw baseline differs from the bound receipt")
    directory.mkdir(parents=True, exist_ok=False)
    bindings = {k: v for k, v in baseline.items() if k != "rows"}
    bindings.update(baseline_sha256=sha(BASELINE))
    evidence = []
    best = last = None
    reason = "update_cap"
    stale = 0

    def observe(step, active):
        nonlocal best, last, reason, stale
        current = evaluate(active, tokenizer, spec)
        last = dict(step=step, rows=current, **verified_save(active, directory, f"step-{step}", dict(bindings, step=step)))
        prior = [baseline["rows"]] + [entry["rows"] for entry in evidence]
        drop = any(regressed(old, current) for old in prior)
        evidence.append(last)
        write_json(directory / f"step-{step}.json", last)
        previous_best = baseline["rows"] if best is None else best["rows"]
        if not drop and score(current) > score(previous_best):
            best = last
            stale = 0
        elif step:
            stale += 1
        if drop:
            reason = "behavior_regression"
        elif stale >= 2:
            reason = "two_checks_without_behavior_gain"
        active.train()
        return drop or stale >= 2

    sft.run_repaired_sft(model, tokenizer, rows["train"], rows["validation"],
        epochs=spec["epochs"], batch_size=spec["batch_size"], lr=spec["learning_rate"],
        device="mps", observe=observe, native_continuation=True)
    # A setup regression can leave the untouched, already bound parent as best.
    comparison = {}
    for label, item in (("best", best), ("last", last)):
        if item is None:
            reference = sft.load_active_parent(ROOT / sft.active_parent()["directory"], "mps")
            if evaluate(reference, tokenizer, spec) != baseline["rows"]:
                raise ValueError("Best parent behavior differs on reload")
            del reference
            comparison[label] = dict(parent=spec["parent_manifest"], rows=baseline["rows"])
            continue
        restored = restore(directory / item["file"], item["sha256"], "mps")
        if evaluate(restored, tokenizer, spec) != item["rows"]:
            raise ValueError(f"Raw {label} behavior changed after reload")
        comparison[label] = item
        del restored
    result = dict(stop=reason, updates=last["step"], comparison=comparison,
                  release_eligible=False, requires_manual_transcript_review=True)
    write_json(directory / "result.json", result)
    return result
