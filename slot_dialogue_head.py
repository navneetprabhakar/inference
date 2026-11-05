"""A compact learned dialogue-act proposal for incomplete offline tool requests."""
from collections import Counter, defaultdict
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import re
import time

import torch
from torch import nn
from torch.nn import functional as F

from checkpoint import checksum
from fallback_head import parse
from pretrain import atomic_status

ROOT=Path(__file__).resolve().parent
REPORT=ROOT/"reports/slot-dialogue"
RUN=ROOT/"runs/slot-dialogue-head-01"
CLASSES={"open":("add","subtract","multiply","divide","convert","none"),
         "pending":("supply","revise","cancel","unrelated")}
LEX=re.compile(r"[a-z]+|\d+(?:\.\d+)?|[+*/=×÷−-]")
PUNCT={"#","@","+","*","/","-","×","÷","="}


def features(text):
    words,_=parse(text,None)
    # Preserve unit spellings in addition to their general slot symbol. No operation-specific rules.
    tokens=LEX.findall(text.casefold())
    out={"bias":.2}
    for i,word in enumerate(words):
        out["w:"+word]=1.
        if i:out["b:"+words[i-1]+"_"+word]=1.
        if i<2:out[f"start{i}:"+word]=.45
        if word not in PUNCT:
            marked="^"+word+"$"
            for n in (3,4):
                for j in range(len(marked)-n+1):
                    out["c:"+marked[j:j+n]]=.35
    for word in tokens:
        if word.isalpha():out["r:"+word]=.40
    if words:
        out["end:"+words[-1]]=.4
        out["length:"+str(min(len(words)//4,4))]=.25
    return out,words


def encode_batch(texts,vocab):
    x=torch.zeros((len(texts),len(vocab)),dtype=torch.float32)
    known=[]
    for i,text in enumerate(texts):
        feats,words=features(text)
        for key,value in feats.items():
            index=vocab.get(key)
            if index is not None:x[i,index]=value
        known.append(sum("w:"+w in vocab for w in words)/max(1,len(words)))
    return F.normalize(x,dim=1),known


def active_predict(mode,text,model,state):
    x,known=encode_batch([text],model["vocab"])
    logits=x@model["weight"].T+model["bias"]
    probs=torch.softmax(logits[0],dim=0)
    top,runner=torch.topk(probs,2).values.tolist()
    label=CLASSES[mode][int(probs.argmax())]
    eligible=(known[0]>=state["known_word_fraction_min"] and top>=state["confidence_min"]
              and top-runner>=state["margin_min"])
    return dict(label=label if eligible else None,raw_label=label,confidence=top,margin=top-runner,known_fraction=known[0])


@lru_cache(maxsize=1)
def load_model():
    # Absence of an approved pin keeps this feature disabled.
    pin_file=REPORT/"accepted-pin.json"
    if not pin_file.exists():raise RuntimeError("No approved slot-dialogue head is installed")
    pin=json.loads(pin_file.read_text());weights=RUN/"weights.pt"
    if checksum(weights)!=pin["weights_sha256"] or checksum(REPORT/"protocol.json")!=pin["protocol_sha256"]:
        raise ValueError("slot head weight or protocol pin mismatch")
    if checksum(REPORT/"fit-result.json")!=pin["evaluation_sha256"]:
        raise ValueError("slot head evaluation pin mismatch")
    result=json.loads((REPORT/"fit-result.json").read_text())
    if result["state"]!="accepted":raise ValueError("slot head not accepted")
    state=torch.load(weights,weights_only=True,map_location="cpu")
    count=sum(m["weight"].numel()+m["bias"].numel() for m in state["heads"].values())
    if count!=pin["parameters"]:raise ValueError("slot head coefficient count mismatch")
    return state


def model_size():
    if (REPORT/"v2/accepted-pin.json").is_file():
        from slot_dialogue_head_v2 import model_size as v2_size
        return v2_size()
    return load_model()["parameters"]


@torch.inference_mode()
def classify(text,pending=False):
    """Return a confident act or None. The opening negative class maps to None."""
    if (REPORT/"v2/accepted-pin.json").is_file():
        from slot_dialogue_head_v2 import classify as v2_classify
        return v2_classify(text,pending=pending)
    if not isinstance(text,str) or not 0<len(text.strip())<=256:return None
    state=load_model()
    mode="pending" if pending else "open"
    decision=active_predict(mode,text,state["heads"][mode],state["protocol"])
    label=decision["label"]
    return None if label=="none" else label


def fit(mode,rows,spec):
    forms=defaultdict(Counter)
    for r in rows:forms[r["label"]][r["form"]]+=1
    names=sorted({key for r in rows for key in features(r["user"])[0]})
    vocab={word:i for i,word in enumerate(names)}
    X,_=encode_batch([r["user"] for r in rows],vocab)
    classes=CLASSES[mode]
    y=torch.tensor([classes.index(r["label"]) for r in rows])
    importance=torch.tensor([1/(len(forms[r["label"]])*forms[r["label"]][r["form"]]) for r in rows])
    importance/=importance.sum()
    model=nn.Linear(len(names),len(classes))
    opt=torch.optim.Adam(model.parameters(),lr=spec["learning_rate"])
    for step in range(spec["iterations"]):
        loss=(F.cross_entropy(model(X),y,reduction="none")*importance).sum()
        loss+=spec["l2"]*model.weight.square().sum()/len(classes)
        opt.zero_grad(set_to_none=True);loss.backward();opt.step()
    return dict(vocab=vocab,weight=model.weight.detach().cpu(),bias=model.bias.detach().cpu())


def evaluate(mode,rows,model,spec):
    forms=Counter((r["label"],r["form"]) for r in rows)
    form_totals=Counter();totals=Counter();by=defaultdict(Counter);errors=[]
    for r in rows:
        d=active_predict(mode,r["user"],model,spec)
        pred=d["label"]; correct=pred==r["label"];accept=pred is not None
        mass=1/forms[r["label"],r["form"]]
        for c,w in ((totals,1),(form_totals,mass),(by[r["label"]],1)):
            c['rows']+=w;c['accepted']+=w*accept;c['correct']+=w*correct
        if accept and not correct and len(errors)<16:
            errors.append(dict(user=r["user"],expected=r["label"],predicted=pred,confidence=d["confidence"]))
    def metrics(c):
        return dict(c,precision=c["correct"]/max(1,c["accepted"]),coverage=c["accepted"]/max(1,c["rows"]))
    metrics_row,metrics_form=metrics(totals),metrics(form_totals)
    passed=all(m['precision']>=spec["semantic_precision_min"] and m['coverage']>=spec["coverage_min"]
               for m in [metrics_row,metrics_form])
    return dict(passed=passed,rows=metrics_row,forms=metrics_form,per_label={k:metrics(v) for k,v in by.items()},accepted_errors=errors)


def training_rows():
    spec=json.loads((REPORT/"protocol.json").read_text())
    source=REPORT/"custody-input.jsonl"
    if checksum(source)!=spec["custody_sha256"]:raise ValueError("custody source mismatch")
    original=json.loads((REPORT/"protected-custody.json").read_text())
    newer=json.loads((REPORT/"other-suite-exclusions.json").read_text())
    if newer["input_sha256"]!=spec["custody_sha256"]:raise ValueError("new protected screen mismatch")
    if original.get("input_sha256",original.get("source_sha256"))!=spec["custody_sha256"]:
        raise ValueError("old protected screen mismatch")
    excluded=set(newer["indices"])|set(original.get("excluded_indices",original.get("excluded_row_indices",[])))
    rows=[r for l in source.read_text().splitlines() if (r:=json.loads(l))["index"] not in excluded]
    return spec,rows,excluded


def train():
    torch.set_num_threads(1)
    spec,rows,excluded=training_rows()
    torch.manual_seed(spec["seed"])
    start=time.monotonic()
    RUN.mkdir(exist_ok=False)
    heads={};results={};counts={}
    for mode in CLASSES:
        train_rows=[r for r in rows if r["mode"]==mode and r["split"]=="train"]
        hold=[r for r in rows if r["mode"]==mode and r["split"]=="form-holdout"]
        assert not ({(r["label"],r["form"]) for r in train_rows}&{(r["label"],r["form"]) for r in hold})
        counts[mode]=dict(train=len(train_rows),heldout=len(hold))
        heads[mode]=fit(mode,train_rows,spec)
        results[mode]=evaluate(mode,hold,heads[mode],spec)
    count=sum(m["weight"].numel()+m["bias"].numel() for m in heads.values())
    duration=time.monotonic()-start
    passed=(all(m['passed'] for m in results.values()) and count<=spec['max_coefficients'] and duration<=spec['cpu_seconds_cap'])
    state=dict(heads=heads,parameters=count,protocol=spec)
    dest=RUN/"weights.pt"
    torch.save(state,dest)
    result=dict(state="accepted" if passed else "experimental",parameters=count,weights_sha256=checksum(dest),
                protocol_sha256=checksum(REPORT/"protocol.json"),code_sha256=checksum(Path(__file__)),
                counts=counts,excluded_rows=sorted(excluded),evaluation=results,cpu_seconds=duration)
    atomic_status(REPORT/"fit-result.json",result)
    if passed:
        atomic_status(REPORT/"accepted-pin.json",dict(parameters=count,weights_sha256=result["weights_sha256"],
                      protocol_sha256=result["protocol_sha256"],evaluation_sha256=checksum(REPORT/"fit-result.json")))
    print(json.dumps(dict(state=result['state'],parameters=count,counts=counts,
                          scores={k:{"rows":v["rows"],"forms":v["forms"]} for k,v in results.items()})))


if __name__=="__main__":
    train()
