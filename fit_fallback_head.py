"""Fit the separately scored CPU routing/slot model using the published screened teaching pools."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import time

import torch

from chat_teaching import examples as chats, natural_examples
from fallback_head import ACTIONS, RECEIPT, ROOT, UNIT_ALIASES, BagModel, lexical, parse, pointer, requested_slots, sha
from tool_teaching import examples as tools

SEED = 1459


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def histories():
    report = RECEIPT.parent
    summary = json.loads((report / "split-summary.json").read_text())
    denyfile = report / "excluded-histories.json"
    if sha(denyfile) != summary["denylist_sha256"] or summary["state"] != "complete":
        raise ValueError("The audited teaching denylist is unavailable or changed")
    denied = set(json.loads(denyfile.read_text()))
    seen = set()
    for pool, make in (("tool",tools),("chat",chats),("natural",natural_examples)):
        rows = make(SEED)
        keys = [digest(json.dumps(row, sort_keys=True, ensure_ascii=False)) for row in rows]
        if digest("\n".join(keys)) != summary["pools"][pool]["ordered_history_hashes_sha256"]:
            raise ValueError(f"Teaching source differs from the audited {pool} pool")
        for key,row in zip(keys,rows):
            if key not in denied and key not in seen:
                seen.add(key)
                yield pool,row


def recall_label(answer, last):
    if not last or not last.get("ok"):
        return "text"
    try:
        if float(answer) == last["data"]["result"]:
            return "recall_number"
    except ValueError:
        pass
    if last["name"] == "convert" and UNIT_ALIASES.get(answer.casefold()) == last["arguments"]["from"]:
        return "recall_unit"
    return "text"


def collect():
    routes, slots, labels, pool_counts = Counter(), Counter(), Counter(), Counter()
    unmatched = 0
    for pool,history in histories():
        pool_counts[pool] += 1
        prev, last_call = None, None
        user = None
        for message in history:
            if message["role"] == "user":
                user = message["text"]
                continue
            if message["role"] == "tool":
                result = message["result"]
                prev = dict(ok="result" in result, name=last_call["name"], arguments=last_call["arguments"])
                if prev["ok"]:
                    prev["data"] = {"result":result["result"]}
                continue
            if user is None:
                continue  # post-dispatch answer belongs to GPT-2, not the routing target
            words, spans = parse(user, prev)
            if "call" in message:
                last_call = message["call"]
                args = last_call["arguments"]
                action = "convert" if last_call["name"]=="convert" else args["op"]
                for slot,kind in requested_slots(action):
                    candidates=[s for s in spans if s.kind==kind]
                    if not any(s.value==args[slot] for s in candidates):
                        unmatched += 1
                        continue
                    for rank,span in enumerate(candidates):
                        features=pointer(words,candidates,rank,action,slot)
                        slots[features,int(span.value==args[slot])] += 1
            else:
                action=recall_label(message["text"],prev)
            routes[lexical(words,spans,prev), ACTIONS.index(action)] += 1
            labels[action] += 1
            user = None
    return routes, slots, dict(pool_counts=pool_counts, labels=labels, unmatched_slot_targets=unmatched)


def main():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    start=time.monotonic()
    routes,slots,info=collect()
    route_net=BagModel.fit(routes,len(ACTIONS),SEED)
    rank_net=BagModel.fit(slots,2,SEED+1)
    root=ROOT/"runs"/"working-head-01"
    root.mkdir(parents=True,exist_ok=True)
    temp=root/"head.tmp"
    torch.save(dict(actions=list(ACTIONS),routes=route_net.state(),ranker=rank_net.state()),temp)
    digest_sha=sha(temp)
    weights=root/f"head-{digest_sha}.pt"
    os.replace(temp,weights)
    params=route_net.weights.numel()+rank_net.weights.numel()
    receipt=dict(version=1, weights=str(weights.relative_to(ROOT)), sha256=digest_sha, bytes=weights.stat().st_size,
                 parameters=params, combined_student_parameters=124439808+params, seed=SEED, device="cpu",
                 denylist_sha256=sha(RECEIPT.parent/"excluded-histories.json"),
                 data_summary_sha256=sha(RECEIPT.parent/"split-summary.json"), seconds=time.monotonic()-start,
                 unique_route_feature_labels=len(routes), unique_pointer_feature_labels=len(slots), **info)
    if RECEIPT.exists():
        previous = json.loads(RECEIPT.read_text())
        if previous["sha256"] != digest_sha:
            raise ValueError("New weights differ from the pinned product head; retained as a separate candidate")
        print(f"Reproduced pinned head SHA-256 {digest_sha}.")
    else:
        RECEIPT.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print(json.dumps(receipt,indent=2))


if __name__=="__main__":
    main()
