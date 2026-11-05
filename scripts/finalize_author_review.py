"""Validate the assistant-review ledger and build its explicitly derived candidate.

This never writes the immutable 2,500-record source.  The candidate is not an
admitted training set: it is the deterministic keep/repair projection of a
fully auditable assistant review ledger.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/author-only-v2/conversations-2500.jsonl"
LEDGER = ROOT / "reports/author-review-v1/systematic-review-ledger.jsonl"
OUT = ROOT / "data/author-review-v1/reviewed-candidate.jsonl"
REPORT = ROOT / "reports/author-review-v1/finalization.json"
SOURCE_HASH = "f4e2fdc22bd92ea083cc2b97f4684315681306186802855ca996fdc468081c7b"


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def valid_messages(messages):
    return (isinstance(messages, list) and messages and len(messages) % 2 == 0 and all(
        isinstance(m, dict) and m.get("role") == ("user" if i % 2 == 0 else "assistant")
        and isinstance(m.get("content"), str) and m["content"].strip()
        for i, m in enumerate(messages)))


def main():
    source_bytes = SOURCE.read_bytes()
    assert digest_bytes(source_bytes) == SOURCE_HASH, "immutable source changed"
    rows = [json.loads(x) for x in source_bytes.splitlines() if x]
    ledger = [json.loads(x) for x in LEDGER.read_text().splitlines() if x]
    assert len(rows) == len(ledger) == 2500
    errors, candidate, sample_outcomes = [], [], []
    counts = Counter()
    for index, (row, record) in enumerate(zip(rows, ledger)):
        status = record.get("review_status")
        counts[status] += 1
        decision = record.get("decision")
        if record.get("id") != row.get("id") or record.get("original_index") != index:
            errors.append([index, "identity"]); continue
        if record.get("source_corpus_sha256") != SOURCE_HASH or record.get("original_messages_sha256") != digest_bytes(canonical(row["messages"])):
            errors.append([index, "source provenance"]); continue
        required = ["status", "specific_reason", "reviewer_model", "model_provenance", "independent_human_review", "reviewed_entire_conversation", "before", "after", "reviewed_at_utc"]
        if status not in {"keep", "repair", "exclude"} or not isinstance(decision, dict) or any(k not in decision or decision[k] in (None, "") for k in required):
            errors.append([index, "missing decision evidence"]); continue
        if decision["status"] != status or decision["before"] != row["messages"] or not decision["reviewed_entire_conversation"]:
            errors.append([index, "decision/source disagreement"]); continue
        if decision["reviewer_model"] != "gpt-5.6-terra" or decision["independent_human_review"] is not False:
            errors.append([index, "reviewer provenance"]); continue
        if not valid_messages(decision["after"]):
            errors.append([index, "invalid after structure"]); continue
        if (status == "keep" and decision["after"] != row["messages"]) or (status == "repair" and decision["after"] == row["messages"]):
            errors.append([index, "invalid status/change relation"]); continue
        if record.get("prior_sample_review") is not None:
            sample_outcomes.append({"id": row["id"], "rechecked_status": status})
        if status != "exclude":
            candidate.append({
                "id": row["id"], "messages": decision["after"], "source": {
                    "original_corpus_sha256": SOURCE_HASH,
                    "original_index": index,
                    "original_messages_sha256": record["original_messages_sha256"],
                    "assistant_review_status": status,
                    "ledger": "reports/author-review-v1/systematic-review-ledger.jsonl",
                    "reviewer_kind": "Codex CLI assistant review",
                    "reviewer_model": decision["reviewer_model"],
                    "model_provenance": decision["model_provenance"],
                    "independent_human_review": False,
                },
            })
    assert not errors, errors[:20]
    payload = "".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in candidate).encode()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(payload)
    report = {
        "kind": "deterministic_assistant_review_projection_not_training_admission",
        "source": str(SOURCE.relative_to(ROOT)), "source_sha256": SOURCE_HASH,
        "ledger": str(LEDGER.relative_to(ROOT)), "ledger_records": len(ledger),
        "decision_counts": dict(counts), "unreviewed": counts["unreviewed"],
        "evidence_validation_errors": errors,
        "prior_sample_rechecks": {"count": len(sample_outcomes), "outcomes": dict(Counter(x["rechecked_status"] for x in sample_outcomes)), "records": sample_outcomes},
        "derived_candidate": str(OUT.relative_to(ROOT)), "derived_records": len(candidate),
        "derived_sha256": digest_bytes(payload),
        "reviewer": {"kind": "Codex CLI assistant review", "actual_model": "gpt-5.6-terra", "model_provenance": "externally selected Codex CLI flag; not independently server-attested", "independent_human_review": False},
        "limitations": ["A completed assistant ledger is not independent human certification.", "The candidate has not been approved for training.", "Excluded originals remain only in the immutable source and audit ledger."],
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
