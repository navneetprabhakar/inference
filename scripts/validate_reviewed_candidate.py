"""Audit every retained repair with the actual student tokenizer.

The immutable source is evidence, not the object being admitted. Edited
assistant messages are tokenized and masked as they occur in the projection.
"""
import collections
import argparse
import hashlib
import json
import re
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "data/author-review-v1/reviewed-candidate.jsonl"
LEDGER = ROOT / "reports/author-review-v1/systematic-review-ledger.jsonl"
SOURCE = ROOT / "data/author-only-v2/conversations-2500.jsonl"
OUT = ROOT / "reports/author-review-v1/derived-candidate-validation.json"
EOS_ID = 1
ROLES = {"user": "<|user|>", "assistant": "<|assistant|>"}


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def norm(text): return " ".join(text.casefold().split())
def shingles(text):
    words = re.findall(r"\w+", norm(text))
    return {tuple(words[i:i + 5]) for i in range(len(words) - 4)}


def episode_stats(tokenizer, messages):
    ids, weights, role_mask_violations = [], [], []
    for message in messages:
        prefix = tokenizer.encode(ROLES[message["role"]]).ids
        body = tokenizer.encode(message["content"] + ("<|endoftext|>" if message["role"] == "assistant" else "\n")).ids
        prefix_weights = [0] * len(prefix)
        body_weights = [int(message["role"] == "assistant")] * len(body)
        ids += prefix + body
        weights += prefix_weights + body_weights
        if any(prefix_weights): role_mask_violations.append("role_prefix_supervised")
        if message["role"] == "user" and any(body_weights): role_mask_violations.append("user_content_supervised")
        if message["role"] == "assistant" and not all(body_weights): role_mask_violations.append("assistant_content_unmasked")
    return {"tokens": len(ids), "fits_512_context": len(ids) <= 513,
            "final_token_is_eos": bool(ids and ids[-1] == EOS_ID),
            "supervised_final_eos": bool(weights and weights[-1] == 1),
            "supervised_targets": sum(weights), "mask_length": max(0, len(weights) - 1),
            "role_mask_violations": role_mask_violations}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=CANDIDATE)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--corrections", type=Path)
    args = parser.parse_args()
    candidate_path = args.candidate if args.candidate.is_absolute() else ROOT / args.candidate
    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    corrections_path = (args.corrections if args.corrections and args.corrections.is_absolute() else ROOT / args.corrections) if args.corrections else None
    rows = [json.loads(x) for x in candidate_path.read_text().splitlines() if x]
    source = [json.loads(x) for x in SOURCE.read_text().splitlines() if x]
    ledger = [json.loads(x) for x in LEDGER.read_text().splitlines() if x]
    tokenizer = Tokenizer.from_file(str(ROOT / "data/sft-v3/tokenizer.json"))
    source_by_id = {row["id"]: row for row in source}
    ledger_by_id = {row["id"]: row for row in ledger}
    corrections_by_id = {}
    if corrections_path:
        corrections_by_id = {row["id"]: row for row in (json.loads(x) for x in corrections_path.read_text().splitlines() if x)}
    ids, bad, full, first, token_counts = [], [], [], [], []
    token_failures, role_mask_failures, provenance_failures, provenance_label_failures, user_turn_failures, repairs = [], [], [], [], [], []
    for row in rows:
        ids.append(row.get("id")); messages = row.get("messages")
        if not isinstance(messages, list) or not messages or len(messages) % 2 or any(
            m.get("role") != ("user" if i % 2 == 0 else "assistant") or not isinstance(m.get("content"), str) or not m["content"].strip()
            for i, m in enumerate(messages)):
            bad.append(row.get("id")); continue
        full.append(norm("\n".join(m["content"] for m in messages)))
        first.append(norm(messages[0]["content"]))
        stats = episode_stats(tokenizer, messages); token_counts.append(stats["tokens"])
        if stats["role_mask_violations"]: role_mask_failures.append({"id": row["id"], **stats})
        if not (stats["fits_512_context"] and stats["final_token_is_eos"] and stats["supervised_final_eos"] and stats["supervised_targets"]):
            token_failures.append({"id": row["id"], **stats})
        original = source_by_id.get(row["id"])
        entry = corrections_by_id.get(row["id"], ledger_by_id.get(row["id"]))
        meta = row.get("source", {})
        expected_original_hash = hashlib.sha256(json.dumps((original or {}).get("messages"), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest() if original else None
        if not original or not entry or meta.get("original_messages_sha256") != expected_original_hash or entry.get("decision", {}).get("before") != (original or {}).get("messages"):
            provenance_failures.append({"id": row["id"], "reason": "source/ledger identity mismatch"})
        if entry and (entry.get("review_status") or entry.get("decision", {}).get("status")) == "repair":
            repairs.append(row["id"])
            if entry.get("decision", {}).get("after") != messages:
                provenance_failures.append({"id": row["id"], "reason": "repair projection differs from ledger after"})
            before_users = [m["content"] for m in entry["decision"]["before"] if m["role"] == "user"]
            after_users = [m["content"] for m in messages if m["role"] == "user"]
            if before_users != after_users:
                user_turn_failures.append({"id": row["id"], "reason": "repair changed, removed, or reordered a user turn"})
        labels = original.get("provenance", {}) if original else {}
        if not labels.get("method"):
            provenance_label_failures.append({"id": row["id"], "reason": "missing source attribution method", "available_fields": sorted(labels)})
    protected = {}
    for version in ["sft-v1", "sft-v2", "sft-v3"]:
        for split in ["dev", "test"]:
            path = ROOT / "data" / version / (split + ".jsonl")
            if path.exists():
                for line in path.read_text().splitlines():
                    record = json.loads(line)
                    for message in record.get("episode", record.get("messages", [])):
                        if message.get("role") == "user":
                            protected.setdefault(norm(message["content"]), []).append(str(path.relative_to(ROOT)))
    exact, near = [], []
    protected_shingles = [(text, shingles(text)) for text in protected]
    for row in rows:
        for message in row["messages"]:
            if message["role"] != "user": continue
            text = norm(message["content"]); candidate_shingles = shingles(text)
            if text in protected: exact.append({"id": row["id"], "sources": protected[text]})
            if len(candidate_shingles) >= 5:
                for protected_text, reference_shingles in protected_shingles:
                    if protected_text != text and len(reference_shingles) >= 5:
                        score = len(candidate_shingles & reference_shingles) / len(candidate_shingles | reference_shingles)
                        if score >= .8: near.append({"id": row["id"], "score": score})
    failed_ids = {failure["id"] for failure in token_failures}
    report = {
        "kind": "derived_candidate_actual_tokenizer_and_lexical_overlap_audit_not_semantic_certification",
        "candidate": str(candidate_path.relative_to(ROOT)), "candidate_sha256": sha(candidate_path), "records": len(rows), "unique_ids": len(set(ids)), "role_structure_failures": bad,
        "tokenizer": {"path": "data/sft-v3/tokenizer.json", "sha256": sha(ROOT / "data/sft-v3/tokenizer.json"),
                      "all_retained_records_tokenized": len(token_counts) == len(rows), "context_limit_tokens": 513,
                      "token_count": {"min": min(token_counts), "max": max(token_counts), "total": sum(token_counts)}, "failures": token_failures,
                      "role_mask_failures": role_mask_failures},
        "repaired_records": {"count": len(repairs), "all_tokenized_with_actual_student_tokenizer": not bool(set(repairs) & failed_ids),
                             "ids_with_token_failures": sorted(set(repairs) & failed_ids)},
        "source_and_ledger_identity": {"source_records": len(source), "ledger_records": len(ledger), "correction_records": len(corrections_by_id), "failures": provenance_failures,
            "note": "Original-source content checks validate identity only; edited assistant content is validated against ledger after and candidate tokenization."},
        "repair_user_turn_preservation": {"repairs_checked": len(repairs), "failures": user_turn_failures},
        "source_attribution_and_license_metadata": {"attribution_failures": provenance_label_failures,
            "note": "Per-row provenance is source attribution, not a legal license assertion. Missing redundant per-row license/dataset fields is reported as unknown metadata, not proof that a row is unusable for local inference."},
        "normalized_full_duplicate_groups": sum(n > 1 for n in collections.Counter(full).values()),
        "normalized_first_user_duplicate_groups": sum(n > 1 for n in collections.Counter(first).values()),
        "heldout_exact_user_turns": exact, "heldout_near_user_turns": near,
        "limitations": ["Lexical overlap does not prove or rule out semantic dependence.", "Passing token/mask checks does not approve training or establish semantic quality."]}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
