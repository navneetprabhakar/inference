"""Persist explicit, resumable full-conversation semantic review decisions.

This tool never changes the immutable source corpus.  A reviewer must read the
displayed entire conversations before using --decide.  `keep` records retain
the original messages; `repair` requires a full replacement messages JSON and
`exclude` retains the original only in the audit ledger.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/author-only-v2/conversations-2500.jsonl"
LEDGER = ROOT / "reports/author-review-v1/systematic-review-ledger.jsonl"
MODEL = "gpt-5.6-terra"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load():
    rows = [json.loads(line) for line in SOURCE.read_text().splitlines() if line]
    ledger = [json.loads(line) for line in LEDGER.read_text().splitlines() if line]
    assert len(rows) == len(ledger) == 2500
    return rows, ledger


def show(rows, ledger, start, count):
    for i in range(start, min(start + count, len(rows))):
        row, record = rows[i], ledger[i]
        print(f"\n===== INDEX {i} | {row['id']} | {record['review_status']} =====")
        for message in row["messages"]:
            print(f"{message['role'].upper()}: {message['content']}")


def decide(rows, ledger, start, count, status, reason, replacement_file):
    if status == "repair" and not replacement_file:
        raise ValueError("repair requires --replacement-file with an id -> messages mapping")
    replacements = json.loads(Path(replacement_file).read_text()) if replacement_file else {}
    changed = []
    for i in range(start, min(start + count, len(rows))):
        record, row = ledger[i], rows[i]
        if record["review_status"] != "unreviewed":
            raise ValueError(f"index {i} is already {record['review_status']}; do not overwrite")
        before = row["messages"]
        after = replacements.get(row["id"], before)
        if status == "repair" and after == before:
            raise ValueError(f"repair for {row['id']} has no changed replacement")
        if status != "repair" and after != before:
            raise ValueError("only repair may change messages")
        record.update({
            "review_status": status,
            "decision": {
                "status": status,
                "specific_reason": reason,
                "reviewer_model": MODEL,
                "model_provenance": "externally selected Codex CLI flag; not independently server-attested",
                "independent_human_review": False,
                "reviewed_entire_conversation": True,
                "before": before,
                "after": after,
                "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        })
        changed.append(record)
    LEDGER.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in ledger))
    print(json.dumps({"updated": len(changed), "start": start, "status": status,
                      "ids": [x["id"] for x in changed]}, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--show", action="store_true")
    p.add_argument("--decide", choices=["keep", "repair", "exclude"])
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--count", type=int, required=True)
    p.add_argument("--reason")
    p.add_argument("--replacement-file")
    args = p.parse_args()
    rows, ledger = load()
    if args.show:
        show(rows, ledger, args.start, args.count)
    if args.decide:
        if not args.reason:
            p.error("--reason is required with --decide")
        decide(rows, ledger, args.start, args.count, args.decide, args.reason, args.replacement_file)


if __name__ == "__main__":
    main()
