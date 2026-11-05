"""Randomly initialized GPT-2 small and a local forward-pass check."""
import argparse
from dataclasses import dataclass

import torch
from torch import nn
from torch.nn import functional as F


@dataclass(frozen=True)
class Config:
    vocabulary: int = 50257
    context: int = 1024
    width: int = 768
    heads: int = 12
    depth: int = 12


class Block(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.heads = config.heads
        width = config.width
        if width % self.heads:
            raise ValueError("width must be divisible by the number of heads")
        self.before_attention = nn.LayerNorm(width)
        self.before_mlp = nn.LayerNorm(width)
        self.qkv = nn.Linear(width, 3 * width)
        self.attention_out = nn.Linear(width, width)
        self.mlp = nn.Sequential(
            nn.Linear(width, 4 * width), nn.GELU(approximate="tanh"),
            nn.Linear(4 * width, width),
        )

    def forward(self, hidden):
        batch, length, width = hidden.shape
        projected = self.qkv(self.before_attention(hidden))
        heads = projected.reshape(batch, length, 3, self.heads, width // self.heads)
        query, key, value = heads.permute(2, 0, 3, 1, 4).unbind(0)
        attention = F.scaled_dot_product_attention(query, key, value, is_causal=True)
        hidden = hidden + self.attention_out(attention.transpose(1, 2).reshape_as(hidden))
        return hidden + self.mlp(self.before_mlp(hidden))


class GPT2(nn.Module):
    def __init__(self, config=Config()):
        super().__init__()
        self.tokens = nn.Embedding(config.vocabulary, config.width)
        self.positions = nn.Embedding(config.context, config.width)
        self.blocks = nn.ModuleList(Block(config) for _ in range(config.depth))
        self.final_norm = nn.LayerNorm(config.width)
        for module in self.modules():
            if isinstance(module, (nn.Linear, nn.Embedding)):
                nn.init.normal_(module.weight, std=0.02)
            if isinstance(module, nn.Linear):
                nn.init.zeros_(module.bias)
        for block in self.blocks:
            for projection in (block.mlp[-1], block.attention_out):
                nn.init.normal_(projection.weight, std=0.02 / (2 * config.depth) ** 0.5)

    def forward(self, token_ids):
        length = token_ids.size(1)
        if not 0 < length <= self.positions.num_embeddings:
            raise ValueError("sequence length is outside the model context")
        positions = torch.arange(length, device=token_ids.device)
        hidden = self.tokens(token_ids) + self.positions(positions)
        for block in self.blocks:
            hidden = block(hidden)
        return F.linear(self.final_norm(hidden), self.tokens.weight)


def next_token_loss(model, sequence):
    """Each row contains input IDs followed by one extra target ID."""
    logits = model(sequence[:, :-1])
    return F.cross_entropy(logits.flatten(0, 1), sequence[:, 1:].flatten())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    args = parser.parse_args()
    torch.manual_seed(42)
    with torch.inference_mode():
        model = GPT2().to(args.device).eval()
        count = sum(weight.numel() for weight in model.parameters())
        assert count == 124_439_808
        # Change the suffix and check that earlier predictions cannot see it.
        pair = torch.tensor([[101, 102, 103, 104], [101, 102, 110, 111]], device=args.device)
        logits = model(pair)
        torch.testing.assert_close(logits[0, :2], logits[1, :2], atol=1e-5, rtol=1e-5)
        loss = next_token_loss(model, pair)
        assert torch.isfinite(loss)
        print(f"{args.device}: {count:,} parameters; logits {tuple(logits.shape)}; "
              f"synthetic next-token loss {loss.item():.4f}; causal prefix check passed")
