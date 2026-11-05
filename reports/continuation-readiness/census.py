"""Read train-only local sources. Counts are raw ceilings before quality or family admission."""
from collections import Counter, defaultdict
from hashlib import file_digest, sha256
import json
from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tokenizer import load
from broad_teaching import DOLLY_SHA, OASST_SHA, MAP_SHA
from scaled_teaching import SMOLTALK_SHA

DATA = ROOT.parent / "inference-history-20261021/data"


def verified(path, sha):
    with path.open("rb") as stream:
        if file_digest(stream,"sha256").hexdigest()!=sha:
            raise ValueError(f"Local source mismatch: {path}")
    return path


def rows(path):
    with path.open() as stream:
        for line in stream:
            yield json.loads(line)


def main():
    tokenizer=load()
    counts=defaultdict(Counter)
    seen=defaultdict(set)

    def add(name,role,text):
        s=" ".join(unicodedata.normalize("NFKC",text).casefold().split())
        h=sha256(s.encode()).hexdigest()
        if not s or h in seen[name]:
            return
        seen[name].add(h)
        counts[name]["distinct_texts"]+=1
        counts[name]["gpt2_"+role]+=len(tokenizer.encode(text).ids)

    squad=DATA/"grounded-qa-groups-v2"
    eligible=verified(squad/"eligible.jsonl","9f4c2135dcf6185c296295677008666cb67ddf470514f25516e44b08b587bf35")
    first=next(rows(eligible))
    print("squad schema",list(first),flush=True)
    for r in rows(eligible):
        add("SQuAD legacy candidate","context",r.get("context",r.get("paragraph","")))
        add("SQuAD legacy candidate","user",r.get("question",""))
        add("SQuAD legacy candidate","assistant",r.get("answer",""))
    smol=verified(DATA/"conversation-parquet-intake-v3/train.jsonl",SMOLTALK_SHA)
    for r in rows(smol):
        assert r["official_split"]=="train"
        if r["source"] not in ("smol-magpie-ultra-short","smollm-rewrite-30k","smol-contraints","smol-summarize-20k"):
            continue
        for m in r["messages"]:
            if m["role"] in ("user","assistant"):
                add(r["source"],m["role"],m["content"])
    print("smoltalk counted",flush=True)
    split=json.loads(verified(DATA/"iteration-two-oasst2-partitions-v1/mapping.json",MAP_SHA).read_text())
    for tree in rows(verified(DATA/"iteration-two-oasst2-snapshot-v1/trees.jsonl",OASST_SHA)):
        if split[tree["message_tree_id"]]["split"]!="train":
            continue
        pending=[tree["prompt"]]
        while pending:
            node=pending.pop()
            if node["lang"]!="en" or node["deleted"] or node["synthetic"] or not node["review_result"]:
                continue
            labels=node["labels"]
            if any(labels.get(k,{}).get("value",0)>0 for k in ["pii","lang_mismatch","spam","sexual_content","violence","hate_speech","not_appropriate"]):
                continue
            add("OASST approved English train", "assistant" if node["role"]=="assistant" else "user",node["text"])
            pending.extend(node["replies"])
    output=Path(__file__).parent/"local-census.json"
    output.write_text(json.dumps(dict(note="Original, normalized-exact-distinct texts per source; no role delimiters. No quality, rights or cross-source admission. A repeated answer in a new context is counted once in this conservative ceiling.",sources=counts),indent=2)+"\n")
    print(json.dumps(counts,indent=2),flush=True)


if __name__=="__main__":
    main()
