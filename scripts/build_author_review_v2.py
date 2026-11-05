"""Build a versioned, evidence-preserving correction of the reviewed corpus.

The v1 source and ledger remain immutable.  This projection applies only the
two records named in the v2 correction ledger and records the inherited v1
decision evidence for every other retained row.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/author-only-v2/conversations-2500.jsonl"
V1_LEDGER = ROOT / "reports/author-review-v1/systematic-review-ledger.jsonl"
CORRECTIONS = ROOT / "reports/author-review-v2/corrections.jsonl"
OUT = ROOT / "data/author-review-v2/reviewed-candidate.jsonl"
REPORT = ROOT / "reports/author-review-v2/projection.json"
SOURCE_SHA = "f4e2fdc22bd92ea083cc2b97f4684315681306186802855ca996fdc468081c7b"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def valid(messages):
    return isinstance(messages, list) and messages and len(messages) % 2 == 0 and all(
        message.get("role") == ("user" if index % 2 == 0 else "assistant")
        and isinstance(message.get("content"), str) and message["content"].strip()
        for index, message in enumerate(messages)
    )


def main():
    assert digest(SOURCE.read_bytes()) == SOURCE_SHA, "immutable source changed"
    source = [json.loads(line) for line in SOURCE.read_text().splitlines() if line]
    base = {row["id"]: row for row in (json.loads(line) for line in V1_LEDGER.read_text().splitlines() if line)}
    corrections = {row["id"]: row for row in (json.loads(line) for line in CORRECTIONS.read_text().splitlines() if line)}
    assert set(corrections) == {"local-author-v1-00780", "local-author-v1-02099"}
    candidate, errors = [], []
    for index, original in enumerate(source):
        entry = corrections.get(original["id"], base.get(original["id"]))
        if not entry:
            errors.append([original["id"], "missing decision evidence"]); continue
        decision = entry["decision"]
        if entry.get("original_index") != index or decision.get("before") != original["messages"]:
            errors.append([original["id"], "source identity mismatch"]); continue
        if decision.get("status") not in {"keep", "repair", "exclude"} or not valid(decision.get("after")):
            errors.append([original["id"], "invalid decision"]); continue
        if decision["status"] == "repair":
            before_users = [m["content"] for m in original["messages"] if m["role"] == "user"]
            after_users = [m["content"] for m in decision["after"] if m["role"] == "user"]
            if before_users != after_users:
                errors.append([original["id"], "repair changed user turn"]); continue
        if decision["status"] == "exclude":
            continue
        candidate.append({
            "id": original["id"], "messages": decision["after"],
            "source": {
                "original_corpus_sha256": SOURCE_SHA, "original_index": index,
                "original_messages_sha256": digest(canonical(original["messages"])),
                "assistant_review_status": decision["status"],
                "base_ledger": "reports/author-review-v1/systematic-review-ledger.jsonl",
                "correction_ledger": "reports/author-review-v2/corrections.jsonl" if original["id"] in corrections else None,
                "reviewer_kind": "Codex CLI assistant review", "reviewer_model": decision["reviewer_model"],
                "independent_human_review": False,
            },
        })
    assert not errors, errors[:10]
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in candidate).encode()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(payload)
    report = {"kind": "versioned_v2_correction_projection_not_training_admission", "source": str(SOURCE.relative_to(ROOT)),
              "source_sha256": SOURCE_SHA, "base_ledger": str(V1_LEDGER.relative_to(ROOT)),
              "corrections": str(CORRECTIONS.relative_to(ROOT)), "corrected_ids": sorted(corrections),
              "records": len(candidate), "candidate": str(OUT.relative_to(ROOT)), "candidate_sha256": digest(payload),
              "errors": errors, "training_approved": False}
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
