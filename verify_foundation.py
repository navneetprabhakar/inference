"""Compare the student to a randomly initialized HF GPT-2 on a fixed tiny case."""
import json
import sys
from pathlib import Path

import torch
from torch.nn import functional as F
from transformers import GPT2Config, GPT2LMHeadModel

from gpt2 import Config, GPT2, next_token_loss
from tokenizer import document_ids, load


def verify(device):
    torch.manual_seed(42)
    config = Config(vocabulary=67, width=24, heads=3, depth=2)
    model = GPT2(config).to(device)
    ref_config = GPT2Config(vocab_size=67, n_embd=24, n_head=3, n_layer=2,
                            n_positions=1024, resid_pdrop=0, embd_pdrop=0, attn_pdrop=0)
    ref_config._attn_implementation = "eager"
    ref = GPT2LMHeadModel(ref_config).to(device).eval()
    pairs = [(model.tokens, ref.transformer.wte, False),
             (model.positions, ref.transformer.wpe, False),
             (model.final_norm, ref.transformer.ln_f, False)]
    for ours, theirs in zip(model.blocks, ref.transformer.h):
        pairs.extend([(ours.before_attention, theirs.ln_1, False),
                      (ours.before_mlp, theirs.ln_2, False),
                      (ours.qkv, theirs.attn.c_attn, True),
                      (ours.attention_out, theirs.attn.c_proj, True),
                      (ours.mlp[0], theirs.mlp.c_fc, True),
                      (ours.mlp[2], theirs.mlp.c_proj, True)])
    mapped = []
    for ours, theirs, transpose in pairs:
        for key, param in ours.named_parameters():
            other = getattr(theirs, key)
            transposed = transpose and key == "weight"
            with torch.no_grad():
                other.copy_(param.T if transposed else param)
            mapped.append((param, other, transposed))
    assert len(mapped) == len(list(model.parameters())) == len(list(ref.parameters()))
    row = torch.tensor([[1, 3, 8, 6, 5], [1, 3, 8, 9, 2]], device=device)
    logits = model(row[:, :-1])
    reference = ref(row[:, :-1]).logits
    labels = torch.tensor([[3, 8, 6, 5], [3, 8, 9, 2]], device=device)
    expected = F.cross_entropy(reference.flatten(0, 1), labels.flatten())
    actual = next_token_loss(model, row)
    tolerance = dict(atol=1e-5, rtol=1e-4)
    torch.testing.assert_close(logits, reference, **tolerance)
    torch.testing.assert_close(actual, expected, **tolerance)
    torch.testing.assert_close(logits[0, :3], logits[1, :3], **tolerance)
    actual.backward()
    expected.backward()
    max_grad = 0.
    for param, other, transposed in mapped:
        grad = other.grad.T if transposed else other.grad
        torch.testing.assert_close(param.grad, grad, **tolerance)
        max_grad = max(max_grad, (param.grad - grad).abs().max().item())
    with torch.no_grad():
        assert torch.isfinite(next_token_loss(model, torch.ones((1, 1025), dtype=torch.long, device=device)))
        try:
            model(torch.ones((1, 1025), dtype=torch.long, device=device))
        except ValueError:
            pass
        else:
            raise AssertionError("overlength input accepted")
    return dict(device=device, max_gradient_error=max_grad, loss_error=(expected-actual).abs().item(),
                max_logit_error=(logits-reference).abs().max().item())


if __name__ == "__main__":
    tokenizer = load()
    for sample, ids in json.loads(Path("tokenizer_fixtures.json").read_text()).items():
        assert document_ids(tokenizer, sample) == ids + [50256] and tokenizer.decode(ids) == sample
    print(json.dumps(verify(sys.argv[1] if len(sys.argv) > 1 else "cpu"), indent=2))
