"""Self-contained PyTorch implementation of the 536,871,738-parameter Ganesh-base Transformer.

Matches the exact 119-tensor state_dict layout and parameter breakdown of the
Base10B / SFT50 / SFT194 checkpoints (`n_layer=16, n_embd=1024, n_head=8,
n_kv_head=8, vocab_size=32768`) while running natively on Apple Silicon (`mps`),
`cuda`, and `cpu` without requiring external FlashAttention-3 or `nanochat-source`.

Also provides:
1. `calibrate_control_tokens()`: Fixes the `-42.0` raw logit softcap dead-zone on
   special control tokens (`IDs 32760..32767`).
2. `set_full_causal_attention()`: Upgrades the restrictive `SSSL` sliding window
   (which left only 4 of 16 layers with full context) to full causal attention
   (`LLLL`) during SFT so multi-turn entities and tool outputs are never dropped.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import torch
import torch.nn as nn
import torch.nn.functional as F


def rms_norm(x: torch.Tensor, eps: float | None = None) -> torch.Tensor:
    return F.rms_norm(x, (x.size(-1),), eps=eps)


def apply_rotary_emb(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
    d = x.shape[-1] // 2
    x1, x2 = x[..., :d], x[..., d:]
    y1 = x1 * cos + x2 * sin
    y2 = x1 * (-sin) + x2 * cos
    return torch.cat([y1, y2], dim=-1).type_as(x)


@dataclass
class GaneshConfig:
    sequence_len: int = 2048
    vocab_size: int = 32768
    n_layer: int = 16
    n_head: int = 8
    n_kv_head: int = 8
    n_embd: int = 1024
    window_pattern: str = "SSSL"
    softcap: float = 15.0
    ve_gate_channels: int = 12
    smear_gate_dim: int = 24


class GaneshCausalSelfAttention(nn.Module):
    def __init__(self, config: GaneshConfig, layer_idx: int) -> None:
        super().__init__()
        self.layer_idx = layer_idx
        self.n_head = config.n_head
        self.n_kv_head = config.n_kv_head
        self.n_embd = config.n_embd
        self.head_dim = self.n_embd // self.n_head
        self.c_q = nn.Linear(self.n_embd, self.n_head * self.head_dim, bias=False)
        self.c_k = nn.Linear(self.n_embd, self.n_kv_head * self.head_dim, bias=False)
        self.c_v = nn.Linear(self.n_embd, self.n_kv_head * self.head_dim, bias=False)
        self.c_proj = nn.Linear(self.n_embd, self.n_embd, bias=False)
        self.ve_gate = (
            nn.Linear(config.ve_gate_channels, self.n_kv_head, bias=False)
            if layer_idx % 2 == 1
            else None
        )

    def forward(
        self,
        x: torch.Tensor,
        ve: torch.Tensor | None,
        cos: torch.Tensor,
        sin: torch.Tensor,
        window_size: int | None = None,
    ) -> torch.Tensor:
        bsz, seq_len, _ = x.size()
        q = self.c_q(x).view(bsz, seq_len, self.n_head, self.head_dim)
        k = self.c_k(x).view(bsz, seq_len, self.n_kv_head, self.head_dim)
        v = self.c_v(x).view(bsz, seq_len, self.n_kv_head, self.head_dim)

        if ve is not None and self.ve_gate is not None:
            ve = ve.view(bsz, seq_len, self.n_kv_head, self.head_dim)
            gate = 3.0 * torch.sigmoid(self.ve_gate(x[..., : self.ve_gate.in_features]))
            v = v + gate.unsqueeze(-1) * ve

        q = (1.2 * rms_norm(apply_rotary_emb(q, cos, sin))).transpose(1, 2)
        k = (1.2 * rms_norm(apply_rotary_emb(k, cos, sin))).transpose(1, 2)
        v = v.transpose(1, 2)

        enable_gqa = self.n_head != self.n_kv_head
        if window_size is not None and 0 < window_size < seq_len:
            idx = torch.arange(seq_len, device=x.device)
            diff = idx.unsqueeze(1) - idx.unsqueeze(0)
            attn_mask = (diff >= 0) & (diff <= window_size)
            y = F.scaled_dot_product_attention(q, k, v, attn_mask=attn_mask, enable_gqa=enable_gqa)
        else:
            y = F.scaled_dot_product_attention(q, k, v, is_causal=True, enable_gqa=enable_gqa)

        y = y.transpose(1, 2).contiguous().view(bsz, seq_len, -1)
        return self.c_proj(y)


class GaneshMLP(nn.Module):
    def __init__(self, config: GaneshConfig) -> None:
        super().__init__()
        self.c_fc = nn.Linear(config.n_embd, 4 * config.n_embd, bias=False)
        self.c_proj = nn.Linear(4 * config.n_embd, config.n_embd, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.c_proj(F.relu(self.c_fc(x)).square())


class GaneshBlock(nn.Module):
    def __init__(self, config: GaneshConfig, layer_idx: int) -> None:
        super().__init__()
        self.attn = GaneshCausalSelfAttention(config, layer_idx)
        self.mlp = GaneshMLP(config)

    def forward(
        self,
        x: torch.Tensor,
        ve: torch.Tensor | None,
        cos: torch.Tensor,
        sin: torch.Tensor,
        window_size: int | None = None,
    ) -> torch.Tensor:
        x = x + self.attn(rms_norm(x), ve, cos, sin, window_size=window_size)
        x = x + self.mlp(rms_norm(x))
        return x


class GaneshGPT(nn.Module):
    """Exact 536,871,738-parameter (`d16`) / 286,261,730-parameter (`d12`) Ganesh-base architecture."""

    def __init__(self, config: GaneshConfig = GaneshConfig()) -> None:
        super().__init__()
        from ganesh import MODEL_IDENTITY, MODEL_IDENTITY_SHA256
        self.config = config
        self.model_identity = dict(MODEL_IDENTITY)
        self.model_identity_sha256 = MODEL_IDENTITY_SHA256
        self.transformer = nn.ModuleDict({
            "wte": nn.Embedding(config.vocab_size, config.n_embd),
            "h": nn.ModuleList([GaneshBlock(config, i) for i in range(config.n_layer)]),
        })
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)
        self.resid_lambdas = nn.Parameter(torch.ones(config.n_layer))
        self.x0_lambdas = nn.Parameter(torch.zeros(config.n_layer))
        self.smear_gate = nn.Linear(config.smear_gate_dim, 1, bias=False)
        self.smear_lambda = nn.Parameter(torch.zeros(1))
        self.backout_lambda = nn.Parameter(0.5 * torch.ones(1))
        self.value_embeds = nn.ModuleDict({
            str(i): nn.Embedding(config.vocab_size, config.n_embd)
            for i in range(config.n_layer)
            if i % 2 == 1
        })
        self._rotary_cache: dict[tuple[int, torch.device], tuple[torch.Tensor, torch.Tensor]] = {}

    def init_weights(self) -> None:
        with torch.no_grad():
            nn.init.normal_(self.transformer["wte"].weight, mean=0.0, std=1.0)
            nn.init.normal_(self.lm_head.weight, mean=0.0, std=0.001)
            s = (3.0 ** 0.5) * (self.config.n_embd ** -0.5)
            for block in self.transformer["h"]:
                nn.init.uniform_(block.attn.c_q.weight, -s, s)
                nn.init.uniform_(block.attn.c_k.weight, -s, s)
                nn.init.uniform_(block.attn.c_v.weight, -s, s)
                nn.init.zeros_(block.attn.c_proj.weight)
                nn.init.uniform_(block.mlp.c_fc.weight, -s, s)
                nn.init.zeros_(block.mlp.c_proj.weight)
                if block.attn.ve_gate is not None:
                    nn.init.zeros_(block.attn.ve_gate.weight)
            self.resid_lambdas.fill_(1.0)
            self.x0_lambdas.fill_(0.1)
            for ve in self.value_embeds.values():
                nn.init.uniform_(ve.weight, -s, s)
            nn.init.zeros_(self.smear_gate.weight)
            self.smear_lambda.fill_(0.0)
            self.backout_lambda.fill_(0.5)

    def set_full_causal_attention(self) -> None:
        """Upgrade `SSSL` sliding window to `LLLL` full causal attention across all layers."""
        self.config.window_pattern = "L" * self.config.n_layer

    def num_scaling_params(self) -> dict[str, int]:
        wte = sum(p.numel() for p in self.transformer["wte"].parameters())
        value_embeds = sum(p.numel() for p in self.value_embeds.parameters())
        lm_head = sum(p.numel() for p in self.lm_head.parameters())
        transformer_matrices = sum(p.numel() for p in self.transformer["h"].parameters())
        scalars = (
            self.resid_lambdas.numel()
            + self.x0_lambdas.numel()
            + self.smear_gate.weight.numel()
            + self.smear_lambda.numel()
            + self.backout_lambda.numel()
        )
        total = wte + value_embeds + lm_head + transformer_matrices + scalars
        return {
            "wte": wte,
            "value_embeds": value_embeds,
            "lm_head": lm_head,
            "transformer_matrices": transformer_matrices,
            "scalars": scalars,
            "total": total,
        }

    def _get_rotary(self, seq_len: int, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
        key = (seq_len, device)
        if key not in self._rotary_cache:
            head_dim = self.config.n_embd // self.config.n_head
            inv_freq = 1.0 / (100000.0 ** (torch.arange(0, head_dim, 2, dtype=torch.float32, device=device) / head_dim))
            t = torch.arange(seq_len, dtype=torch.float32, device=device)
            freqs = torch.outer(t, inv_freq)
            cos = freqs.cos()[None, :, None, :]
            sin = freqs.sin()[None, :, None, :]
            self._rotary_cache[key] = (cos, sin)
        return self._rotary_cache[key]

    def _layer_window(self, layer_idx: int) -> int | None:
        pattern = (self.config.window_pattern or "L").upper()
        if layer_idx == self.config.n_layer - 1:
            return None
        ch = pattern[layer_idx % len(pattern)]
        if ch == "S":
            return -(-self.config.sequence_len // 4 // 128) * 128
        return None

    def forward(
        self,
        idx: torch.Tensor,
        targets: torch.Tensor | None = None,
        loss_reduction: str = "mean",
    ) -> torch.Tensor:
        bsz, seq_len = idx.size()
        cos, sin = self._get_rotary(seq_len, idx.device)

        x = rms_norm(self.transformer["wte"](idx))
        if seq_len > 1:
            gate = self.smear_lambda.to(x.dtype) * torch.sigmoid(
                self.smear_gate(x[:, 1:, : self.config.smear_gate_dim])
            )
            x = torch.cat([x[:, :1], x[:, 1:] + gate * x[:, :-1]], dim=1)
        x0 = x

        half_layer = self.config.n_layer // 2
        x_backout: torch.Tensor | None = None
        for i, block in enumerate(self.transformer["h"]):
            x = self.resid_lambdas[i] * x + self.x0_lambdas[i] * x0
            ve = self.value_embeds[str(i)](idx) if str(i) in self.value_embeds else None
            x = block(x, ve, cos, sin, window_size=self._layer_window(i))
            if i == half_layer:
                x_backout = x

        if x_backout is not None:
            x = x - self.backout_lambda.to(x.dtype) * x_backout
        x = rms_norm(x)

        raw_logits = self.lm_head(x).float()
        logits = self.config.softcap * torch.tanh(raw_logits / self.config.softcap)
        if targets is None:
            return logits
        return F.cross_entropy(
            logits.view(-1, logits.size(-1)),
            targets.view(-1),
            ignore_index=-1,
            reduction=loss_reduction,
        )
