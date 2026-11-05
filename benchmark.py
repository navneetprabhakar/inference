"""Time one disposable 124M MPS worker, including validation and checkpoint restore."""
import argparse
from collections import deque
import json
import math
import os
import time
from pathlib import Path

import numpy as np
import torch

import checkpoint
from gpt2 import GPT2, next_token_loss
from guards import Guard, ResourceStop
from pilot import ACCUM, LENGTH
from train import backward_rows, optimizer_for


WARMUP = 5
MEASURED_SECONDS = 30 * 60
ELAPSED_CAP = 45 * 60
SOURCES = ["wiki"] * 9 + ["stories"] * 7


def write_status(path, status):
    status["timestamp"] = time.time()
    temp = path / "status.tmp"
    temp.write_text(json.dumps(status, indent=2))
    os.replace(temp, path / "status.json")


def measure(guard, corpus, status):
    path = guard.path
    if len(SOURCES) != ACCUM:
        raise ValueError("benchmark mix differs from configured accumulation")
    per_update = LENGTH * ACCUM
    identity = dict(seed=81, dtype="fp32", parameters=124439808, length=LENGTH,
                    microbatch=1, accumulation=ACCUM, targets_per_update=per_update,
                    corpus=checkpoint.checksum(corpus / "manifest.json"), torch=str(torch.__version__),
                    source_sha={name: checkpoint.checksum(Path(__file__).with_name(name)) for name in
                                ["benchmark.py", "gpt2.py", "guards.py", "checkpoint.py", "train.py", "pilot.py"]},
                    elapsed_cap=ELAPSED_CAP, measured_seconds=MEASURED_SECONDS,
                    validation_every=30, save_restore_at_measured_step=10, warmup_updates=WARMUP,
                    data_policy="cycle finite training shards only for throughput measurement")
    (path / "config.json").write_text(json.dumps(identity, indent=2))
    torch.manual_seed(identity["seed"])
    manifest = json.loads((corpus / "manifest.json").read_text())
    data = {}
    for key in ("wiki-train", "stories-train", "wiki-validation"):
        file = corpus / (key + ".u16")
        if checkpoint.checksum(file) != manifest["shards"][key]["sha256"]:
            raise ValueError("benchmark source mismatch")
        data[key] = np.memmap(file, mode="r", dtype="<u2")
        if len(data[key]) < LENGTH + 1:
            raise ValueError(f"short benchmark shard {key}")
    guard.check(force=True)
    model = GPT2().to("mps")
    if sum(p.numel() for p in model.parameters()) != identity["parameters"]:
        raise ValueError("wrong model for benchmark")
    opt = optimizer_for(model)
    pos = dict(wiki=0, stories=0)
    wraps = dict(wiki=0, stories=0)
    step = 0
    started = None
    recent = deque()
    training_seconds = 0.0
    restored = False
    while started is None or time.monotonic() - started < MEASURED_SECONDS:
        guard.check()
        torch.mps.synchronize()
        begin = time.monotonic()
        opt.zero_grad(set_to_none=True)
        for name in SOURCES:
            guard.check()
            stream = data[name + "-train"]
            if pos[name] + LENGTH + 1 > len(stream):
                wraps[name] += 1
                pos[name] = 0
            offset = pos[name]
            row = torch.tensor(stream[offset:offset+LENGTH+1].astype("int64")[None], device="mps")
            loss = backward_rows(model, row[:, :-1], row[:, 1:], per_update)
            if not math.isfinite(loss.item()):
                raise ResourceStop("nonfinite training loss")
            pos[name] += LENGTH
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
        opt.step()
        torch.mps.synchronize()
        step += 1
        train_time = time.monotonic() - begin
        status.update(step=step, target_tokens=step * per_update, input_tokens=step * per_update)
        if step <= WARMUP:
            write_status(path, status)
            if step == WARMUP:
                started = time.monotonic()
            continue
        training_seconds += train_time
        if step % 30 == 0:
            with torch.no_grad():
                row = torch.tensor(data["wiki-validation"][:LENGTH+1].astype("int64")[None], device="mps")
                status["validation_loss"] = next_token_loss(model, row).item()
                if not math.isfinite(status["validation_loss"]):
                    raise ResourceStop("nonfinite validation loss")
        if step == WARMUP + 10:
            guard.check(force=True)
            checkpoint.save(path, dict(step=step, identity=identity, offsets=dict(pos), wraps=dict(wraps),
                                       model=model.state_dict(), optimizer=opt.state_dict(),
                                       rng=torch.get_rng_state(), mps_rng=torch.mps.get_rng_state(),
                                       target_tokens=step * per_update, input_tokens=step * per_update,
                                       elapsed=time.monotonic() - guard.start))
            del model, opt
            torch.mps.empty_cache()
            guard.check(force=True)
            saved = checkpoint.load(path, identity)
            model = GPT2().to("mps")
            model.load_state_dict(saved["model"])
            opt = optimizer_for(model)
            opt.load_state_dict(saved["optimizer"])
            torch.set_rng_state(saved["rng"])
            torch.mps.set_rng_state(saved["mps_rng"])
            if (saved["step"] != step or saved["offsets"] != pos or saved["wraps"] != wraps
                    or saved["target_tokens"] != step * per_update):
                raise ValueError("restored cursor or counters mismatch")
            pos, wraps = saved["offsets"], saved["wraps"]
            restored = True
            del saved
        now = time.monotonic()
        seconds = now - started
        measured = (step - WARMUP) * per_update
        recent.append(now)
        while recent and recent[0] <= now - 600:
            recent.popleft()
        status.update(measured_seconds=seconds, measured_target_tokens=measured,
                      measured_training_seconds=training_seconds, restored=restored,
                      training_tokens_per_second=measured / training_seconds,
                      end_to_end_tokens_per_second=measured / seconds,
                      last_ten_minutes_tokens_per_second=len(recent) * per_update / min(600, seconds),
                      last_window_seconds=min(600, seconds), source_wraps=dict(wraps),
                      remaining_measured_seconds=max(0, MEASURED_SECONDS - seconds),
                      remaining_elapsed_seconds=max(0, guard.limit - (time.time() - guard.wall_start)))
        with (path / "windows.jsonl").open("a") as log:
            log.write(json.dumps(dict(step=step, measured_elapsed=seconds, train_seconds=train_time,
                                      total_measured_targets=measured)) + "\n")
        write_status(path, status)
    guard.check(force=True)
    if not restored or "validation_loss" not in status or status["measured_seconds"] < MEASURED_SECONDS:
        raise ResourceStop("incomplete measurement, validation or checkpoint roundtrip")


def benchmark(path, corpus):
    guard = Guard(path, ELAPSED_CAP)
    status = dict(stage="benchmark", state="running", step=0, target_tokens=0,
                  measured_target_tokens=0, measured_seconds=0, warmup_updates=WARMUP)
    try:
        write_status(path, status)
        measure(guard, corpus, status)
        status["state"] = "passed"
    except ResourceStop as error:
        status.update(state="stopped", reason=str(error))
    except BaseException as error:
        status.update(state="failed", reason=f"{type(error).__name__}: {error}")
        raise
    finally:
        try:
            status["elapsed_seconds"] = time.time() - guard.wall_start
            write_status(path, status)
        finally:
            guard.close()
    return status["state"] == "passed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("corpus", type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if benchmark(args.path, args.corpus) else 1)
