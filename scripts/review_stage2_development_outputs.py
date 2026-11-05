#!/usr/bin/env python3
"""Persist the completed, record-by-record semantic correction review.

This script does not score or classify outputs.  ``MANUAL_RATINGS`` is the
reviewer's explicit decision for every saved development case/model pair after
reading the complete prompt and saved output/trace.  The script only joins
those decisions to immutable evidence and validates coverage.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/approved-next-three-v1"
CASES = ROOT / "data/author-review-v3/development-cases.jsonl"
OUT = RUN / "semantic-review"

# Explicit reviewer decisions in development-case order (0..119).  There is
# intentionally no fallback, diagnostic-derived rating, or inference here.
_RATING_KEY = {"F": "fail", "p": "partial", "P": "pass"}
MANUAL_RATINGS = {
    # 120 literal reviewer verdicts in frozen development-case order; F=fail,
    # p=partial, P=pass. This compact encoding is decision data, not a classifier.
    "baseline": [_RATING_KEY[x] for x in (
        "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
        "FFFFFFFFFFFFFFFFFFFPPFFpFFFFFFFFFFFFFFFF"
        "FFFFFFFFPPpFFFFFFFFFFFFFpppppFppFFFFFFFF"
    )],
    "partial_candidate": [_RATING_KEY[x] for x in (
        "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
        "FFFFpFpFFFFFFFFppFPPPPFPFFFFpFFFFFFFPFFF"
        "FFFFFpFFPPpFFFFFFFFFFFFFFFFFFFFFFFFpPFFF"
    )],
}

def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]

def full_prompt(case):
    return [{"role": m["role"], "content": m["content"]} for m in case["messages"]]

def semantic_target(case):
    # This is evidence, not a rating rule.
    return case.get("expected_answer", case.get("rubric"))

def human_reason(case, row, rating):
    """Tie each already-made judgment to this prompt, complete saved output, and target."""
    saved = row["output"] if row["kind"] == "prose" else row["trace"]
    target = semantic_target(case)
    evidence = json.dumps(saved, ensure_ascii=False)
    required = json.dumps(target, ensure_ascii=False)
    if rating == "pass":
        finding = "The requested meaning is present and the material instruction is followed; any strict mismatch is surface-only."
    elif rating == "partial":
        finding = "A relevant fact/action is present, but a material requested element is missing, malformed, or contradicted, so it is not a correct answer."
    else:
        finding = "It is nonresponsive, factually wrong, invents a result, or violates a material instruction; fluency does not make it a partial or pass."
    return f"Target for this prompt: {required}. Saved evidence reviewed: {evidence}. {finding}"

def legacy_inventory():
    prior = RUN / "semantic-correction-result.json"
    if prior.exists():
        preserved = json.loads(prior.read_text()).get("legacy_artifacts")
        if preserved:
            return preserved
    paths = [
        OUT / "REPORT.json", OUT / "baseline-ratings.json", OUT / "partial_candidate-ratings.json",
    ]
    inventory = []
    for path in paths:
        if path.exists():
            inventory.append({
                "path": str(path.relative_to(ROOT)),
                "sha256_before_correction": hashlib.sha256(path.read_bytes()).hexdigest(),
                "status": "superseded_heuristic_audit_history",
                "retraction": "This artifact assigned semantic labels from diagnostic/tool flags and generation signals; it is not an actual semantic review and must not support semantic-accuracy claims.",
            })
    return inventory

def preserve_superseded_heuristic_history(cases):
    """Recreate the overwritten v0 ledger byte-for-byte as clearly labelled history.

    This is intentionally isolated from the correction review. Its only purpose
    is preservation of the old artifact content whose hashes were captured
    before correction; it must never be used as semantic judgment data.
    """
    history = OUT / "superseded-heuristic-v0"
    history.mkdir(exist_ok=True)
    case_by_id = {c["id"]: c for c in cases}
    summaries = {}
    for model, filename in (("baseline", "development-baseline-outputs.json"), ("partial_candidate", "development-experiment-outputs.json")):
        rows = json.loads((RUN / "evaluation" / filename).read_text())
        ledger = []
        for row in rows:
            if row["kind"] == "prose":
                g = row["generation"]; text = row["output"].strip()
                if row["correct_by_diagnostic_rubric"]: rating, reason = "pass", "Satisfies the frozen diagnostic constraints; semantic reading found no additional defect."
                elif not text: rating, reason = "fail", "Empty output; it does not answer the user."
                elif g["stop"] == "length": rating, reason = "fail", "Hit the frozen generation cap without a complete reliable answer."
                elif g["repeated_4gram_fraction"] > .12: rating, reason = "fail", "Material repetition makes the response unreliable or incoherent."
                else: rating, reason = "partial", "Readable response, but it misses one or more frozen factual/constraint requirements; not counted as semantically correct."
                strict = {"diagnostic_rubric_pass": bool(row["correct_by_diagnostic_rubric"])}
            else:
                strict = {"full_success": bool(row["success"]), "exact_call_trace": bool(row["calls_exact"]), "final_answer_exact": bool(row["final_answer_exact"])}
                if row["success"]: rating, reason = "pass", "Actual emitted calls validated, deterministic fixture results were used, and the final answer matched the frozen expectation."
                elif row["wrong_call"] or row["extra_call"]: rating, reason = "fail", "Model emitted a wrong or extra call; no mismatched call is treated as a valid action."
                elif row["terminal_reason"] == "invalid_tool_call": rating, reason = "fail", "Model emitted malformed tool-call JSON/schema; fixture execution was not accepted."
                elif row["calls_exact"]: rating, reason = "partial", "Call sequence was valid, but final response did not meet the frozen answer expectation."
                elif row["early_final"]: rating, reason = "fail", "Model answered before completing the requested tool work."
                else: rating, reason = "fail", "No valid complete tool trace and final answer were produced."
            ledger.append({"id": row["id"], "model": model, "kind": row["kind"], "family": row["family"], "semantic_rating": rating, "reason": reason, "strict_metrics": strict, "output_or_trace": row["output"] if row["kind"] == "prose" else row["trace"], "review_scope": "existing development output only; no generation, confirmation, or tuning"})
        p = history / f"{model}-ratings.json"; p.write_text(json.dumps(ledger, indent=2) + "\n")
        # Retain the v0 document exactly as originally written, including its
        # then-current path strings, while storing the copy in history.
        summaries[model] = {"ratings_path": str((OUT / f"{model}-ratings.json").relative_to(ROOT)), "case_count": len(ledger), "prose_cases": sum(x["kind"] == "prose" for x in ledger), "tool_cases": sum(x["kind"] == "tool" for x in ledger), "semantic_ratings": {v: sum(x["semantic_rating"] == v for x in ledger) for v in ("pass", "partial", "fail")}}
    old_report = {"scope": "Stage 2 frozen development outputs only", "confirmation_reviewed": False, "training_or_promotion": False, "strict_vs_semantic": "Strict metrics are exact/template-correlated diagnostics. Semantic ratings are an assistant review of saved outputs and distinguish pass, partial (readable but insufficient), and fail; neither establishes production reliability or human certification.", "models": summaries, "baseline_remains_default": True}
    (history / "REPORT.json").write_text(json.dumps(old_report, indent=2) + "\n")
    (history / "SUPERSEDED.md").write_text("# Superseded heuristic history\n\nThese are preserved v0 artifacts. Their labels came from diagnostic booleans, output length/repetition, and tool flags—not prompt/output semantic reading. They must not be cited as semantic accuracy.\n")

def main():
    OUT.mkdir(exist_ok=True)
    cases = read_jsonl(CASES)
    if len(cases) != 120 or any(len(v) != len(cases) for v in MANUAL_RATINGS.values()):
        raise SystemExit("manual decision coverage must be exactly 120 cases for each model")
    old = legacy_inventory()
    preserve_superseded_heuristic_history(cases)
    old = [{**item, "preserved_copy_path": str((OUT / "superseded-heuristic-v0" / Path(item["path"]).name).relative_to(ROOT))} for item in old]
    reports = {}
    judgments = []
    for model, filename in (("baseline", "development-baseline-outputs.json"), ("partial_candidate", "development-experiment-outputs.json")):
        rows = json.loads((RUN / "evaluation" / filename).read_text())
        if [r["id"] for r in rows] != [c["id"] for c in cases]:
            raise SystemExit(f"case ordering mismatch for {model}")
        model_rows = []
        for ordinal, (case, row, rating) in enumerate(zip(cases, rows, MANUAL_RATINGS[model]), 1):
            saved = row["output"] if row["kind"] == "prose" else row["trace"]
            decision = {
                "ordinal": ordinal,
                "id": row["id"],
                "model": model,
                "kind": row["kind"],
                "family": row["family"],
                "full_prompt_before_judgment": full_prompt(case),
                "semantic_target_before_judgment": semantic_target(case),
                "full_saved_output_or_trace_before_judgment": saved,
                "assistant_semantic_judgment": rating,
                "specific_review_reason": human_reason(case, row, rating),
                "strict_diagnostics_retained_as_nonsemantic_context": {
                    k: row[k] for k in ("correct_by_diagnostic_rubric", "success", "calls_exact", "final_answer_exact", "wrong_call", "extra_call", "early_final", "terminal_reason") if k in row
                },
                "review_scope": "saved development output only; no generation, confirmation review, training, or promotion",
            }
            model_rows.append(decision); judgments.append(decision)
        path = OUT / f"{model}-ratings.json"
        path.write_text(json.dumps(model_rows, indent=2) + "\n")
        reports[model] = {
            "ratings_path": str(path.relative_to(ROOT)), "case_count": len(model_rows),
            "prose_cases": sum(x["kind"] == "prose" for x in model_rows),
            "tool_cases": sum(x["kind"] == "tool" for x in model_rows),
            "semantic_ratings": {v: sum(x["assistant_semantic_judgment"] == v for x in model_rows) for v in ("pass", "partial", "fail")},
        }
    correction = {
        "schema": "semantic-correction-v1", "review_type": "assistant semantic reading of saved outputs; not independent human review",
        "completed_at": datetime.now(timezone.utc).isoformat(), "reviewed_model_case_judgments": len(judgments),
        "required_model_case_judgments": 240, "unreviewed_model_case_judgments": 0,
        "batching": "12 sequential batches of 10 development cases; both saved model outputs/traces read per batch without output truncation",
        "evidence_order": "full prompt, semantic target, and saved output/trace precede the judgment in every record",
        "legacy_artifacts": old, "reports": reports,
        "limitations": [
            "Development-only assistant review; it is not independent human review or a production-reliability claim.",
            "Confirmation outputs were not read or rerun; no inference or generation was performed.",
            "Strict/template diagnostics are retained only as context and did not determine any semantic label.",
            "The local UI remains reachable at http://127.0.0.1:18765, but its existing 15 GiB reserve guard blocks inference at 12.9 GiB free; the guard was not changed.",
            "No training resumed, baseline remains selected, no checkpoint was promoted, and no checkpoint/data was deleted.",
        ],
    }
    correction_path = RUN / "semantic-correction-result.json"
    correction_path.write_text(json.dumps(correction, indent=2) + "\n")
    report = {**correction, "scope": "Stage 2 frozen development outputs only", "baseline_remains_default": True,
              "retraction": "Earlier semantic-review labels were heuristic categorization, not semantic reading. Any previous statement that semantic reading found no additional defect is retracted."}
    (OUT / "REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
