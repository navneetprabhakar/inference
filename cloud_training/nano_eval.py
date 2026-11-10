"""Finite, fixed-budget base-language evaluation for the pinned own-base recipe.

This evaluates held-out next-token loss only. It cannot establish conversation,
context-grounding or tool correctness; those have separate frozen contracts.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import torch

from cloud_training.nano_checkpoint import capture_rng, restore_rng_state, validate_bundle
from cloud_training.nano_data import PackedRows

PINNED_REVISION = '92d63d4e8bb4df75c3b71618f31ddde2378b2bcd'


def verify_upstream(repo):
    repo = Path(repo).resolve()
    rev = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain'], text=True).strip()
    if rev != PINNED_REVISION or dirty:
        raise ValueError('Evaluation requires the pinned clean upstream checkout')
    return rev


def evaluate_packed(model, directory, *, tokenizer_sha256, token_budget,
                    batch_rows=1, device=None, actual_revision,
                    expected_manifest_sha256=None):
    """Return token-weighted CE over an exact prefix of a validation-only corpus.

    Caller supplies actual_revision from verify_upstream (or an equivalent launch
    verification). Every call starts at row zero, never consumes the training
    iterator, never wraps, and requires a whole-row token budget. Evaluation
    preserves RNG and each submodule's train/eval flag. No optimizer is accepted.
    """
    if actual_revision != PINNED_REVISION:
        raise ValueError('Unreviewed upstream evaluation revision')
    if type(token_budget) is not int or token_budget <= 0:
        raise ValueError('Positive integer token budget required')
    if type(batch_rows) is not int or batch_rows <= 0:
        raise ValueError('Positive batch_rows required')
    reader = PackedRows(directory, expected_tokenizer_sha256=tokenizer_sha256,
                        expected_split='validation', verify_hash=True)
    manifest = reader.manifest
    if expected_manifest_sha256 is not None and reader.manifest_sha256 != expected_manifest_sha256:
        raise ValueError('Validation manifest differs from frozen evaluation corpus')
    seq = manifest['sequence_length']
    if token_budget % seq:
        raise ValueError('Token budget must be an exact multiple of packed sequence length')
    row_budget = token_budget // seq
    if row_budget > manifest['rows']:
        raise ValueError('Evaluation budget exceeds finite validation data; replay prohibited')
    config = model.config
    if config.vocab_size != manifest['vocab_size']:
        raise ValueError('Model/tokenizer vocabulary mismatch')
    if seq > config.sequence_len:
        raise ValueError('Validation rows exceed model context length')
    parameter_device = next(model.parameters()).device
    device = torch.device(device or parameter_device)
    if device.type == parameter_device.type and device.index is None:
        device = parameter_device  # resolve 'cuda' against this already-placed model
    if any(p.device != device for p in model.parameters()):
        raise ValueError('Model parameter device mismatch')
    modes = [(module, module.training) for module in model.modules()]
    rng = capture_rng()
    losses, counts = [], []
    tick = time.monotonic()
    if device.type == 'cuda':
        torch.cuda.synchronize(device)
    try:
        model.eval()
        with torch.inference_mode():
            remaining = row_budget
            while remaining:
                rows = min(batch_rows, remaining)
                x, y = reader.read(rows)
                # Validate read token ranges too; integrity is not semantic admission.
                if any(t < 0 or t >= config.vocab_size for row in x + y for t in row):
                    raise ValueError('Validation token outside model vocabulary')
                xt = torch.tensor(x, dtype=torch.long, device=device)
                yt = torch.tensor(y, dtype=torch.long, device=device)
                loss_sum = model(xt, yt, loss_reduction='sum')
                if loss_sum.ndim != 0 or not bool(torch.isfinite(loss_sum)):
                    raise ValueError('Nonfinite or nonscalar validation loss')
                losses.append(float(loss_sum))
                counts.append(rows * seq)
                remaining -= rows
        if device.type == 'cuda':
            torch.cuda.synchronize(device)
    finally:
        for module, mode in modes:
            module.training = mode
        restore_rng_state(rng)
    count = sum(counts)
    if count != token_budget:
        raise RuntimeError('Validation target count differs from frozen budget')
    total = math.fsum(losses)
    ce = total / count
    seconds = time.monotonic() - tick
    return {'schema': 1, 'status': 'finite_validation_complete', 'purpose': 'base_language_loss_only',
            'revision': actual_revision, 'dataset_manifest_sha256': reader.manifest_sha256,
            'source_manifest_sha256': manifest['source_manifest_sha256'],
            'tokenizer_sha256': tokenizer_sha256, 'split': 'validation',
            'packing': manifest['packing'], 'sequence_length': seq,
            'target_tokens': count, 'rows': row_budget, 'batches': len(counts),
            'negative_log_likelihood_sum': total, 'cross_entropy_nats': ce,
            'perplexity': math.exp(ce) if ce < 700 else None,
            'seconds': seconds, 'targets_per_second': count / seconds,
            'source_admission': manifest.get('evaluation_admitted', False),
            'limitation': 'Finite packed held-out CE is not chat/tool acceptance or proof of source decontamination.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--validation', required=True)
    parser.add_argument('--tokenizer-sha256', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--tokens', type=int, required=True)
    parser.add_argument('--batch-rows', type=int, default=1)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    rev = verify_upstream(args.repo)
    sys.path.insert(0, str(Path(args.repo).resolve()))
    from nanochat.gpt import GPT, GPTConfig
    checkpoint = Path(args.checkpoint)
    validate_bundle(checkpoint)
    metadata = json.loads((checkpoint / 'metadata.json').read_text())
    identity = metadata['identity']
    if identity.get('revision') != rev or identity.get('tokenizer_sha256') != args.tokenizer_sha256:
        raise ValueError('Checkpoint revision/tokenizer identity differs from evaluation')
    config = GPTConfig(**identity['config'])
    with torch.device('meta'):
        model = GPT(config)
    model.to_empty(device=args.device)
    model.init_weights()  # initializes nonpersistent RoPE buffers; weights replaced below
    payload = torch.load(checkpoint / 'payload.pt', map_location='cpu', weights_only=True)
    model.load_state_dict(payload['model'], strict=True)
    del payload
    result = evaluate_packed(model, args.validation, tokenizer_sha256=args.tokenizer_sha256,
                             token_budget=args.tokens, batch_rows=args.batch_rows,
                             device=args.device, actual_revision=rev,
                             expected_manifest_sha256=args.manifest_sha256)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
