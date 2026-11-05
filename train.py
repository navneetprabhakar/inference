"""Bounded diagnostic training with summed-token normalization and resource guards."""
import argparse
import json
import math
from pathlib import Path

import torch
from torch.nn import functional as F

from gpt2 import Config, GPT2
from guards import Guard, ResourceStop
from tokenizer import load


def backward_rows(model, inputs, labels, supervised_tokens):
    if supervised_tokens <= 0:
        raise ValueError("training update requires supervised targets")
    logits = model(inputs)
    loss = F.cross_entropy(logits.flatten(0, 1), labels.flatten(),
                           ignore_index=-100, reduction="sum") / supervised_tokens
    loss.backward()
    return loss.detach()


def check_accumulation():
    config = Config(vocabulary=19, width=12, depth=1, heads=3)
    models = [GPT2(config), GPT2(config)]
    models[1].load_state_dict(models[0].state_dict())
    x = torch.tensor([[1, 2, 3], [4, 5, 0]])
    labels = torch.tensor([[2, 3, 4], [5, -100, -100]])
    backward_rows(models[0], x, labels, 4)
    for inputs, targets in zip(x, labels):
        backward_rows(models[1], inputs[None], targets[None], 4)
    for a, b in zip(models[0].parameters(), models[1].parameters()):
        torch.testing.assert_close(a.grad, b.grad, atol=1e-6, rtol=1e-5)
    for model in models:
        torch.optim.AdamW(model.parameters(), lr=3e-4, eps=1e-6).step()
    for a, b in zip(models[0].parameters(), models[1].parameters()):
        torch.testing.assert_close(a, b, atol=1e-6, rtol=1e-5)


def optimizer_for(model):
    matrices = [p for p in model.parameters() if p.ndim >= 2]
    other = [p for p in model.parameters() if p.ndim < 2]
    return torch.optim.AdamW([{"params": matrices, "weight_decay": 0.1},
                              {"params": other, "weight_decay": 0.0}],
                             lr=3e-4, betas=(0.9, 0.95), foreach=False)


def memorize(path):
    guard = Guard(path, 15 * 60)
    check_accumulation()
    torch.manual_seed(57)
    tokenizer = load()
    ids = tokenizer.encode("A quiet fox crossed the bridge before sunrise.").ids
    row = torch.tensor([ids], device="mps")
    assert len(set(ids[:-1])) == len(ids)-1
    model = GPT2().to("mps")
    opt = optimizer_for(model)
    before = model.tokens.weight[ids[0]].detach().clone()
    result = dict(stage="memorization", seed=57, device="mps", dtype="fp32",
                  input=[tokenizer.decode([i]) for i in ids[:-1]],
                  targets=[tokenizer.decode([i]) for i in ids[1:]], state="running")
    try:
        for step in range(1,201):
            guard.check()
            opt.zero_grad(set_to_none=True)
            loss = backward_rows(model, row[:, :-1], row[:, 1:], len(ids)-1)
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
            opt.step()
            with torch.no_grad():
                logits = model(row[:, :-1])
                acc = (logits.argmax(-1) == row[:, 1:]).float().mean().item()
                ce = F.cross_entropy(logits[0], row[0, 1:]).item()
            if not math.isfinite(ce):
                raise ResourceStop("nonfinite loss")
            result.update(step=step, post_update_ce=ce, accuracy=acc,
                          gradient_norm=norm.item(), train_ce=loss.item(),
                          parameter_delta=(model.tokens.weight[ids[0]]-before).abs().max().item())
            with (path/"metrics.jsonl").open("a") as log:
                log.write(json.dumps(result)+"\n")
            if ce < 0.1 and acc >= .95:
                result.update(state="passed")
                break
        else:
            result.update(state="failed", reason="memorization target missed within 200 steps")
        guard.check(force=True)
    except ResourceStop as error:
        result.update(state="stopped", reason=str(error))
    finally:
        (path/"status.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    return result["state"] == "passed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if memorize(args.run) else 1)
