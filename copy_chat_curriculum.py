"""Only frozen training histories. False endings are contrastive negatives, never CE targets."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random

from chat_teaching import examples as chat, natural_examples
from compositional_teaching import FORMS, records as paired_records
from fit_working import chat_row, copy_row
from followon_curriculum import additional_pools
from local_chat import encode_frame
from no_robots_teaching import examples as no_robots
from plain_grounding import TRAIN
from quac_teaching import examples as quac
from scaled_teaching import examples as scaled
from squad_teaching import examples as squad
from taskmaster_teaching import examples as taskmaster_sft
from tool_teaching import examples as tools
from tool_teaching_varied import examples as varied
from checkpoint import checksum

ROOT=Path(__file__).resolve().parent
PUBLIC=ROOT/"reports/working-chat"
SEED=1459
PINS={
    "split-summary.json":"e664711ee86d697576de6896f4df4eace55a3fdcae139c2dbe44bc88a8acde05",
    "excluded-histories.json":"3cc001eebe01ac72186c946b54d89fe9f838d8b4929da897073f43f7707bc95b",
    "broad-excluded-histories.json":"37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "followon-excluded-histories.json":"37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "varied-tool-excluded-histories.json":"0e6fd8b156ccdb9a6dbc380eff488c4bf1774ba7f30a1c745a022b9efea0dfea",
    "followon-source-pins.json":"c0294f80238ab297caf79d32ee351d48c8ad737160ecb34e6465654a257fb0f7",
    "human-admission-summary.json":"9e4889374fb3f324ad5a7d3d0e65c1e144355e19f9df26ae9b697e9d078be143",
    "human-sft-excluded-histories.json":"e33873b6314c5abba9d9a1dec2e12c2f055faace8e9329b619acb1a47dd40bf6",
    "no-robots-excluded-histories.json":"37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
}
HUMAN_FILES={
    "squad":"data/squad-training-v1/train.jsonl",
    "quac":"data/quac-train-v1/train.jsonl",
    "taskmaster_sft":"data/taskmaster2/sft-train.jsonl",
    "no_robots":"data/no-robots/train.jsonl",
}
NO_ROBOTS_FILE_SHA="86b1860cb445ad1cbb4afcaeb820ba7992e476e1f1fb91e1707a3d4e80b55627"
NO_ROBOTS_POOL_SHA="0632503dee7918ba00c0375821baf9b98827bffb47bb5f32345eb1e5f183f009"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def history_hash(value):
    return digest(json.dumps(value,sort_keys=True,ensure_ascii=False).encode())


def checked(condition,message):
    if not condition:
        raise ValueError(message)


def allowed_rows(histories,denied,tok):
    return [chat_row(tok,h) for h in histories if history_hash(h) not in denied]


def original_copy_rows(tok):
    # Never invoke the joint teaching/holdout generator. Only the TRAIN forms
    # contribute, with deterministic, distinct distractors and both answer formats.
    rng=random.Random(SEED)
    rows=[]
    for template in TRAIN:
        for value in range(10,100):
            other=rng.choice([n for n in range(10,100) if n!=value])
            previous=f"Previous reading: {other}."
            text=template.format(v=value)
            for prompt in (previous+" "+text,text+" "+previous):
                for json_mode in (False,True):
                    rows.append(copy_row(tok,prompt,value,json_mode))
    return rows


def final_answer_row(tok,history,answer):
    if history[-1].get("role")!="assistant" or "text" not in history[-1] or not isinstance(answer,str):
        raise ValueError("expected a final assistant text")
    replaced=[*history[:-1],{"role":"assistant","text":answer}]
    inputs,labels=chat_row(tok,replaced)
    _,body=encode_frame(tok,"assistant",{"text":answer})
    checked(labels[-len(body):]==body,"final-answer shift mismatch")
    return inputs,[-100]*(len(labels)-len(body))+list(body)


def split_compositions(tok,denied,pin,check):
    held={}
    for family,forms in FORMS.items():
        count=max(1,min(2,round(.18*len(forms))))
        ranked=sorted(range(len(forms)),key=lambda i:history_hash(["copy-form-split-v1",family,forms[i]]))
        held[family]=set(ranked[:count])
    groups=defaultdict(dict)
    all_histories=[]
    train_histories=[]
    held_rows=set()
    reserved_histories=set()
    for record in paired_records(SEED):
        h=record["history"]
        family,form=record["family"],record["form"]
        key=family,form,record["pair"]
        group=groups[key]
        checked(record["variant"] not in group,"duplicate counterfactual member")
        group[record["variant"]]=h
        all_histories.append(h)
        if form in held[family]:
            held_rows.add(history_hash(chat_row(tok,h)))
            reserved_histories.add(history_hash(h))
        else:
            train_histories.append(h)
    random.Random(SEED).shuffle(all_histories)
    checked(history_hash(all_histories)==pin,"compositional pool differs from the frozen source")
    random.Random(SEED).shuffle(train_histories)
    pairs=[]
    choices=defaultdict(list)
    skipped={"denied":0,"same_final":0}
    train_exclusions=denied|reserved_histories
    for i,((family,form,pair_id),members) in enumerate(groups.items()):
        if i%250==0:check()
        checked(members.keys()=={0,1},"incomplete counterfactual pair")
        a,b=members[0],members[1]
        aa,bb=a[-1]["text"],b[-1]["text"]
        if aa==bb:
            skipped["same_final"]+=1
            continue
        af=[*a[:-1],{"role":"assistant","text":bb}]
        bf=[*b[:-1],{"role":"assistant","text":aa}]
        excluded=denied if form in held[family] else train_exclusions
        if any(history_hash(h) in excluded for h in (a,b,af,bf)):
            skipped["denied"]+=1
            continue
        if form in held[family]:
            key=history_hash(["copy-probe-pair-v1",family,form,pair_id,history_hash(a),history_hash(b)])
            choices[family,form].append((key,dict(family=family,form=form,pair=pair_id,members=[a,b])))
        else:
            pairs.append((final_answer_row(tok,a,aa),final_answer_row(tok,a,bb),
                          final_answer_row(tok,b,bb),final_answer_row(tok,b,aa)))
    probe=[]
    for family,forms in sorted(held.items()):
        for form in sorted(forms):
            picked=sorted(choices[family,form],key=lambda x:x[0])[:2]
            checked(len(picked)==2,f"insufficient eligible probe pairs for {family}/{form}")
            probe.extend(x[1] for x in picked)
    checked(len(probe)>=18 and bool(pairs),"empty counterfactual panels")
    meta=dict(method="Whole forms ranked by SHA-256; two eligible differing-answer pairs per held form",
              seed=SEED,source_pool_sha256=pin,held_histories=len(held_rows),training_histories=len(train_histories),
              held_forms={k:[dict(id=i,template=FORMS[k][i]) for i in sorted(v)] for k,v in sorted(held.items())},
              probe_pair_ids=[dict(family=r["family"],form=r["form"],pair=r["pair"],
                                   member_hashes=[history_hash(h) for h in r["members"]]) for r in probe],
              probe_sha256=history_hash(probe), conditional="Greedy exact final text with all preceding gold frames; both members must pass.")
    return train_histories,held_rows,pairs,skipped,probe,meta


def row_digest(rows):
    hasher=hashlib.sha256()
    for row in rows:
        hasher.update(json.dumps(row,separators=(",",":")).encode()+b"\n")
    return hasher.hexdigest()


def prepare(tok,check=lambda:None):
    for name,expected in PINS.items():
        checked(checksum(PUBLIC/name)==expected,f"custody pin mismatch: {name}")
    denied=set(json.loads((PUBLIC/"excluded-histories.json").read_text()))
    summary=json.loads((PUBLIC/"split-summary.json").read_text())
    pools={"copy":original_copy_rows(tok)}
    for name,make in (("chat",chat),("natural",natural_examples),("tool",tools)):
        check()
        histories=make(SEED)
        actual=digest("\n".join(map(history_hash,histories)).encode())
        checked(actual==summary["pools"][name]["ordered_history_hashes_sha256"],f"unverified {name} histories")
        pools[name]=allowed_rows(histories,denied,tok)
    pins=json.loads((PUBLIC/"followon-source-pins.json").read_text())
    for name,make in (("scaled",scaled),("varied",varied)):
        check()
        checked(history_hash(make(SEED))==pins[name],f"unverified {name} source")
    # The broad receipt itself uses its own seed; its loader verifies source files and reviewed IDs.
    del histories
    pair_deny=set()
    for name in PINS:
        if name.endswith("excluded-histories.json"):
            pair_deny.update(json.loads((PUBLIC/name).read_text()))
    train_comps,held_rows,pairs,skipped,probe,split=split_compositions(tok,pair_deny,pins["compositional"],check)
    weights=additional_pools(tok,SEED,pools,chat_row,copy_row,compositional_histories=train_comps)
    checked(abs(sum(weights.values())-1)<1e-8,"invalid inherited CE mix")
    weights={name:.75*weight for name,weight in weights.items()}

    human=json.loads((PUBLIC/"human-admission-summary.json").read_text())
    human_denied=set(json.loads((PUBLIC/"human-sft-excluded-histories.json").read_text()))
    nr_denied=set(json.loads((PUBLIC/"no-robots-excluded-histories.json").read_text()))
    eligible={}
    for name,make in (("squad",squad),("quac",quac),("taskmaster_sft",taskmaster_sft),("no_robots",no_robots)):
        check()
        info=human["pools"].get(name,{})
        file_sha=NO_ROBOTS_FILE_SHA if name=="no_robots" else info["file_sha256"]
        pool_sha=NO_ROBOTS_POOL_SHA if name=="no_robots" else info["source_pool_sha256"]
        checked(checksum(ROOT/HUMAN_FILES[name])==file_sha,f"unverified human SFT file: {name}")
        hs=make(SEED)
        checked(history_hash(hs)==pool_sha,f"unverified human SFT pool: {name}")
        pools[name]=allowed_rows(hs,nr_denied if name=="no_robots" else human_denied,tok)
        eligible[name]=len(pools[name])
        expected=77 if name=="no_robots" else info["eligible"]
        checked(eligible[name]==expected,f"wrong admitted count for {name}")
    weights.update({name:.25*n/sum(eligible.values()) for name,n in eligible.items()})
    checked(pools.keys()==weights.keys() and all(pools.values()),"missing CE pool")
    checked(abs(sum(weights.values())-1)<1e-8,"invalid final mix")
    blocked_cross_pool={}
    for name,rows in pools.items():
        clean=[r for r in rows if history_hash(r) not in held_rows]
        blocked_cross_pool[name]=len(rows)-len(clean)
        checked(bool(clean),"empty CE pool after reserved form exclusion")
        pools[name]=clean
    info={"pool_rows":{name:len(rows) for name,rows in pools.items()},"mixture":weights,
          "pool_sha256":{name:row_digest(rows) for name,rows in pools.items()},
          "contrast_pairs":len(pairs),"contrast_skipped":skipped,"contrast_sha256":row_digest(pairs),
          "custody_sha256":PINS,"blocked_cross_pool":blocked_cross_pool,
          "form_split_sha256":history_hash(split), "probe_sha256":split["probe_sha256"]}
    return pools,weights,pairs,probe,split,info
