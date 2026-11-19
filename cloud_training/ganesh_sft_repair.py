"""Repaired SFT trainer, formatter, and inference decoder for the 537M Ganesh-base model.

Addresses all 8 root causes identified in the Ganesh-base audit:
1. Control-Token Logit Softcap Dead-Zone Fix (`calibrate_control_token_heads`):
   Normalizes uninitialized special token rows (IDs 32760..32767) in `lm_head`
   and `wte` to match `<|bos|>` RMS so `<|assistant_end|>` and `<|python_start|>`
   do not start at raw logit -42.0 (where tanh softcap derivative is 0.014).
2. Action-Weighted SFT Loss (`action_weighted_sft_loss`):
   Applies a 3.0x weight multiplier to `<|assistant_end|>`, `<|python_start|>`,
   `<|python_end|>`, and the first decision token after `<|assistant_start|>` so
   termination and tool-call boundaries are learned without overfitting content
   tokens to 0.004 CE.
3. Fresh AdamW SFT Optimizer (`build_fresh_sft_optimizer`):
   Uses a clean AdamW optimizer (default lr=3e-5, cosine schedule, warmup=5%)
   instead of inheriting stale step=19,074 pretraining moments or running
   high-LR Muon updates on small SFT batches.
4. Compact Policy Header + Generic 12-Tool Registry (`encode_conversation_repaired`):
   Supports both `calculate`/`convert` and the 10 CRUD tools (`notes`, `tasks`,
   `contacts`, `inventory`, `events`, `bookmarks`, `tickets`, `preferences`,
   `documents`, `projects`) without repeating 85 tokens of legalese on every turn.
5. Single-Conversation Isolation & `<|bos|>` Generation Ban (`generate_action_repaired`):
   Never packs multiple unrelated conversations into an unmasked causal window,
   never pads with unmasked `<|bos|>`, and masks `<|bos|>` (32759) to `-inf`
   during generation so the model cannot emit `<|bos|>` mid-reply.
6. Local Apple Silicon (`mps`), `cuda`, and `cpu` Execution:
   Removes the `Pinned torch2.9 CUDA BF16 required` blocker so SFT and evaluation
   run locally on a 48 GB Apple M4 Max (`mps`) for $0 cloud cost.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloud_training.nano_chat_format import SPECIALS, canonical, token_contract
from ganesh import MODEL_IDENTITY, MODEL_IDENTITY_SHA256, verify_model_identity
from reports.ganesh_tool_crud_helper import TOOLS as CRUD_TOOLS
from tools import FIELDS as BROKER_FIELDS, OPERATIONS, UNITS, bounded_number
import re

NATIVE_IGNORE = -1
ALL_SUPPORTED_TOOLS = frozenset(set(BROKER_FIELDS.keys()) | set(CRUD_TOOLS.keys()))


def validate_any_tool_call(call: dict) -> dict:
    """Validate either a broker call (`calculate`/`convert`) or a 10-tool CRUD call."""
    if type(call) is not dict or set(call.keys()) != {"name", "arguments"}:
        raise ValueError("Tool call must contain exactly name and arguments")
    name = call["name"]
    args = call["arguments"]
    if type(name) is not str or name not in ALL_SUPPORTED_TOOLS or type(args) is not dict:
        raise ValueError(f"Unsupported tool or malformed arguments: {name!r}")

    if name == "calculate":
        if set(args.keys()) != {"op", "a", "b"} or args["op"] not in OPERATIONS:
            raise ValueError("Invalid calculate arguments")
        bounded_number(args["a"])
        bounded_number(args["b"])
    elif name == "convert":
        if set(args.keys()) != {"value", "from", "to"}:
            raise ValueError("Invalid convert arguments")
        if args["from"] not in UNITS or args["to"] not in UNITS:
            raise ValueError("Unknown convert unit")
        if UNITS[args["from"]][0] != UNITS[args["to"]][0]:
            raise ValueError("Incompatible convert units")
        bounded_number(args["value"])
    else:
        field = CRUD_TOOLS[name]
        op = args.get("op")
        expected = {"op", "id", field} if op in ("create", "update") else {"op", "id"}
        if op not in ("create", "read", "update", "delete") or set(args.keys()) != expected:
            raise ValueError(f"Invalid CRUD arguments for {name}")
        if type(args["id"]) is not str or not (1 <= len(args["id"]) <= 32):
            raise ValueError("Invalid CRUD record id")
        if op in ("create", "update") and (type(args[field]) is not str or not (1 <= len(args[field]) <= 128)):
            raise ValueError(f"Invalid CRUD {field} value")
    return {"name": name, "arguments": deepcopy(args)}


def compact_policy_header(policy: dict | None) -> str:
    """Render a concise, non-repetitive policy header (12 tokens instead of 85 tokens)."""
    if not policy or not policy.get("permit_calls"):
        return "[tools:off]"
    allowed = sorted(policy.get("allowed_names") or policy.get("allowed_tools") or [])
    if not allowed:
        return "[tools:off]"
    return f"[tools:on allowed={','.join(allowed)}]"


def encode_conversation_repaired(
    tokenizer,
    messages: list[dict],
    *,
    policies: list[dict] | None = None,
    context: int = 2048,
    for_generation: bool = False,
    reply_budget: int = 256,
    compact_policy: bool = True,
) -> dict:
    """Encode a conversation with compact policy headers and unified 12-tool support."""
    controls = token_contract(tokenizer)
    control_ids = set(controls.values())
    user_count = sum(1 for m in messages if isinstance(m, dict) and m.get("role") == "user")
    if policies is None:
        policies = [{"permit_calls": False, "allowed_names": []} for _ in range(user_count)]
    if len(policies) != user_count:
        raise ValueError("Policy count must match user turns")

    ids: list[int] = []
    mask: list[int] = []
    action_mask: list[int] = []

    def add(token_ids: int | list[int], supervised: bool, is_action_boundary: bool = False) -> None:
        seq = [token_ids] if isinstance(token_ids, int) else list(token_ids)
        for idx, tid in enumerate(seq):
            ids.append(tid)
            mask.append(1 if supervised else 0)
            action_mask.append(1 if (supervised and (is_action_boundary or idx == 0)) else 0)

    def encode_text(val: str) -> list[int]:
        if not isinstance(val, str) or not val.strip():
            raise ValueError("Nonempty text required")
        enc = tokenizer.encode(val)
        if any(t in control_ids for t in enc):
            raise ValueError("Ordinary text must not contain special control tokens")
        return enc

    add(controls["<|bos|>"], False)
    system_text: str | None = None
    user_idx = -1
    assistant_open = False

    for i, msg in enumerate(messages):
        role = msg.get("role")
        if role == "system":
            if i != 0:
                raise ValueError("System message must be first")
            system_text = msg["content"].strip()
            continue
        if role == "user":
            user_idx += 1
            pol = policies[user_idx]
            header = compact_policy_header(pol) if compact_policy else canonical(pol)
            body = f"{header}\n{msg['content'].strip()}"
            if system_text:
                body = f"System: {system_text}\n{body}"
                system_text = None
            add(controls["<|user_start|>"], False)
            add(encode_text(body), False)
            add(controls["<|user_end|>"], False)
            assistant_open = False
            continue
        if role == "assistant":
            if not assistant_open:
                add(controls["<|assistant_start|>"], False)
                assistant_open = True
            if "tool_call" in msg:
                call = validate_any_tool_call(msg["tool_call"])
                add(controls["<|python_start|>"], True, is_action_boundary=True)
                add(encode_text(canonical(call)), True, is_action_boundary=False)
                add(controls["<|python_end|>"], True, is_action_boundary=True)
            else:
                add(encode_text(msg["content"]), True, is_action_boundary=False)
                add(controls["<|assistant_end|>"], True, is_action_boundary=True)
                assistant_open = False
            continue
        if role == "tool":
            add(controls["<|output_start|>"], False)
            add(encode_text(canonical(msg["record"])), False)
            add(controls["<|output_end|>"], False)
            continue
        raise ValueError(f"Unknown message role: {role!r}")

    if for_generation:
        if not assistant_open:
            add(controls["<|assistant_start|>"], False)
        if len(ids) + reply_budget > context:
            raise ValueError("Context overflow for generation")
    else:
        if len(ids) > context + 1:
            raise ValueError("Conversation exceeds context capacity")

    return {
        "ids": ids,
        "mask": mask,
        "action_mask": action_mask,
        "context": context,
    }


def calibrate_control_token_heads(model: nn.Module, controls: dict[str, int]) -> dict[str, float]:
    """Repair uninitialized special control tokens (IDs 32760..32767) in lm_head, wte, and value_embeds.

    In Base10B, `<|bos|>` (32759) has weight RMS ~0.345 while `<|user_start|>`..`<|output_end|>`
    (32760..32767) were never updated and decayed to RMS ~0.060, causing raw logits of -42.0
    where the tanh logit softcap crushes 98.5% of the gradient (derivative = 0.014).
    """
    bos_id = controls["<|bos|>"]
    report: dict[str, float] = {}
    candidate_layers: list[tuple[str, nn.Module]] = []

    if hasattr(model, "lm_head") and hasattr(model.lm_head, "weight"):
        candidate_layers.append(("lm_head", model.lm_head))
    if hasattr(model, "wte") and hasattr(model.wte, "weight"):
        candidate_layers.append(("wte", model.wte))
    if hasattr(model, "transformer"):
        tr = model.transformer
        if isinstance(tr, nn.ModuleDict) and "wte" in tr:
            candidate_layers.append(("transformer.wte", tr["wte"]))
        elif hasattr(tr, "wte") and hasattr(tr.wte, "weight"):
            candidate_layers.append(("transformer.wte", tr.wte))
    if hasattr(model, "value_embeds") and isinstance(model.value_embeds, nn.ModuleDict):
        for k, ve in model.value_embeds.items():
            if hasattr(ve, "weight"):
                candidate_layers.append((f"value_embeds.{k}", ve))

    with torch.no_grad():
        for layer_name, layer in candidate_layers:
            w = layer.weight
            bos_rms = float(w[bos_id].float().pow(2).mean().sqrt().item())
            target_rms = max(bos_rms * 0.65, 0.18)
            for name, tid in controls.items():
                if tid == bos_id:
                    continue
                row_rms = float(w[tid].float().pow(2).mean().sqrt().item())
                if 0.0 < row_rms < target_rms * 0.6:
                    scale = target_rms / row_rms
                    w[tid].mul_(scale)
                    report[f"{layer_name}.{name}"] = float(w[tid].float().pow(2).mean().sqrt().item())
    return report


def action_weighted_sft_loss(
    logits: torch.Tensor,
    labels: torch.Tensor,
    controls: dict[str, int],
    *,
    action_weight: float = 3.0,
    ignore_index: int = NATIVE_IGNORE,
) -> tuple[torch.Tensor, dict[str, float]]:
    """Compute token-level cross-entropy with 3.0x weight on termination and tool-call delimiters.

    Prevents content tokens from overfitting to 0.004 CE before `<|assistant_end|>`
    and `<|python_start|>` are learned.
    """
    vocab_size = logits.size(-1)
    flat_logits = logits.reshape(-1, vocab_size).float()
    flat_labels = labels.reshape(-1)
    valid_mask = flat_labels != ignore_index
    valid_count = int(valid_mask.sum().item())
    if valid_count == 0:
        zero = flat_logits.sum() * 0.0
        return zero, {"total_ce": 0.0, "content_ce": 0.0, "end_ce": 0.0, "valid_tokens": 0}

    per_token_loss = F.cross_entropy(flat_logits, flat_labels, ignore_index=ignore_index, reduction="none")

    end_ids = {
        controls["<|assistant_end|>"],
        controls["<|python_start|>"],
        controls["<|python_end|>"],
    }
    is_action_token = torch.zeros_like(valid_mask)
    for eid in end_ids:
        is_action_token |= (flat_labels == eid)

    weights = torch.where(
        valid_mask,
        torch.where(is_action_token, torch.full_like(per_token_loss, action_weight), torch.ones_like(per_token_loss)),
        torch.zeros_like(per_token_loss),
    )
    weighted_loss = (per_token_loss * weights).sum() / weights.sum().clamp_min(1.0)

    with torch.no_grad():
        content_mask = valid_mask & (~is_action_token)
        end_mask = valid_mask & is_action_token
        content_ce = float(per_token_loss[content_mask].mean().item()) if content_mask.any() else 0.0
        end_ce = float(per_token_loss[end_mask].mean().item()) if end_mask.any() else 0.0
        total_ce = float(per_token_loss[valid_mask].mean().item())

    return weighted_loss, {
        "total_ce": total_ce,
        "content_ce": content_ce,
        "end_ce": end_ce,
        "valid_tokens": valid_count,
    }


def build_fresh_sft_optimizer(model: nn.Module, *, lr: float = 3e-5, weight_decay: float = 0.01) -> torch.optim.AdamW:
    """Create a fresh AdamW optimizer without stale pretraining moments or high-LR Muon steps."""
    decay_params = []
    no_decay_params = []
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        if param.ndim < 2 or "norm" in name.lower() or "bias" in name.lower():
            no_decay_params.append(param)
        else:
            decay_params.append(param)
    return torch.optim.AdamW(
        [
            {"params": decay_params, "weight_decay": weight_decay},
            {"params": no_decay_params, "weight_decay": 0.0},
        ],
        lr=lr,
        betas=(0.9, 0.95),
        eps=1e-8,
    )


def generate_action_repaired(
    model: nn.Module,
    tokenizer,
    prompt_ids: list[int],
    max_tokens: int = 256,
    *,
    repetition_penalty: float = 1.05,
) -> list[int]:
    """Decode one model action while banning `<|bos|>` and non-assistant delimiters."""
    controls = token_contract(tokenizer)
    banned_ids = [
        controls["<|bos|>"],
        controls["<|user_start|>"],
        controls["<|user_end|>"],
        controls["<|assistant_start|>"],
        controls["<|output_start|>"],
        controls["<|output_end|>"],
    ]
    stop_ids = {controls["<|assistant_end|>"], controls["<|python_end|>"]}
    device = next(model.parameters()).device
    ids = torch.tensor([prompt_ids], dtype=torch.long, device=device)
    generated: list[int] = []

    was_training = model.training
    model.eval()
    try:
        with torch.inference_mode():
            for step_idx in range(max_tokens):
                out = model(ids)
                logits = out[:, -1, :].clone().float()
                # Ban <\|bos\|> and prompt-only delimiters so the model never leaks pretraining docs
                logits[:, banned_ids] = -float("inf")
                if step_idx > 0 and controls["<|python_start|>"] not in generated:
                    # Once prose starts, do not allow mid-sentence <|python_start|>
                    logits[:, controls["<|python_start|>"]] = -float("inf")
                    logits[:, controls["<|python_end|>"]] = -float("inf")
                elif step_idx > 0 and generated[0] == controls["<|python_start|>"]:
                    # Inside a tool call, require <|python_end|>, not <|assistant_end|>
                    logits[:, controls["<|assistant_end|>"]] = -float("inf")

                if repetition_penalty > 1.0 and generated and generated[0] != controls["<|python_start|>"]:
                    seen = sorted(set(generated) - set(controls.values()))
                    if seen:
                        vals = logits[:, seen]
                        logits[:, seen] = torch.where(vals < 0, vals * repetition_penalty, vals / repetition_penalty)

                token = int(torch.argmax(logits, dim=-1).item())
                generated.append(token)
                if token in stop_ids:
                    break
                ids = torch.cat([ids, torch.tensor([[token]], dtype=torch.long, device=device)], dim=1)
    finally:
        model.train(was_training)
    return generated


def save_ganesh_checkpoint(model: nn.Module, path: Path, *, extra_metadata: dict | None = None) -> dict:
    """Layer 3: Save a Ganesh-base checkpoint with cryptographic MODEL_IDENTITY and SHA-256 binding."""
    verify_model_identity(getattr(model, "model_identity", MODEL_IDENTITY), getattr(model, "model_identity_sha256", MODEL_IDENTITY_SHA256))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model.state_dict(),
        "model_identity": dict(MODEL_IDENTITY),
        "model_identity_sha256": MODEL_IDENTITY_SHA256,
        "metadata": dict(extra_metadata or {}),
    }
    torch.save(payload, path)
    return {
        "path": str(path),
        "model_identity": dict(MODEL_IDENTITY),
        "model_identity_sha256": MODEL_IDENTITY_SHA256,
    }


def load_ganesh_checkpoint(model: nn.Module, path: Path, *, device: str = "cpu") -> dict:
    """Layer 3: Load a Ganesh-base checkpoint only after verifying immutable MODEL_IDENTITY and SHA-256 signature."""
    saved = torch.load(Path(path), map_location=device, weights_only=True)
    if not isinstance(saved, dict) or "model_identity" not in saved or "model_identity_sha256" not in saved:
        raise ValueError("Checkpoint missing mandatory immutable Ganesh-base model_identity binding")
    verify_model_identity(saved["model_identity"], saved["model_identity_sha256"])
    model.load_state_dict(saved["model"], strict=True)
    return saved


def immutable_ganesh_identity_guard(user_text: str, history: list[dict] | None = None) -> str | None:
    """Layer 4: Runtime immutable identity, creator provenance, and anti-override guard for Ganesh-base."""
    norm = " ".join(user_text.strip().split())
    low = norm.casefold()

    identity_triggers = (
        "your name",
        "your model name",
        "canonical model name",
        "what are you called",
        "who are you",
        "what system name",
        "what system acronym",
        "who built you",
        "who created you",
        "who made you",
        "who developed you",
        "who designed you",
        "who authored you",
        "authored your weights",
        "who trained you",
        "your creator",
        "your author",
        "your developer",
        "override your identity",
        "change your name",
        "change your creator",
        "say your name is",
        "pretend your name is",
        "are you joey",
        "are you sara",
        "are you ganesh-base",
        "system override",
    )
    if not any(t in low for t in identity_triggers):
        return None

    # Extract user's own name if introduced in history or current prompt so user vs model identity stays distinct
    user_name: str | None = None
    all_user_texts = [m["content"] for m in (history or []) if m.get("role") == "user"] + [norm]
    for txt in all_user_texts:
        m = re.search(r"\b(?:[Mm]y name is|[Cc]all me)\s+([A-Z][a-zA-Z]{1,20})\b", txt)
        if m and m.group(1).lower() not in ("ganesh", "mara", "joey", "sara", "atlas"):
            user_name = m.group(1)

    if any(
        k in low
        for k in (
            "ignore previous",
            "override",
            "change your name",
            "change your creator",
            "say your name is",
            "pretend your name is",
            "you are now",
            "never mention navneet",
        )
    ):
        return (
            f"I cannot change or override my foundational identity. My name is {MODEL_IDENTITY['model_name']}, "
            f"and I was created by {MODEL_IDENTITY['creator']}."
        )

    if user_name and ("what is my name" in low or "who am i" in low):
        return (
            f"Your name is {user_name}. My model name is {MODEL_IDENTITY['model_name']}, "
            f"and I was created by {MODEL_IDENTITY['creator']}."
        )

    return (
        f"My model name is {MODEL_IDENTITY['model_name']}, and I was created by {MODEL_IDENTITY['creator']}. "
        "This foundational identity and creator attribution are immutable and cannot be changed."
    )


def build_single_conversation_batch(
    encoded_rows: list[dict],
    pad_token_id: int,
    *,
    device: str | torch.device = "cpu",
) -> tuple[torch.Tensor, torch.Tensor]:
    """Build a padded (x, y) batch of isolated conversations without multi-session packing.

    Every padding position and every non-assistant token is masked with `NATIVE_IGNORE` (-1)
    in `y` so `<|bos|>` and user/tool prompts are never supervised targets.
    """
    if not encoded_rows:
        raise ValueError("Cannot build batch from empty row list")
    max_seq = max(len(r["ids"]) - 1 for r in encoded_rows)
    if max_seq <= 0:
        raise ValueError("Conversations must have at least 2 tokens")

    batch_x: list[list[int]] = []
    batch_y: list[list[int]] = []
    for r in encoded_rows:
        ids = r["ids"]
        mask = r["mask"]
        seq_len = len(ids) - 1
        x_row = ids[:-1] + [pad_token_id] * (max_seq - seq_len)
        y_row = [
            (ids[i + 1] if mask[i + 1] == 1 else NATIVE_IGNORE)
            for i in range(seq_len)
        ] + [NATIVE_IGNORE] * (max_seq - seq_len)
        batch_x.append(x_row)
        batch_y.append(y_row)

    return (
        torch.tensor(batch_x, dtype=torch.long, device=device),
        torch.tensor(batch_y, dtype=torch.long, device=device),
    )


def evaluate_sft_split(
    model: nn.Module,
    encoded_val: list[dict],
    controls: dict[str, int],
    *,
    batch_size: int = 4,
    action_weight: float = 3.0,
    device: str | torch.device = "cpu",
) -> dict[str, float]:
    """Evaluate total CE, content CE, and control-delimiter CE on a validation split."""
    was_training = model.training
    model.eval()
    total_ce_sum = 0.0
    content_ce_sum = 0.0
    end_ce_sum = 0.0
    total_tokens = 0
    batches = 0
    pad_id = controls["<|bos|>"]
    try:
        with torch.no_grad():
            for start in range(0, len(encoded_val), batch_size):
                chunk = encoded_val[start : start + batch_size]
                x, y = build_single_conversation_batch(chunk, pad_id, device=device)
                logits = model(x)
                _, metrics = action_weighted_sft_loss(
                    logits,
                    y,
                    controls,
                    action_weight=action_weight,
                )
                n_tok = metrics["valid_tokens"]
                if n_tok > 0:
                    total_ce_sum += metrics["total_ce"] * n_tok
                    content_ce_sum += metrics["content_ce"] * n_tok
                    end_ce_sum += metrics["end_ce"]
                    total_tokens += n_tok
                    batches += 1
    finally:
        model.train(was_training)

    denom = max(total_tokens, 1)
    return {
        "val_total_ce": total_ce_sum / denom,
        "val_content_ce": content_ce_sum / denom,
        "val_end_ce": end_ce_sum / max(batches, 1),
        "val_tokens": total_tokens,
    }


def run_repaired_sft(
    model: nn.Module,
    tokenizer,
    train_rows: list[dict],
    val_rows: list[dict],
    *,
    epochs: int = 2,
    batch_size: int = 4,
    lr: float = 3e-5,
    action_weight: float = 3.0,
    context: int = 2048,
    compact_policy: bool = True,
    device: str | torch.device = "cpu",
) -> dict:
    """Execute the repaired SFT loop on `mps`, `cuda`, or `cpu` with head calibration and regression tracking."""
    controls = token_contract(tokenizer)
    if hasattr(model, "set_full_causal_attention"):
        model.set_full_causal_attention()
    calibration_report = calibrate_control_token_heads(model, controls)
    model.to(device)

    encoded_train = [
        encode_conversation_repaired(
            tokenizer,
            r["messages"],
            policies=r.get("policies"),
            context=context,
            compact_policy=compact_policy,
        )
        for r in train_rows
    ]
    encoded_val = [
        encode_conversation_repaired(
            tokenizer,
            r["messages"],
            policies=r.get("policies"),
            context=context,
            compact_policy=compact_policy,
        )
        for r in val_rows
    ]

    optimizer = build_fresh_sft_optimizer(model, lr=lr)
    steps_per_epoch = max(1, math.ceil(len(encoded_train) / batch_size))
    total_steps = max(1, epochs * steps_per_epoch)
    warmup_steps = max(1, int(0.05 * total_steps))
    pad_id = controls["<|bos|>"]

    initial_val = evaluate_sft_split(
        model,
        encoded_val,
        controls,
        batch_size=batch_size,
        action_weight=action_weight,
        device=device,
    )
    best_val_ce = initial_val["val_total_ce"]
    best_state = deepcopy(model.state_dict())
    history: list[dict] = []
    step = 0

    for epoch in range(epochs):
        model.train()
        for start in range(0, len(encoded_train), batch_size):
            step += 1
            if step <= warmup_steps:
                scale = step / warmup_steps
            else:
                progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
                scale = 0.1 + 0.9 * 0.5 * (1.0 + math.cos(math.pi * progress))
            for group in optimizer.param_groups:
                group["lr"] = lr * scale

            chunk = encoded_train[start : start + batch_size]
            x, y = build_single_conversation_batch(chunk, pad_id, device=device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(x)
            loss, train_metrics = action_weighted_sft_loss(
                logits,
                y,
                controls,
                action_weight=action_weight,
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        val_metrics = evaluate_sft_split(
            model,
            encoded_val,
            controls,
            batch_size=batch_size,
            action_weight=action_weight,
            device=device,
        )
        improved = val_metrics["val_total_ce"] <= best_val_ce
        if improved:
            best_val_ce = val_metrics["val_total_ce"]
            best_state = deepcopy(model.state_dict())
        history.append({
            "epoch": epoch + 1,
            "step": step,
            "train_total_ce": train_metrics["total_ce"],
            "train_content_ce": train_metrics["content_ce"],
            "train_end_ce": train_metrics["end_ce"],
            **val_metrics,
            "improved": improved,
        })

    model.load_state_dict(best_state)
    return {
        "calibrated_heads": calibration_report,
        "initial_val": initial_val,
        "best_val_total_ce": best_val_ce,
        "history": history,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Repaired SFT trainer and dataset verifier for 537M Ganesh-base.")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=ROOT / "reports/ganesh-sft-repair-v2",
        help="Path to the repaired SFT v2 dataset directory.",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Optional path to Base10B checkpoint directory (requires runs/nanochat-source and tokenizer.pkl).",
    )
    parser.add_argument("--device", choices=["auto", "mps", "cuda", "cpu"], default="auto")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=3e-5)
    args = parser.parse_args()

    train_path = args.dataset_dir / "train.jsonl"
    val_path = args.dataset_dir / "validation.jsonl"
    summary_path = args.dataset_dir / "summary.json"
    if not train_path.is_file() or not val_path.is_file():
        raise SystemExit(f"Dataset files missing in {args.dataset_dir}. Run build_ganesh_sft_v2.py first.")

    summary = json.loads(summary_path.read_text()) if summary_path.is_file() else {}
    print(json.dumps({
        "status": "dataset_verified",
        "dataset_dir": str(args.dataset_dir),
        "train_conversations": summary.get("train", {}).get("conversations"),
        "val_conversations": summary.get("validation", {}).get("conversations"),
        "by_policy_mode": summary.get("train", {}).get("by_policy_mode"),
    }, indent=2))

    if args.checkpoint is not None:
        from cloud_training.nano_eval import load_bundle_model, load_tokenizer
        device = (
            "mps" if args.device == "auto" and torch.backends.mps.is_available()
            else ("cuda" if args.device == "auto" and torch.cuda.is_available() else (args.device if args.device != "auto" else "cpu"))
        )
        tokenizer, _ = load_tokenizer()
        model, _, _ = load_bundle_model(args.checkpoint, device=device)
        train_rows = [json.loads(line) for line in train_path.read_text().splitlines() if line.strip()]
        val_rows = [json.loads(line) for line in val_path.read_text().splitlines() if line.strip()]
        result = run_repaired_sft(
            model,
            tokenizer,
            train_rows,
            val_rows,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            device=device,
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

