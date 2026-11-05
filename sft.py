"""One locked, bounded fixture-SFT diagnostic from a hash-pinned retained base."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import random
import time

import torch

import checkpoint
from dialogue import VERSION, training_row
from evaluate_sft import DEVELOPMENT, DEV_SHA, evaluate
from gpt2 import Config, GPT2
from guards import Guard, ResourceStop
from prepare_sft import DEST, REPORT
from pretrained_base import load_base
from pretrain import atomic_status
from tokenizer import ASSETS, load
from train import backward_rows, optimizer_for
from verify_dialogue import PROBE, PROBE_SHA256

SPEC = REPORT/"budget.json"
SPEC_SHA256 = "233b7c4f84be3f2092512b35690cc668498279710723a73ef5a9c372f8c82d64"


def frozen_budget():
    if checkpoint.checksum(SPEC) != SPEC_SHA256:
        raise ValueError("budget differs from the preregistered SFT experiment")
    return json.loads(SPEC.read_text())


def load_teaching(tokenizer, spec):
    checks = [(DEST, spec["training_sha256"]), (PROBE, PROBE_SHA256),
              (DEVELOPMENT, DEV_SHA)]
    for file, sha in checks:
        if checkpoint.checksum(file) != sha:
            raise ValueError(f"data hash mismatch: {file.name}")
    rows=[training_row(tokenizer,json.loads(line)["history"]) for line in DEST.open()]
    totals=(sum(len(r.inputs) for r in rows)*spec["passes"],
            sum(r.target_count for r in rows)*spec["passes"])
    if totals != (spec["input_cap"],spec["target_cap"]):
        raise ValueError("mixture does not match frozen budget")
    return rows


def schedule(rows, spec):
    batches=[]
    for epoch in range(spec["passes"]):
        order=list(range(len(rows)))
        random.Random(spec["seed"]+epoch).shuffle(order)
        size=spec["rows_per_update"]
        batches.extend(order[i:i+size] for i in range(0,len(order),size))
    return batches


def update(model, opt, rows, indices, step, steps, spec, check):
    model.train()
    target_count=sum(rows[i].target_count for i in indices)
    lr=spec["learning_rate"]*min(1, (step+1)/spec["warmup_steps"])*(
        .1+.9*(1+math.cos(math.pi*max(0,step-spec["warmup_steps"])/max(1,steps-spec["warmup_steps"])))/2)
    for group in opt.param_groups:
        group["lr"]=lr
    opt.zero_grad(set_to_none=True)
    loss=0.
    device=next(model.parameters()).device
    for index in indices:
        check()
        row=rows[index]
        inputs=torch.tensor([row.inputs],device=device)
        labels=torch.tensor([row.labels],device=device)
        loss+=backward_rows(model,inputs,labels,target_count).item()
    if not math.isfinite(loss):
        raise ValueError("nonfinite SFT loss")
    norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
    opt.step()
    if device.type=="mps":
        torch.mps.synchronize()
    return dict(train_ce=loss,gradient_norm=norm.item(),lr=lr)


def candidate(guard, base, base_sha, resume):
    path=guard.path
    spec=frozen_budget()
    if spec["probe_sha256"]!=PROBE_SHA256 or spec["conversation_dev_sha256"]!=DEV_SHA:
        raise ValueError("budget does not bind the frozen development assets")
    identity=dict(spec=spec,base_sha256=base_sha,base_file=str(base.resolve()),format=VERSION,
                  model=asdict(Config()),torch=str(torch.__version__),tokenizer=ASSETS,
                  code={file:checkpoint.checksum(Path(__file__).parent/file) for file in (
                      "sft.py","evaluate_sft.py","evaluate.py","verify_dialogue.py","dialogue.py","train.py","gpt2.py",
                      "tokenizer.py","guards.py","checkpoint.py","prepare_sft.py","pretrain.py","pretrained_base.py","tools/__init__.py")})
    if resume:
        old=json.loads((path/"status.json").read_text())
        if old["state"]!="running" or json.loads((path/"config.json").read_text())!=identity:
            raise ValueError("resume requires interrupted identical SFT run")
    else:
        old={}
        atomic_status(path/"config.json",identity)
    before=old.get("active_seconds",0)+max(0,time.time()-old.get("timestamp",time.time()))
    counters=dict(input_tokens=0,target_tokens=0,step=0)
    reserved_inputs=old.get("reserved_input_tokens",0)
    reserved_targets=old.get("reserved_target_tokens",0)
    status=dict(stage="SFT diagnostic",state="running",phase="setup")

    def active():
        return before+time.monotonic()-guard.start

    def check(force=False):
        guard.check(force=force)
        if active()>=spec["active_seconds"]:
            raise ResourceStop("SFT active budget exhausted")

    def publish():
        status.update(counters,active_seconds=active(),wall_seconds=time.time()-guard.wall_start,
                      reserved_input_tokens=reserved_inputs,reserved_target_tokens=reserved_targets,
                      remaining_inputs=spec["input_cap"]-reserved_inputs,
                      remaining_active_seconds=max(0,spec["active_seconds"]-active()),timestamp=time.time())
        atomic_status(path/"status.json",status)

    def capture():
        check(force=True)
        checkpoint.save(path,dict(identity=identity,model=model.state_dict(),optimizer=opt.state_dict(),
                                  **counters,cpu_rng=torch.get_rng_state(),mps_rng=torch.mps.get_rng_state(),
                                  active_seconds=active(),elapsed=time.time()-guard.wall_start,
                                  reserved_inputs=reserved_inputs,reserved_targets=reserved_targets))

    def assessment(name):
        dest=path/f"{name}-development.json"
        if dest.exists():
            report=json.loads(dest.read_text())
            if report["probe"]["probe_sha256"]!=PROBE_SHA256:
                raise ValueError("stale evaluation artifact")
            return report
        status["phase"]=f"evaluate-{name}"
        publish()
        report=evaluate(model,tokenizer,check)
        atomic_status(dest,report)
        return report

    try:
        check(force=True)
        tokenizer=load()
        rows=load_teaching(tokenizer,spec)
        batches=schedule(rows,spec)
        weights=load_base(base,base_sha)
        torch.manual_seed(spec["seed"])
        model=GPT2().to("mps")
        model.load_state_dict(weights)
        del weights
        opt=optimizer_for(model)
        if resume:
            saved=checkpoint.load(path,identity)
            for key in counters:
                counters[key]=saved[key]
            step=counters["step"]
            if not 0<=step<=len(batches):
                raise ValueError("invalid SFT batch cursor")
            completed=[rows[i] for batch in batches[:step] for i in batch]
            if (counters["input_tokens"]!=sum(len(r.inputs) for r in completed) or
                    counters["target_tokens"]!=sum(r.target_count for r in completed)):
                raise ValueError("SFT counters do not match immutable sampler position")
            model.load_state_dict(saved["model"])
            opt.load_state_dict(saved["optimizer"])
            torch.set_rng_state(saved["cpu_rng"])
            torch.mps.set_rng_state(saved["mps_rng"])
            reserved_inputs=max(saved["reserved_inputs"],reserved_inputs)
            reserved_targets=max(saved["reserved_targets"],reserved_targets)
            del saved
        else:
            capture()
        publish()
        if counters["step"] and not (path/"base-development.json").exists():
            raise ValueError("base evaluation missing after optimizer updates")
        assessment("base")
        status["phase"]="fit"
        while counters["step"]<len(batches):
            check()
            step=counters["step"]
            indices=batches[step]
            inputs=sum(len(rows[i].inputs) for i in indices)
            targets=sum(rows[i].target_count for i in indices)
            if (reserved_inputs+inputs>spec["input_cap"] or
                    reserved_targets+targets>spec["target_cap"]):
                raise ResourceStop("remaining reserved budget cannot cover the next update")
            reserved_inputs+=inputs
            reserved_targets+=targets
            publish()
            status.update(update(model,opt,rows,indices,step,len(batches),spec,check))
            counters.update(step=step+1,input_tokens=counters["input_tokens"]+inputs,
                            target_tokens=counters["target_tokens"]+targets)
            publish()
            with (path/"metrics.jsonl").open("a") as stream:
                stream.write(json.dumps(status)+"\n")
            if counters["step"]%20==0 or counters["step"]==len(batches):
                capture()
        entry=checkpoint.protect(path)
        report=assessment("endpoint")
        passed=report["probe"]["passed"]
        status.update(state="review_required" if passed else "failed",phase="done",
                      reason="probe passed; adjudicate complete conversations" if passed else "counterfactual transfer gate failed",
                      endpoint_sha256=entry["sha256"],skills=report["probe"]["skills"])
    except ResourceStop as error:
        status.update(state="stopped",reason=str(error))
    except Exception as error:
        status.update(state="failed",reason=f"{type(error).__name__}: {error}")
        raise
    finally:
        publish()
    return status["state"]=="review_required"


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("base",type=Path)
    p.add_argument("base_sha256")
    p.add_argument("run",type=Path)
    p.add_argument("--resume",action="store_true")
    a=p.parse_args()
    if a.resume and json.loads((a.run/"status.json").read_text())["state"]!="running":
        raise SystemExit("Only an interrupted running SFT diagnostic can resume")
    guard=Guard(a.run,frozen_budget()["elapsed_seconds"],resume=a.resume)
    try:
        passed=candidate(guard,a.base,a.base_sha256,a.resume)
    finally:
        guard.close()
    raise SystemExit(0 if passed else 1)
