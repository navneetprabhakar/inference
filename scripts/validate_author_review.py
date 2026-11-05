"""Read-only integrity audit and resumable review-ledger bootstrap for author-only-v2.

This deliberately does *not* certify semantic quality.  Semantic decisions must be
made after reading complete conversations and must retain the original and any
replacement assistant turn in the ledger.
"""
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/author-only-v2/conversations-2500.jsonl"
OUT = ROOT / "reports/author-review-v1"
LEDGER = OUT / "systematic-review-ledger.jsonl"
EOS_ID = 1
ROLE_TOKENS = {"user": "<|user|>", "assistant": "<|assistant|>"}


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def normalized(text):
    return " ".join(text.casefold().split())


def episode_stats(tokenizer, messages):
    ids, supervised = [], []
    for message in messages:
        role = message["role"]
        if role not in ROLE_TOKENS:
            raise ValueError(f"unsupported role: {role}")
        prefix = tokenizer.encode(ROLE_TOKENS[role]).ids
        suffix = "<|endoftext|>" if role == "assistant" else "\n"
        body = tokenizer.encode(message["content"] + suffix).ids
        ids.extend(prefix + body)
        supervised.extend([0] * len(prefix) + [int(role == "assistant")] * len(body))
    return {"tokens": len(ids), "fits_512_context": len(ids) <= 513,
            "final_token_is_eos": bool(ids and ids[-1] == EOS_ID),
            "supervised_final_eos": bool(supervised and supervised[-1] == 1),
            "supervised_targets": sum(supervised)}


def load_rows():
    rows = [json.loads(line) for line in SOURCE.read_text().splitlines() if line]
    manifest = json.loads(SOURCE.with_name("manifest.json").read_text())
    digest = sha_bytes(SOURCE.read_bytes())
    if digest != "f4e2fdc22bd92ea083cc2b97f4684315681306186802855ca996fdc468081c7b":
        raise ValueError("original corpus SHA256 differs from the supplied immutable value")
    if digest != manifest["corpus_sha256"] or len(rows) != 2500:
        raise ValueError("source manifest/count mismatch")
    return rows, digest


def initialize_ledger(rows, source_hash):
    if LEDGER.exists():
        raise FileExistsError(f"refusing to overwrite existing ledger: {LEDGER}")
    sampled = {x["id"]: x for x in json.loads((OUT / "sample-review.json").read_text())}
    records = []
    for index, row in enumerate(rows):
        prior = sampled.get(row["id"])
        records.append({
            "id": row["id"], "original_index": index,
            "source_corpus_sha256": source_hash,
            "original_messages_sha256": sha_bytes(canonical(row["messages"])),
            "review_status": "unreviewed",
            "prior_sample_review": prior,
            "required_fields_for_decision": ["status", "specific_reason", "reviewer_model",
                                             "reviewed_entire_conversation", "before", "after"],
            "note": "No semantic decision recorded. Prior sample findings require recheck, not adoption."
        })
    LEDGER.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))


def audit(rows, source_hash):
    tokenizer = Tokenizer.from_file(str(ROOT / "data/sft-v3/tokenizer.json"))
    ids, full, first, bad_structure, context_overflow, final_eos, supervised_eos = set(), [], [], [], [], 0, 0
    token_counts = []
    for index, row in enumerate(rows):
        messages = row.get("messages")
        if not isinstance(messages, list) or not messages or len(messages) % 2:
            bad_structure.append({"id": row.get("id"), "reason": "empty or odd number of messages"}); continue
        if any(message.get("role") != ("user" if turn % 2 == 0 else "assistant") or
               not isinstance(message.get("content"), str) or not message["content"].strip()
               for turn, message in enumerate(messages)):
            bad_structure.append({"id": row["id"], "reason": "non-alternating roles or blank content"}); continue
        ids.add(row["id"]); full.append(normalized("\n".join(m["content"] for m in messages)))
        first.append(normalized(messages[0]["content"]))
        stats = episode_stats(tokenizer, messages); token_counts.append(stats["tokens"])
        if not stats["fits_512_context"]: context_overflow.append(row["id"])
        final_eos += stats["final_token_is_eos"]; supervised_eos += stats["supervised_final_eos"]
    report = {
        "audit_kind": "mechanical_only_not_semantic_certification",
        "source_corpus_sha256": source_hash, "conversations": len(rows),
        "unique_ids": len(ids), "role_structure_failures": bad_structure,
        "context_overflow_ids": context_overflow,
        "final_eos_count": final_eos, "supervised_final_eos_count": supervised_eos,
        "token_count": {"min": min(token_counts), "max": max(token_counts), "total": sum(token_counts)},
        "normalized_full_duplicate_groups": sum(n > 1 for n in collections.Counter(full).values()),
        "normalized_first_user_duplicate_groups": sum(n > 1 for n in collections.Counter(first).values()),
        "checkpoint": checkpoint_report(),
        "limitations": ["No facts, naturalness, follow-up continuity, or semantic duplicates were judged.",
                        "Held-out approximate overlap needs a distinct corpus-aware screen; this audit does not replace it.",
                        "A passing mechanical audit never authorizes training or inference tuning."]
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "systematic-integrity-v2.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def checkpoint_report():
    artifact = ROOT / "runs/sft-v3/repair-lr3/milestones/2000000/model.safetensors"
    expected = "93bb235b29c8bdff5efe4e14bac223b92b5bc70fecc3023a22d8ed2d9b6fd781"
    actual = sha_bytes(artifact.read_bytes()) if artifact.exists() else None
    return {"artifact": str(artifact.relative_to(ROOT)), "expected_sha256": expected,
            "actual_sha256": actual, "matches": actual == expected, "frozen": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize-ledger", action="store_true")
    args = parser.parse_args()
    rows, source_hash = load_rows()
    if args.initialize_ledger:
        initialize_ledger(rows, source_hash)
    print(json.dumps(audit(rows, source_hash), indent=2))


if __name__ == "__main__":
    main()
