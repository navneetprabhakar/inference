"""Protect A, B and the release set without exposing any prompts or rubrics to the fitter."""
import argparse
import json
from pathlib import Path

from protect_split import DEV_SHA, SEALED_SHA, Shield, digest
from protect_validation_b import B_SHA, BShield

DIRECTORY = Path(__file__).resolve().parent / "reports/slot-dialogue"
EXPECTED = "1e06c5d1f3781145a25b7d5ea82390758335b376544d693049b5c9694320cf98"


def main(directory, expected):
    source = directory / "custody-input.jsonl"
    if digest(source.read_bytes()) != expected:
        raise ValueError("Unrecognized candidates")
    shields = (Shield(), BShield())
    denied = []
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    for index, row in enumerate(rows):
        if row["index"] != index:
            raise ValueError("Unexpected row order")
        history = [{"role": "user", "text": row["user"]}]
        if any(shield.reasons(history) for shield in shields):
            denied.append(index)
    receipt = dict(source_sha256=expected, candidate_rows=len(rows), excluded_indices=denied,
                   protected_sha256={"A": DEV_SHA, "B": B_SHA, "release": SEALED_SHA},
                   scope="Existing normalized exact, shape, eight-word shingle and lexical anchor checks. No student outputs were generated.")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    parser.add_argument("--source-sha", default=EXPECTED)
    args = parser.parse_args()
    receipt = main(args.directory, args.source_sha)
    output = args.directory / "protected-custody.json"
    data = json.dumps(receipt, indent=2) + "\n"
    if output.exists() and output.read_text() != data:
        raise ValueError("A different receipt already exists")
    output.write_text(data)
    print("Candidate rows:", receipt["candidate_rows"], "excluded:", receipt["excluded_indices"])
