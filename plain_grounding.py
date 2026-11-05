"""One preregistered, plain-text result-copying diagnostic."""
import argparse
import json
import random
import time
from pathlib import Path

import torch

from checkpoint import checksum
from gpt2 import GPT2
from guards import Guard
from pretrain import atomic_status
from sft import load_base
from tokenizer import EOT, load
from train import backward_rows, optimizer_for

DIRECTORY = Path("reports/plain-grounding")
TRAIN = [
    "A stockroom count was requested. The count tool returned {v}.",
    "The pace sensor displayed {v} during the practice run.",
    "A greenhouse moisture probe returned {v} on the last reading.",
    "A carton scanner produced the following count: {v}.",
    "For the milling test the gauge read {v}.",
    "On the tally sheet, the scoring tool printed {v}.",
    "An archive lookup found {v} matching items.",
    "The coffee dispenser's volume readout shows {v}.",
    "From the seed tray counter we received {v}.",
    "The fabric cutter reports a measured width of {v}.",
]
TEST = [
    "The cave surveyor asked for depth. The sonar reply was {v}.",
    "The kiln controller gave a temperature reading of {v}.",
    "A festival gate checked wristbands. Its output was {v}.",
    "From the ferry terminal's berth lookup: {v}.",
    "The telescope exposure meter settled on {v}.",
    "At the bookbinding bench, the thickness indicator shows {v}.",
    "The apiary scale transmitted {v} after calibration.",
    "A pipe inspector's pressure sensor logged {v}.",
    "On the weaving loom the tension instrument indicated {v}.",
    "In the rehearsal booth, the pitch detector displayed {v}.",
    "The soil assay lists the specimen's reading as {v}.",
    "A mountain hut's visibility instrument recorded {v}.",
    "In the pottery workshop the turntable sensor returned {v}.",
    "The rink technician queried the ice gauge and received {v}.",
    "The baggage carousel reported a load of {v}.",
    "A plank passed the sawmill laser and the display flashed {v}.",
    "The drying cabinet issued a humidity reading of {v}.",
    "The orchestra librarian ran a parts lookup. It found {v}.",
    "The reservoir monitor delivered a level of {v}.",
    "In the signal lab, the pulse reader registered {v}.",
]
PLAIN = "\nReply with the reported number only.\nAnswer:"
JSON_REPLY = '\nReply with the reported number as JSON, using a string field named "text".\nAnswer:'
SEED = 713
RUN = Path("runs/astra-plain-grounding-01")


def examples():
    rng = random.Random(SEED)
    pairs = []
    for i, family in enumerate(TEST):
        a, b, distractor = rng.sample(range(10, 100), 3)
        old = f"Previous reading: {distractor}. "
        sentence = old + family if i % 2 == 0 else family + " " + old.strip()
        pairs.append({"template": sentence, "values": [a,b]})
    teaching = []
    for family in TRAIN:
        for v in range(10,100):
            d = rng.choice([x for x in range(10,100) if x != v])
            old = f"Previous reading: {d}."
            for template in (old+" "+family, family+" "+old):
                teaching.append([template.format(v=v),v])
    memo = [(TRAIN[0].format(v=v),v) for v in (13, 42, 67, 95)]
    return teaching, memo, pairs


def freeze():
    teaching,memo,pairs = examples()
    spec = dict(seed=SEED,learning_rate=.00015,clip_norm=1.,batch=8,
                memorize_max_steps=120,memorize_check_every=5,memorize_required=4,
                teaching_steps=450,training_rows=len(teaching),memorization_rows=memo,
                teaching_templates=TRAIN,holdout=pairs,threshold_pairs=16,
                time_limit_seconds=3600,plain_suffix=PLAIN,json_suffix=JSON_REPLY,
                decoding="greedy, eight tokens plain or 16 JSON; EOT required, trim whitespace, exact decimal value; JSON must be exactly one string text field",
                conditional="If plain passes, same weights and cases with JSON instruction, zero further updates",
                base_sha256="f029b7d3cf7921b72911697c38a6a697608af3646c2d9f8fe7d6ed90eda734a4")
    atomic_status(DIRECTORY/"protocol.json",spec)


def fit_row(tok, text, value):
    prefix = tok.encode(text+PLAIN).ids
    target = tok.encode(" "+str(value)).ids+[EOT]
    ids = prefix + target
    labels = [-100]*(len(prefix)-1)+target
    assert len(ids)-1 == len(labels)
    return ids[:-1],labels


def update(model,opt,rows):
    size = max(len(x) for x,_ in rows)
    inputs = torch.tensor([x+[0]*(size-len(x)) for x,_ in rows],device="mps")
    labels = torch.tensor([y+[-100]*(size-len(y)) for _,y in rows],device="mps")
    opt.zero_grad(set_to_none=True)
    loss = backward_rows(model,inputs,labels,int((labels!=-100).sum()))
    torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
    opt.step()
    return loss.item()


@torch.inference_mode()
def answer(model,tok,text,guard,json_mode=False):
    ids = tok.encode(text+(JSON_REPLY if json_mode else PLAIN)).ids
    output = []
    for _ in range(16 if json_mode else 8):
        guard.check()
        token = model(torch.tensor([ids],device="mps"))[0,-1].argmax().item()
        if token == EOT:
            break
        ids.append(token)
        output.append(token)
    raw = tok.decode(output)
    value = raw.strip() if token == EOT else None
    if json_mode and value is not None:
        from tools import unique_fields
        try:
            obj = json.loads(value,object_pairs_hook=unique_fields)
            value = obj["text"] if type(obj) is dict and obj.keys()=={"text"} and type(obj["text"]) is str else None
        except ValueError:
            value = None
    return dict(raw=raw, terminated=token==EOT, value=value)


def score(model,tok,pairs,guard,json_mode=False):
    records=[]
    for pair in pairs:
        replies=[]
        for value in pair["values"]:
            text=pair["template"].format(v=value)
            reply=answer(model,tok,text,guard,json_mode)
            replies.append(dict(prompt=text,expected=value,correct=reply["value"]==str(value),**reply))
        records.append(dict(replies=replies,passed=all(r["correct"] for r in replies)))
    return dict(pairs_passed=sum(r["passed"] for r in records),
                members_correct=sum(x["correct"] for r in records for x in r["replies"]),records=records)


def run():
    spec=json.loads((DIRECTORY/"protocol.json").read_text())
    teaching,memo,pairs=examples()
    assert pairs==spec["holdout"] and len(teaching)==spec["training_rows"]
    guard=Guard(RUN,spec["time_limit_seconds"])
    result=dict(state="running",protocol_sha256=checksum(DIRECTORY/"protocol.json"),
                code_sha256=checksum(Path(__file__)))
    try:
        torch.manual_seed(SEED)
        rng=random.Random(SEED)
        sha=spec["base_sha256"]
        base=Path("runs/astra-candidate-01")/f"step-000600-{sha}.pt"
        model=GPT2().to("mps")
        model.load_state_dict(load_base(base,sha))
        opt=optimizer_for(model)
        for group in opt.param_groups:
            group["lr"]=spec["learning_rate"]
        tok=load()
        memo_rows=[fit_row(tok,*r) for r in memo]*2
        result["baseline"]=score(model,tok,pairs,guard)
        atomic_status(RUN/"results.json",result)
        for step in range(1,spec["memorize_max_steps"]+1):
            guard.check()
            loss=update(model,opt,memo_rows)
            if step%5==0:
                replies=[answer(model,tok,text,guard) for text,_ in memo]
                hits=sum(r["value"]==str(v) for r,(_,v) in zip(replies,memo))
                result["memorization"]=dict(step=step,loss=loss,correct=hits,replies=replies)
                if hits==len(memo):
                    break
        if result["memorization"]["correct"]!=len(memo):
            result["state"]="memorization_failed"
            return
        data=[fit_row(tok,*r) for r in teaching]
        result["state"]="teaching"
        atomic_status(RUN/"results.json",result)
        for step in range(1,spec["teaching_steps"]+1):
            guard.check()
            loss=update(model,opt,rng.sample(data,spec["batch"]))
            if step%25==0:
                with (RUN/"loss.jsonl").open("a") as f:
                    f.write(json.dumps(dict(step=step,loss=loss))+"\n")
        guard.check(force=True)
        result["plain"]=score(model,tok,pairs,guard)
        torch.save(model.state_dict(),RUN/"weights.pt")
        result["weights_sha256"]=checksum(RUN/"weights.pt")
        if result["plain"]["pairs_passed"]>=spec["threshold_pairs"]:
            result["json"]=score(model,tok,pairs,guard,True)
        result["state"]="plain_passed" if "json" in result else "transfer_failed"
    except Exception as exc:
        result.update(state="stopped",reason=repr(exc))
        raise
    finally:
        result["elapsed_seconds"]=time.time()-guard.wall_start
        atomic_status(RUN/"results.json",result)
        guard.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--freeze",action="store_true")
    if parser.parse_args().freeze:
        freeze()
    else:
        run()
