"""Training-only role-preserving Taskmaster-2 clarification histories."""
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from random import Random

ROOT=Path(__file__).resolve().parent
DEST=ROOT/"data/taskmaster2"

@lru_cache(maxsize=1)
def records():
    f=DEST/"sft-train.jsonl"
    expected=json.loads((ROOT/"reports/taskmaster2/receipt.json").read_text())["files"][f.name]["sha256"]
    if sha256(f.read_bytes()).hexdigest()!=expected:raise ValueError("TM2 train hash mismatch")
    rows=[json.loads(line) for line in f.open()]
    if any(r["split"]!="train" or r["usage"]!="sft" for r in rows):raise ValueError("Invalid training row")
    return rows

def examples(seed):
    rows=[deepcopy(r["history"]) for r in records()]
    Random(seed).shuffle(rows)
    return rows

def pretraining_documents():
    """Yield labeled dialogue excerpts for unsupervised text modeling only."""
    src=DEST/"pretrain-only-train.jsonl"
    info=json.loads((ROOT/"reports/taskmaster2/receipt.json").read_text())["files"][src.name]
    if sha256(src.read_bytes()).hexdigest()!=info["sha256"]:raise ValueError("TM2 illustrative file hash mismatch")
    for line in src.open():
        row=json.loads(line)
        if row["usage"]!="pretrain-only" or row["split"]!="train":raise ValueError("Unexpected TM2 usage")
        text="\n".join(m["role"].capitalize()+": "+m["text"] for m in row["history"])
        yield row["conversation_id"],text
