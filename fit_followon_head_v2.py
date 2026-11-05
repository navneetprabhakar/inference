"""Fit one CPU head from eligible training histories; this path never opens the internal panel."""
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
import time

import torch

from compositional_teaching import examples as compositional
from fallback_head import ROOT, UNIT_ALIASES, BagModel, requested_slots, sha
from followon_head_v2 import ACTIONS_V2, inputs, point_features, route_features
from scaled_teaching import examples as scaled
from tool_teaching_varied import records

RUN=ROOT/"runs/working-head-v2"
PUBLIC=ROOT/"reports/working-chat"
SPEC=PUBLIC/"head-v2-protocol.json"


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def history_sha(history):
    return digest(json.dumps(history, sort_keys=True, ensure_ascii=False))


def normal(text):
    return re.sub(r"[^\w]+"," ",text.casefold()).strip()


def negative_pools(spec, varied=None):
    denyfile=PUBLIC/"followon-excluded-histories.json"
    assert sha(denyfile)==spec["fit"]["supplement_denylist_sha256"]
    denied=set(json.loads(denyfile.read_text()))
    varied = fit_sources(spec) if varied is None else varied
    blocked={normal(m["text"]) for r in varied for m in r.history if m["role"]=="user"}
    train,held=[],[]
    seen,held_prompts=set(),set()
    source_pools=[]
    for source,make in (("compositional",compositional),("scaled",scaled)):
        unique={history_sha(row):row for row in make(spec["seed"])}
        keys=sorted(unique.keys()-denied-seen, key=lambda k:digest("head-v2-negative-v1"+k))
        seen.update(keys)
        taken=0
        for key in keys:
            history=unique[key]
            first=normal(history[0]["text"])
            if first in blocked or first in held_prompts:continue
            held.append((source,key,history))
            held_prompts.add(first)
            taken+=1
            if taken==64:break
        if taken!=64:raise ValueError(f"too few independent ordinary histories: {source}")
        source_pools.append((source,unique,keys))
    for source,unique,keys in source_pools:
        taken=0
        for key in keys:
            history=unique[key]
            assert all(m["role"] in ("user","assistant") and "text" in m for m in history)
            if any(normal(m["text"]) in held_prompts for m in history if m["role"]=="user"):continue
            train.append((source,key,history))
            taken+=1
            if taken==1000:break
    assert len(held_prompts)==len(held)==128
    return train,held


def fit_sources(spec):
    denyfile=PUBLIC/"varied-tool-excluded-histories.json"
    assert sha(denyfile)==spec["fit"]["varied_denylist_sha256"]
    denied=set(json.loads(denyfile.read_text()))
    source=ROOT/"tool_teaching_varied.py"
    receipt=json.loads((ROOT/"reports/varied-tool-teaching/receipt.json").read_text())
    assert sha(source)==receipt["source_sha256"]
    rows=records(spec["seed"])
    ordered=digest(json.dumps([r.history for r in rows],sort_keys=True,ensure_ascii=False))
    assert len(rows)==5465 and ordered==spec["fit"]["train_history_digest"]
    allowed=[r for r in rows if history_sha(r.history) not in denied]
    assert len(allowed)==5383
    return allowed


def split_turns(history):
    turns=[]
    for msg in history:
        if msg["role"]=="user":
            turns.append(dict(text=msg["text"], calls=[], answer=None))
        elif msg["role"]=="assistant":
            if "call" in msg:
                turns[-1]["calls"].append(msg["call"])
            else:
                turns[-1]["answer"]=msg["text"]
    return turns


def noncall_label(answer,event,last_request):
    if not event or not event["ok"] or not last_request:return "text"
    args=last_request["arguments"]
    try:
        value=float(answer.strip())
        if value==event["data"]["result"]:return "recall_number"
        if value==args.get("a"):return "recall_operand"
    except (ValueError, TypeError):
        pass
    if "from" in args and UNIT_ALIASES.get(answer.casefold())==args["from"]:
        return "recall_unit"
    return "text"


def gather(route_rows,slot_rows,turns,observations,counts):
    trace=[]
    last_request=None
    previous=None
    for turn in turns:
        for phase in range(len(turn["calls"])+1):
            if phase>=2:break
            user=turn["text"]
            words,old,spans,event=inputs(user,previous,trace,last_request,phase)
            call=turn["calls"][phase] if phase<len(turn["calls"]) else None
            if call:
                args=call["arguments"]
                action="convert" if call["name"]=="convert" else args["op"]
                for slot,kind in requested_slots(action):
                    c=[s for s in spans if s.kind==kind]
                    if not any(s.value==args[slot] for s in c):
                        counts["unmatched_slot_targets"]+=1
                        continue
                    for i,s in enumerate(c):
                        slot_rows[point_features(words,old,c,i,action,slot,phase),int(s.value==args[slot])]+=1
            else:
                action="done" if phase else noncall_label(turn["answer"],event,last_request)
            counts[action]+=1
            route_rows[route_features(words,old,spans,event,phase),ACTIONS_V2.index(action)]+=1
            if call:
                observed=observations[len(trace)]
                assert observed["name"]==call["name"]
                last_request=call
                trace.append(observed)
        previous=turn["text"]


def fit():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    spec=json.loads(SPEC.read_text())
    start=time.monotonic()
    allowed=fit_sources(spec)
    ordinary,test=negative_pools(spec,allowed)
    route_rows,slot_rows,counts=Counter(),Counter(),Counter()
    for lesson in allowed:
        gather(route_rows,slot_rows,split_turns(lesson.history),lesson.observations,counts)
    for _,_,history in ordinary:
        gather(route_rows,slot_rows,split_turns(history),[],counts)
    routes=BagModel.fit(route_rows,len(ACTIONS_V2),spec["seed"])
    ranker=BagModel.fit(slot_rows,2,spec["seed"]+1)
    RUN.mkdir(parents=True,exist_ok=False)
    weights=RUN/"candidate.pt"
    torch.save(dict(actions=list(ACTIONS_V2),routes=routes.state(),ranker=ranker.state()),weights)
    train_ids=[history_sha(r.history) for r in allowed]+[k for _,k,_ in ordinary]
    assert not set(train_ids)&{k for _,k,_ in test}
    params=routes.weights.numel()+ranker.weights.numel()
    record=dict(weights=str(weights.relative_to(ROOT)),sha256=sha(weights),bytes=weights.stat().st_size,
                parameters=params,combined_gpt2_head_parameters=124439808+params,
                training_histories=dict(varied=len(allowed),ordinary=len(ordinary)),
                training_order_sha256=digest("\n".join(train_ids)), action_targets=counts,
                ordinary_negative_ids=[dict(source=s,sha256=k) for s,k,_ in test],
                cpu_seconds=time.monotonic()-start, protocol_sha256=sha(SPEC),
                split_amendment_sha256=sha(PUBLIC/"head-v2-split-amendment.json"),
                source_sha256={n:sha(ROOT/n) for n in ["fit_followon_head_v2.py","followon_head_v2.py","fallback_head.py"]})
    (RUN/"fit.json").write_text(json.dumps(record,indent=2)+"\n")
    (RUN/"train-ids.json").write_text(json.dumps(train_ids)+"\n")
    print({k:v for k,v in record.items() if k not in ("ordinary_negative_ids","source_sha256")},flush=True)


if __name__=="__main__":
    fit()
