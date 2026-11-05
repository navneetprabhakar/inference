"""Reconstruct sampler membership of each exact-wording case, without fitting."""
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import random
import sys

import torch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from chat_teaching import examples as chat, natural_examples
from checkpoint import checksum
from compositional_teaching import examples as compositional
from fit_working import chat_row
from tokenizer import load


def main():
    path=ROOT/"runs/working-chat-02"
    spec=json.loads((Path(__file__).parent/"protocol.json").read_text())
    config=json.loads((path/"config.json").read_text())
    seed=config["seed"]
    tok=load()
    pools={}
    lengths={}
    denied=set(json.loads((ROOT/"reports/working-chat/excluded-histories.json").read_text()))
    extra=set(json.loads((ROOT/"reports/working-chat/followon-excluded-histories.json").read_text()))
    for name,make,exclude in (("chat",chat,denied),("natural",natural_examples,denied),("compositional",compositional,extra)):
        histories=[h for h in make(seed) if sha256(json.dumps(h,sort_keys=True,ensure_ascii=False).encode()).hexdigest() not in exclude]
        encoded=[chat_row(tok,h) for h in histories]
        assert sha256(json.dumps(encoded).encode()).hexdigest()==config["dataset_sha256"][name]
        lengths[name]=[len(ids) for ids,labels in encoded]
        pools[name]=histories
    wanted={(case["pool"],case["index"]):case for case in spec["cases"]}
    steps=defaultdict(list)
    rng=random.Random(seed)
    for step in range(1,config["steps"]+1):
        name=rng.choices(list(config["weights"]),weights=list(config["weights"].values()))[0]
        indices=rng.choices(range(config["corpus_counts"][name]),k=config["batch"]*4)
        if name in lengths:indices.sort(key=lambda i:lengths[name][i])
        offset=rng.choice(range(0,len(indices),config["batch"]))
        for index in indices[offset:offset+config["batch"]]:
            if (name,index) in wanted:steps[name,index].append(step)
        if step==4800:
            entry=next(e for e in json.loads((path/"latest.json").read_text()) if e["file"].startswith("step-004800-"))
            assert checksum(path/entry["file"])==entry["sha256"]
            snapshot=torch.load(path/entry["file"],weights_only=True,map_location="cpu",mmap=True)
            assert snapshot["rng"]==rng.getstate()
            del snapshot
    for (name,index),case in wanted.items():
        h=pools[name][index]
        assert [m["text"] for m in h if m["role"]=="user"]==case["exact"]
        assert [m["text"] for m in h if m["role"]=="assistant"]==case["reference"]
        assert case["optimizer_steps"]==steps[name,index] and case["prior_uses"]==len(steps[name,index])
    print(f"Verified {len(wanted)} exposed histories and the optimizer-step 4800 sampler state.")


if __name__=="__main__":
    main()
