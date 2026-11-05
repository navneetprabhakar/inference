"""One bounded, disposable MPS pilot on fixed shards. No automatic production resume."""
import argparse
import json
import math
import os
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

import checkpoint
from gpt2 import Config, GPT2
from guards import Guard, ResourceStop
from tokenizer import load
from train import backward_rows, optimizer_for

LENGTH = 256
ACCUM = 16
BUDGET = 999424  # 244 complete optimizer updates, each with 4096 targets
PROMPTS = ["A bridge is built to", "The child went to the garden because"]


def main(path, corpus):
    guard = Guard(path, 3600)
    try:
        return run_pilot(path, corpus, guard)
    except Exception as error:
        dest = path/"status.json"
        result = json.loads(dest.read_text()) if dest.exists() else {}
        result.update(stage="distinct-document pilot", state="failed", reason=repr(error))
        dest.write_text(json.dumps(result, indent=2))
        raise
    finally:
        guard.close()


def run_pilot(path, corpus, guard):
    manifest = json.loads((corpus/"manifest.json").read_text())
    identity = dict(seed=61, torch=str(torch.__version__), config=asdict(Config()), dtype="float32",
                    length=LENGTH, accumulation=ACCUM, training_tokens_cap=BUDGET, seconds_cap=3600,
                    lr=3e-4, betas=[.9,.95], warmup=10, weight_decay=.1, gradient_clip=1.,
                    mix="nine wiki then seven story microbatches per update", prompts=PROMPTS,
                    corpus_sha=checkpoint.checksum(corpus/"manifest.json"),
                    source_sha={p:checkpoint.checksum(Path(p)) for p in
                                ["gpt2.py","pilot.py","train.py","tokenizer.py","guards.py","checkpoint.py"]})
    (path/"config.json").write_text(json.dumps(identity,indent=2))
    tokenizer = load()
    streams = {}
    for key, m in manifest["shards"].items():
        file = corpus/(key+".u16")
        if checkpoint.checksum(file) != m["sha256"]:
            raise ValueError("shard checksum mismatch")
        streams[key] = np.memmap(file, mode="r", dtype="<u2")
    source_order = ["wiki"]*9 + ["stories"]*7
    pos = dict(wiki=0, stories=0)
    eval_rows = {}
    unigram = np.ones(50257)
    for name in pos:
        unigram += np.bincount(streams[name+"-train"],minlength=50257)
        data = streams[name+"-validation"]
        offsets = np.linspace(0,len(data)-LENGTH-1,8,dtype=int)
        eval_rows[name] = [torch.tensor(data[i:i+LENGTH+1].astype("int64")[None],device="mps") for i in offsets]
    logp = -np.log(unigram/unigram.sum())
    baseline = {s:float(np.mean([logp[r[0,1:].cpu().numpy()].mean() for r in rows])) for s,rows in eval_rows.items()}
    torch.manual_seed(identity["seed"])
    model = GPT2().to("mps")
    opt = optimizer_for(model)
    step = 0
    curves = []
    status = dict(stage="distinct-document pilot",state="running",step=0,target_tokens=0,unigram=baseline)
    def update():
        status.update(step=step,target_tokens=step*LENGTH*ACCUM,elapsed=time.monotonic()-guard.start,
                      shard_offsets=dict(pos),timestamp=time.time())
        temp = path/"status.tmp"
        temp.write_text(json.dumps(status, indent=2))
        os.replace(temp,path/"status.json")

    @torch.no_grad()
    def measure():
        losses = {}
        for name, rows in eval_rows.items():
            values = []
            for r in rows:
                guard.check()
                values.append(F.cross_entropy(model(r[:,:-1])[0],r[0,1:]).item())
            losses[name] = float(np.mean(values))
        samples = {}
        for prompt in PROMPTS:
            ids = tokenizer.encode(prompt).ids
            for _ in range(16):
                guard.check()
                row = torch.tensor([ids], device="mps")
                ids.append(model(row)[0,-1].argmax().item())
                if ids[-1] == 50256:
                    break
            samples[prompt] = tokenizer.decode(ids)
        curves.append(dict(step=step, validation=losses, completions=samples))
        (path/"evaluation.json").write_text(json.dumps(curves,indent=2))

    def save():
        guard.check(force=True)
        state = dict(identity=identity, step=step, offsets=dict(pos), model=model.state_dict(),
                     optimizer=opt.state_dict(), cpu_rng=torch.get_rng_state(),
                     mps_rng=torch.mps.get_rng_state(), target_tokens=step*4096,
                     elapsed=time.monotonic()-guard.start)
        checkpoint.save(path,state)

    try:
        update()
        measure()
        while step*4096 < BUDGET:
            guard.check()
            opt.zero_grad(set_to_none=True)
            lr = 3e-4 * (min(1,(step+1)/10) if step<10 else
                          .1+.9*(1+math.cos(math.pi*(step-10)/(244-10)))/2)
            for group in opt.param_groups:
                group["lr"] = lr
            step_loss = 0
            next_pos = dict(pos)
            for name in source_order:
                guard.check()
                i = next_pos[name]
                raw = streams[name+"-train"][i:i+LENGTH+1]
                if len(raw) != LENGTH+1:
                    raise ValueError("unique training stream exhausted")
                row = torch.tensor(raw.astype("int64")[None],device="mps")
                step_loss += backward_rows(model,row[:,:-1],row[:,1:],4096).item()
                next_pos[name] += LENGTH
            grad = torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
            opt.step()
            torch.mps.synchronize()
            pos = next_pos
            step += 1
            status.update(train_loss=step_loss,gradient_norm=grad.item(),lr=lr)
            update()
            if step in (1, 10, 30, 60, 120, 180, 244):
                measure()
            if step in (10, 120, 244):
                save()
        status["state"] = "passed" if all(curves[-1]["validation"][s] < curves[0]["validation"][s] for s in pos) and curves[-1]["validation"]["wiki"] < baseline["wiki"] and curves[-1]["validation"]["wiki"] < curves[-2]["validation"]["wiki"] < curves[-3]["validation"]["wiki"] else "failed"
    except ResourceStop as error:
        status.update(state="stopped",reason=str(error))
    finally:
        update()
        print(json.dumps(status),flush=True)
    return status["state"] == "passed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run",type=Path)
    parser.add_argument("corpus",type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if main(args.run,args.corpus) else 1)
