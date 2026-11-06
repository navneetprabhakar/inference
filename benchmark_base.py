"""Discarded random-weight foundation throughput benchmark; never a deployable model."""
import argparse
from contextlib import nullcontext
import gc
import json
import math
from pathlib import Path
import time

import numpy as np
import torch
from torch.nn import functional as F

import checkpoint
from gpt2 import GPT2
from guards import Guard, ResourceStop
from train import optimizer_for

LAYOUTS = [("fp32-b2-t256", 2, 256, False),
           ("bf16-b2-t256", 2, 256, True),
           ("bf16-b2-t512", 2, 512, True),
           ("bf16-b4-t512", 4, 512, True)]
TOKENS = 8192
CAP = 1200
SEED = 4817


def write(path, name, value):
    tmp = path / (name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    tmp.replace(path / name)


def amp(enabled):
    return torch.autocast("mps", dtype=torch.bfloat16) if enabled else nullcontext()


def run(path, corpus, *, layouts=LAYOUTS, cap=CAP, prior_run=None):
    torch.set_num_threads(1)
    guard = Guard(path, cap)
    result = dict(state="running", candidates=[], discarded=True)
    try:
        identity = dict(seed=SEED, parameters=124439808, layouts=layouts,
                        effective_targets_per_update=TOKENS, warmup_updates=2,
                        timed_updates=10, cap_seconds=cap, prior_run=prior_run,
                        comparison=dict(loss_absolute_max=.03, logits_rms_max=.05,
                                        gradient_relative_l2_max=.10),
                        optimizer="AdamW FP32 master and moments; lr=3e-4; betas=.9,.95; weight_decay=.1 matrices only",
                        corpus=str(corpus), manifest_sha256=checkpoint.checksum(corpus / "manifest.json"),
                        code={f: checkpoint.checksum(Path(__file__).with_name(f)) for f in
                              ("benchmark_base.py", "gpt2.py", "train.py", "guards.py", "checkpoint.py")},
                        torch=str(torch.__version__),
                        policy="Training shard only; repeated text permitted for throughput only. Random tensors and all updates discarded. No quality claim.")
        write(path, "config.json", identity)
        manifest = json.loads((corpus / "manifest.json").read_text())
        shard = corpus / "wiki-train.u16"
        if checkpoint.checksum(shard) != manifest["shards"]["wiki-train"]["sha256"]:
            raise ValueError("source checksum mismatch")
        data = np.memmap(shard, mode="r", dtype="<u2")

        def rows(pos, batch, length):
            starts = [(pos + i * length) % (len(data) - length - 1) for i in range(batch)]
            array = np.stack([data[i:i + length + 1] for i in starts]).astype("int64")
            return torch.from_numpy(array).to("mps")

        def new_model():
            torch.manual_seed(SEED)
            model = GPT2().to("mps")
            assert sum(p.numel() for p in model.parameters()) == 124439808
            return model

        # Same random tensors and same real text for both numerical paths.
        model = new_model()
        row = rows(0, 2, 256)
        reference = {}
        with amp(False):
            logits = model(row[:, :-1])
            loss = F.cross_entropy(logits.flatten(0, 1), row[:, 1:].flatten())
        loss.backward()
        reference["loss"] = loss.item()
        ref_logits = logits.detach().cpu()
        ref_grads = [p.grad.detach().cpu().clone() for p in model.parameters()]
        del logits, loss
        model.zero_grad(set_to_none=True)
        bf16_ok = False
        try:
            guard.check(force=True)
            with amp(True):
                logits = model(row[:, :-1])
                if logits.dtype != torch.bfloat16:
                    raise ValueError(f"autocast did not produce BF16 logits: {logits.dtype}")
                loss = F.cross_entropy(logits.flatten(0, 1), row[:, 1:].flatten())
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), float("inf"), error_if_nonfinite=True)
            error2 = sum((p.grad.detach().cpu() - r).square().sum().item()
                         for p, r in zip(model.parameters(), ref_grads))
            reference2 = sum(r.square().sum().item() for r in ref_grads)
            reference.update(bf16_loss=loss.item(), loss_absolute_error=abs(loss.item()-reference["loss"]),
                             logits_rms_error=(logits.detach().float().cpu()-ref_logits).square().mean().sqrt().item(),
                             gradient_relative_l2=(error2/reference2)**.5, gradient_norm=norm.item(),
                             actual_logits_dtype=str(logits.dtype))
            bf16_ok = (reference["loss_absolute_error"] <= .03 and reference["logits_rms_error"] <= .05
                       and reference["gradient_relative_l2"] <= .10)
            reference["passed"] = bf16_ok
            del logits, loss
        except (RuntimeError, ValueError) as error:
            reference.update(passed=False, error=str(error))
        result["comparison"] = reference
        del model, row, ref_logits, ref_grads
        gc.collect()
        torch.mps.empty_cache()
        write(path, "status.json", result)

        def update(model, opt, layout, pos):
            name, batch, length, use_amp = layout
            guard.check()
            torch.mps.synchronize()
            start = time.monotonic()
            opt.zero_grad(set_to_none=True)
            total = torch.zeros((), device="mps")
            for _ in range(TOKENS // (batch*length)):
                guard.check()
                row = rows(pos, batch, length)
                with amp(use_amp):
                    logits = model(row[:, :-1])
                    loss = F.cross_entropy(logits.flatten(0, 1), row[:, 1:].flatten(), reduction="sum") / TOKENS
                loss.backward()
                total += loss.detach()
                pos += batch*length
            grad = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
            opt.step()
            torch.mps.synchronize()
            ce = total.item()
            if not math.isfinite(ce):
                raise ValueError("nonfinite CE")
            if any(p.dtype != torch.float32 for p in model.parameters()):
                raise ValueError("master tensors not FP32")
            return pos, time.monotonic()-start, ce, grad.item()

        for layout in layouts:
            name, _, _, use_amp = layout
            if use_amp and not bf16_ok:
                result["candidates"].append(dict(name=name, state="rejected", reason="numerical comparison failed"))
                continue
            model = new_model()
            opt = optimizer_for(model)
            pos, measured = 0, []
            candidate = dict(name=name, state="running", layout=layout)
            result["candidates"].append(candidate)
            try:
                for step in range(12):
                    pos, seconds, ce, grad = update(model, opt, layout, pos)
                    if step >= 2:
                        measured.append(seconds)
                    candidate.update(updates=step+1, train_ce=ce, grad_norm=grad,
                                     measured_seconds=sum(measured),
                                     tokens_per_second=len(measured)*TOKENS/sum(measured) if measured else None,
                                     mps_allocated=torch.mps.current_allocated_memory(),
                                     mps_driver=torch.mps.driver_allocated_memory())
                    write(path, "status.json", result)
                candidate["state"] = "passed"
                guard.check(force=True)
            except (RuntimeError, ValueError) as error:
                candidate.update(state="rejected", reason=str(error))
            del model, opt
            gc.collect()
            torch.mps.empty_cache()
            write(path, "status.json", result)

        passed = [c for c in result["candidates"] if c["state"] == "passed"]
        if not passed:
            raise ValueError("no valid layout")
        winner = max(passed, key=lambda c: c["tokens_per_second"])
        result["selected"] = winner["name"]
        model = new_model()
        opt = optimizer_for(model)
        layout = winner["layout"]
        pos = 0
        for _ in range(2):
            pos, _, _, _ = update(model, opt, layout, pos)
        # Actual checkpoint roundtrip before sustained run, verify fixed text logits.
        row = rows(0, layout[1], layout[2])
        with torch.no_grad(), amp(layout[3]):
            before = model(row[:, :-1]).detach().cpu()
        checkpoint.save(path, dict(identity=identity, step=2, model=model.state_dict(),
                                   optimizer=opt.state_dict(), pos=pos, rng=torch.get_rng_state(),
                                   mps_rng=torch.mps.get_rng_state()))
        del model, opt
        gc.collect()
        torch.mps.empty_cache()
        saved = checkpoint.load(path, identity)
        model = new_model()
        model.load_state_dict(saved["model"])
        opt = optimizer_for(model)
        opt.load_state_dict(saved["optimizer"])
        torch.set_rng_state(saved["rng"])
        torch.mps.set_rng_state(saved["mps_rng"])
        pos = saved["pos"]
        del saved
        with torch.no_grad(), amp(layout[3]):
            after = model(row[:, :-1]).detach().cpu()
        torch.testing.assert_close(before, after, atol=0, rtol=0)
        result["checkpoint_roundtrip"] = "exact logits; model, optimizer, cursor, CPU/MPS RNG restored"
        del row, before, after
        started = time.monotonic()
        measured = []
        while time.monotonic()-guard.start < cap-45:
            pos, seconds, ce, grad = update(model, opt, layout, pos)
            measured.append(seconds)
            result["sustained"] = dict(updates=len(measured), train_ce=ce, gradient_norm=grad,
                                      training_seconds=sum(measured), elapsed_seconds=time.monotonic()-started,
                                      training_tokens_per_second=len(measured)*TOKENS/sum(measured),
                                      end_to_end_tokens_per_second=len(measured)*TOKENS/(time.monotonic()-started),
                                      mps_allocated=torch.mps.current_allocated_memory(),
                                      mps_driver=torch.mps.driver_allocated_memory())
            write(path, "status.json", result)
        guard.check(force=True)
        result["state"] = "passed"
    except ResourceStop as error:
        result.update(state="stopped", reason=str(error))
    except BaseException as error:
        result.update(state="failed", reason=f"{type(error).__name__}: {error}")
        raise
    finally:
        result["elapsed_seconds"] = time.monotonic()-guard.start
        write(path, "status.json", result)
        guard.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--corpus", type=Path, default=Path("data/extended-trial-v3"))
    parser.add_argument("--only", choices=[row[0] for row in LAYOUTS])
    parser.add_argument("--combined-with", type=Path)
    args = parser.parse_args()
    cap = CAP
    prior = None
    if args.combined_with:
        prior_status = json.loads((args.combined_with / "status.json").read_text())
        if prior_status["state"] == "running":
            raise ValueError("prior benchmark must stop before continuation")
        original_start = json.loads((args.combined_with / "guard.json").read_text())["started"]
        cap = int(CAP - (time.time()-original_start))
        if cap < 120:
            raise ValueError("insufficient original wall budget remaining")
        prior = dict(path=str(args.combined_with), status_sha256=checkpoint.checksum(args.combined_with / "status.json"),
                     reason="Owner selected best512 context layout rather than fastest256; combined original1200s cap")
    layouts = [row for row in LAYOUTS if args.only is None or row[0] == args.only]
    print(json.dumps(run(args.path, args.corpus, layouts=layouts, cap=cap, prior_run=prior), indent=2))
