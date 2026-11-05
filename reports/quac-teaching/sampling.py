"""Draw development-quality samples exclusively from the training partition."""
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def stratum(r):
    if any(a["span"]=="CANNOTANSWER" for a in r["annotations"]):return "unanswerable"
    if any(m["text"].startswith(("Yes. ","No. ")) for m in r["history"] if m["role"]=="assistant"):return "yes-no"
    return "extractive"


def sample(rows,salt):
    splits={}
    for r in rows:
        if r["split"]=="train":
            splits.setdefault(stratum(r),[]).append(r)
    return {group:sorted(rs,key=lambda r:sha256((salt+r["dialogue"]).encode()).digest())[:12] for group,rs in splits.items()}


if __name__=="__main__":
    import sys
    raw=[json.loads(l) for l in (ROOT/"data/quac-train-v1/candidates.jsonl").open()]
    sample_rows=sample(raw,sys.argv[1])
    group=sys.argv[2]
    for r in sample_rows[group]:
        print('\n',r["dialogue"],r["title"],'/',r["section"],'\n',' | '.join(x["text"].replace('\n',' ') for x in r["history"]))
