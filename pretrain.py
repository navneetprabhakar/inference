"""Train from random weights or the protected pre-SFT base under a fresh immutable budget."""
import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import time

import numpy as np
import torch

import checkpoint
from gpt2 import Config, GPT2, next_token_loss
from guards import Guard, ResourceStop
from pretrained_base import continuation_parent, load_base
from tokenizer import ASSETS, load
from train import backward_rows, optimizer_for

LENGTH = 256
MICROBATCHES = 16
TOKENS_PER_STEP = LENGTH * MICROBATCHES
MILESTONES = (0, .10, .25, .50, .75, 1.)
PROMPTS = ("A bridge is built to", "The child went to the garden because")
CONTRASTS = (
    ("The second shelf holds an orange vase. The vase is", " orange", " grey"),
    ("The second shelf holds a grey vase. The vase is", " grey", " orange"),
    ("At dawn the bell rang. It rang at", " dawn", " dusk"),
    ("At dusk the bell rang. It rang at", " dusk", " dawn"),
)


def atomic_status(path, value):
    # Called by the single OS-locked worker. Sync before consuming reserved work.
    temp = path.with_suffix(".tmp")
    with temp.open("w") as stream:
        json.dump(value, stream, allow_nan=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    checkpoint.sync_dir(path.parent)


class Shards:
    def __init__(self, directory, mix, evaluation_rows, device):
        meta = json.loads((directory / "manifest.json").read_text())["shards"]
        self.order = [s for s, n in mix.items() for _ in range(n)]
        self.train = {}
        self.validation = {}
        self.offsets = dict.fromkeys(mix, 0)
        self.device = device
        for source in mix:
            for split in ("train", "validation"):
                key = f"{source}-{split}"
                file = directory / (key + ".u16")
                if checkpoint.checksum(file) != meta[key]["sha256"]:
                    raise ValueError(f"checksum mismatch: {key}")
                data = np.memmap(file, mode="r", dtype="<u2")
                if len(data) != meta[key]["tokens"] or len(data) <= LENGTH:
                    raise ValueError(f"invalid shard size: {key}")
                if split == "train":
                    self.train[source] = data
                else:
                    if len(data) < LENGTH * evaluation_rows + 1:
                        raise ValueError(f"insufficient disjoint evaluation windows: {key}")
                    offsets = np.linspace(0, len(data)-LENGTH-1, evaluation_rows, dtype=int)
                    self.validation[source] = [self.tensor(data, i) for i in offsets]

    def tensor(self, array, offset):
        return torch.from_numpy(array[offset:offset+LENGTH+1].astype("int64")[None]).to(self.device)

    def batch(self, source, offsets):
        pos = offsets[source]
        if pos + LENGTH >= len(self.train[source]):
            raise ValueError(f"no fresh targets remain: {source}")
        offsets[source] += LENGTH
        return self.tensor(self.train[source], pos)


@torch.no_grad()
def evaluate(model, shards, tokenizer, check):
    losses = {}
    for source, rows in shards.validation.items():
        values = []
        for row in rows:
            check()
            values.append(next_token_loss(model, row).item())
        losses[source] = float(np.mean(values))
    samples = {}
    for prompt in PROMPTS:
        ids = tokenizer.encode(prompt).ids
        for _ in range(24):
            check()
            token = model(torch.tensor([ids], device=shards.device))[0, -1].argmax().item()
            if token == 50256:
                break
            ids.append(token)
        samples[prompt] = tokenizer.decode(ids)
    contrasts = []
    for prompt, right, wrong in CONTRASTS:
        check()
        row = torch.tensor([tokenizer.encode(prompt).ids], device=shards.device)
        logits = model(row)[0, -1]
        a, b = [tokenizer.encode(s).ids for s in (right, wrong)]
        if len(a) != 1 or len(b) != 1:
            raise ValueError("contrast labels must be single tokens")
        contrasts.append(float((logits[a[0]]-logits[b[0]]).item()))
    if not all(math.isfinite(v) for v in (*losses.values(), *contrasts)):
        raise ValueError("nonfinite development metric")
    return dict(validation=losses, samples=samples, contrast_logit_margins=contrasts)


def validate_spec(spec):
    for key in ("target_tokens", "warmup_steps", "validation_rows_per_source"):
        if type(spec[key]) is not int or spec[key] <= 0:
            raise ValueError(f"{key} must be a positive integer")
    for key in ("active_seconds", "elapsed_seconds"):
        if not math.isfinite(spec[key]) or spec[key] <= 0:
            raise ValueError(f"{key} must be positive and finite")
    for key in ("minimum_ce_improvement", "material_ce_regression"):
        if not math.isfinite(spec[key]) or spec[key] < 0:
            raise ValueError(f"{key} must be nonnegative and finite")
    if spec["target_tokens"] % TOKENS_PER_STEP:
        raise ValueError("budget must be a multiple of tokens per update")
    peak_lr = spec.get("peak_lr", 3e-4)
    if not math.isfinite(peak_lr) or not 0 < peak_lr <= 3e-4:
        raise ValueError("invalid peak learning rate")
    steps = spec["target_tokens"] // TOKENS_PER_STEP
    mix = spec["mix"]
    if (any(type(n) is not int or n <= 0 for n in mix.values()) or
            sum(mix.values()) != MICROBATCHES or spec["primary"] not in mix):
        raise ValueError("invalid source mix or primary source")
    corpus = Path(spec["corpus"])
    if checkpoint.checksum(corpus/"manifest.json") != spec["manifest_sha256"]:
        raise ValueError("budget refers to different data")
    meta = json.loads((corpus/"manifest.json").read_text())["shards"]
    for source, count in mix.items():
        if meta[source+"-train"]["tokens"] < count * LENGTH * steps + 1:
            raise ValueError(f"budget exceeds unique targets in {source}")
    return steps


def candidate(guard, spec, model_config, device, previous):
    path = guard.path
    steps = validate_spec(spec)
    identity = dict(spec=spec, model=asdict(model_config), device=device, tokenizer=ASSETS, dtype="fp32",
                    torch=str(torch.__version__), tokens_per_step=TOKENS_PER_STEP,
                    code={name: checkpoint.checksum(Path(__file__).with_name(name)) for name in
                          ("pretrain.py", "train.py", "gpt2.py", "checkpoint.py", "guards.py", "tokenizer.py")})
    parent = continuation_parent(spec, model_config)
    if parent is not None:
        identity["initialization"] = dict(mode="local_pre_sft_weights", parent=parent, optimizer="fresh_adamw")
        identity["code"]["pretrained_base.py"] = checkpoint.checksum(Path(__file__).with_name("pretrained_base.py"))
    if previous is None:
        atomic_status(path / "config.json", identity)
    elif json.loads((path / "config.json").read_text()) != identity:
        raise ValueError("resume config differs from original identity")

    status = dict(stage="extended pretraining", state="running", step=0, target_tokens=0,
                  attempt=1 if previous is None else previous["attempt"] + 1)
    # A process killed between heartbeats cannot provide its exact stop time.
    # Charge the unobserved interval conservatively, including any downtime.
    active_before = 0.0
    charged_gap = 0.0
    reserved = 0
    if previous is not None:
        charged_gap = max(0.0, time.time() - previous["timestamp"])
        active_before = previous["active_elapsed"] + charged_gap
        reserved = previous["reserved_target_tokens"]
    step = 0
    history = []
    misses = 0
    milestones = {round(steps * f) for f in MILESTONES}
    last_capture = guard.start
    shards = None
    offsets = dict.fromkeys(spec["mix"], 0)
    terminal = None

    def active_elapsed():
        return active_before + time.monotonic() - guard.start

    def check(force=False):
        guard.check(force=force)
        if active_elapsed() >= spec["active_seconds"]:
            raise ResourceStop("active budget exhausted")

    def update():
        active = active_elapsed()
        elapsed = time.time() - guard.wall_start
        tokens = step * TOKENS_PER_STEP
        active_rate = tokens / active if active > 0 else 0.
        status.update(step=step, input_tokens=tokens, target_tokens=tokens, elapsed=elapsed,
                      active_elapsed=active, charged_resume_gap_seconds=charged_gap,
                      reserved_target_tokens=reserved, remaining_target_tokens=spec["target_tokens"] - reserved,
                      remaining_active_seconds=max(0, spec["active_seconds"] - active),
                      remaining_elapsed_seconds=max(0, spec["elapsed_seconds"] - elapsed),
                      observed_tokens_per_second=tokens / max(elapsed, .001), active_tokens_per_second=active_rate,
                      eta_active_seconds=(steps-step)*TOKENS_PER_STEP/active_rate if active_rate else None,
                      next_source_offsets=dict(offsets), timestamp=time.time())
        atomic_status(path / "status.json", status)

    def capture(protected):
        nonlocal last_capture
        check(force=True)
        state = dict(identity=identity, step=step, model=model.state_dict(), optimizer=opt.state_dict(),
                     offsets=dict(offsets), cpu_rng=torch.get_rng_state(),
                     mps_rng=torch.mps.get_rng_state() if device == "mps" else None,
                     input_tokens=step * TOKENS_PER_STEP, target_tokens=step * TOKENS_PER_STEP,
                     reserved_target_tokens=reserved, elapsed=time.time()-guard.wall_start,
                     active_elapsed=active_elapsed(), history=history, failed_windows=misses,
                     terminal=terminal, protected=protected)
        checkpoint.save(path, state)
        if protected:
            checkpoint.protect(path)
        last_capture = time.monotonic()
        check()

    try:
        check(force=True)
        tokenizer = load()
        shards = Shards(Path(spec["corpus"]), spec["mix"], spec["validation_rows_per_source"], device)
        check(force=True)
        torch.manual_seed(spec["seed"])
        model = GPT2(model_config).to(device)
        if previous is None and parent is not None:
            parent_file = Path(parent["path"])
            if parent_file.stat().st_size != parent["bytes"]:
                raise ValueError("pre-SFT base size differs from its acceptance report")
            model.load_state_dict(load_base(parent_file, parent["sha256"], terminal=parent), strict=True)
            check(force=True)
        opt = optimizer_for(model)
        if previous is not None:
            saved = checkpoint.load(path, identity)
            step = saved["step"]
            expected_offsets = {name: step * count * LENGTH for name, count in spec["mix"].items()}
            if (saved["offsets"] != expected_offsets or saved["target_tokens"] != step * TOKENS_PER_STEP
                    or saved["input_tokens"] != saved["target_tokens"] or not 0 <= step <= steps):
                raise ValueError("checkpoint cursor or token count mismatch")
            reserved = max(reserved, saved["reserved_target_tokens"])
            if not step * TOKENS_PER_STEP <= reserved <= spec["target_tokens"] or reserved % TOKENS_PER_STEP:
                raise ValueError("invalid reserved target count")
            offsets = saved["offsets"]
            history, misses, terminal = saved["history"], saved["failed_windows"], saved["terminal"]
            active_before = max(active_before, saved["active_elapsed"])
            if saved["protected"]:
                checkpoint.protect(path)
            model.load_state_dict(saved["model"])
            opt.load_state_dict(saved["optimizer"])
            torch.set_rng_state(saved["cpu_rng"])
            if device == "mps":
                torch.mps.set_rng_state(saved["mps_rng"])
            del saved
            atomic_status(path / "development.json", history)
        update()
        while terminal is None:
            check()
            if step in milestones and (not history or step != history[-1]["step"]):
                result = evaluate(model, shards, tokenizer, check)
                result["step"] = step
                history.append(result)
                if step:
                    primary = spec["primary"]
                    delta = history[-2]["validation"][primary] - result["validation"][primary]
                    result["primary_ce_improvement"] = delta
                    misses = misses + 1 if delta < spec["minimum_ce_improvement"] else 0
                    if delta < -spec["material_ce_regression"] or misses >= 2:
                        terminal = dict(state="failed", reason="development improvement gate")
                    elif step == steps:
                        terminal = dict(state="passed" if misses == 0 else "failed", reason="token budget reached")
                atomic_status(path / "development.json", history)
                capture(protected=True)
            elif time.monotonic() - last_capture >= 600:
                capture(protected=False)
            if terminal is not None:
                break
            if reserved + TOKENS_PER_STEP > spec["target_tokens"]:
                raise ResourceStop("target budget exhausted before selected weights reached the final milestone")
            # Reserve a full update before any work. A crash can lose model progress,
            # but replaying that update can never exceed the authorized token ceiling.
            reserved += TOKENS_PER_STEP
            update()
            opt.zero_grad(set_to_none=True)
            lr = spec.get("peak_lr", 3e-4) * min((step+1)/spec["warmup_steps"], 1.) * (
                .1+.9*(1+math.cos(math.pi*max(0, step-spec["warmup_steps"])/max(1, steps-spec["warmup_steps"])))/2)
            for group in opt.param_groups:
                group["lr"] = lr
            step_loss = 0.
            next_offsets = dict(offsets)
            for source in shards.order:
                check()
                row = shards.batch(source, next_offsets)
                step_loss += backward_rows(model, row[:, :-1], row[:, 1:], TOKENS_PER_STEP).item()
            if not math.isfinite(step_loss):
                raise ValueError("nonfinite training loss")
            grad = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
            opt.step()
            if device == "mps":
                torch.mps.synchronize()
            offsets = next_offsets
            step += 1
            status.update(train_ce=step_loss, gradient_norm=grad.item(), lr=lr)
            update()
            if step % 10 == 0:
                with (path / "metrics.jsonl").open("a") as log:
                    log.write(json.dumps(status, allow_nan=False) + "\n")
        status.update(terminal)
    except ResourceStop as error:
        status.update(state="stopped", reason=str(error))
    except Exception as error:
        status.update(state="failed", reason=f"{type(error).__name__}: {error}")
        raise
    finally:
        update()
    return status["state"] == "passed"


def run(config_file, path, resume=False, *, device="mps", model_config=None):
    spec = json.loads(config_file.read_text())
    guard = Guard(path, spec["elapsed_seconds"], resume=resume)
    try:
        previous = None
        if resume:
            previous = json.loads((path / "status.json").read_text())
            if previous["state"] != "running":
                raise ValueError("only an interrupted running candidate may resume")
        try:
            return candidate(guard, spec, model_config or Config(), device, previous)
        except Exception as error:
            # Setup errors can precede the candidate's first status snapshot.
            status_path = path / "status.json"
            status = json.loads(status_path.read_text()) if status_path.exists() else {}
            if status.get("state") != "failed":
                status.update(stage="extended pretraining", state="failed", timestamp=time.time(),
                              reason=f"{type(error).__name__}: {error}")
                atomic_status(status_path, status)
            raise
    finally:
        guard.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("run", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    raise SystemExit(0 if run(args.config, args.run, args.resume) else 1)
