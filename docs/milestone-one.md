# Tiny model prototype results

Creator: Navneet Prabhakar

Validated locally on 18 October 2026.

- **Result:** 27 tests passed, 1 CUDA test skipped. Final suite runtime: 2.28 seconds after dependencies/imports were warm.
- **Hardware paths:** MLX on Apple GPU, PyTorch on CPU. NVIDIA CUDA was unavailable and has not been validated.
- **Model:** 20,640 parameters; two blocks, width 32, intermediate width 64, four query heads, two KV heads, vocabulary 64, context 64.
- **Scope:** independent FP32 reference models, canonical initialization, model-only checkpoint serialization, reference optimizer, fixture conversation serializer, and numerical parity tests.
- **No training corpus, teacher invocation, model download, GCP provisioning, or substantial pretraining was performed.** The 100-update test learns a small fixed synthetic batch as a correctness check.

## Checks completed

| Area | Evidence |
| --- | --- |
| Architecture | Canonical parameter shapes/counts; tied input/output embedding; deterministic initialization |
| Forward and gradients | Layer states, logits, masked loss and every gradient compared across MLX/PyTorch; sequence lengths 1, 12 and 64; MHA, GQA and MQA head arrangements |
| Numerical conventions | Known RoPE rotation checked against analytic values; loss checked against PyTorch native cross-entropy |
| Attention | Causal-prefix invariance, right-padding equivalence, token/chunk cached decoding, context-limit rejection |
| Optimizer | Reference bias-corrected AdamW compared with native PyTorch AdamW over multiple updates, including clipped and zero gradients and excluded decay groups |
| Training parity | 100 consecutive MLX/PyTorch updates; losses, weights and both optimizer moments compared at every update; fixed-batch loss below 1 |
| Accumulation | Unequal microbatch supervised-token counts reproduce full-batch gradients when correctly weighted |
| Weights | MLX → Safetensors → PyTorch → Safetensors → MLX round trip; checksums, invalid tensors, incomplete checkpoint rejection and no overwrite |
| Serialization | Byte-fixture role boundaries, shifted assistant loss masks, UTF-8, and content unable to inject reserved role IDs |

Forward/loss/weight comparisons use `atol=1e-5`, `rtol=1e-4`; gradients and moment comparisons use tighter absolute bounds where specified in tests. Thresholds were not loosened to obtain passing results.

## Representative numerical measurement

Separate diagnostic fixture: seed 42 initialization, two rows of four tokens, mixed supervised-token mask. These numbers describe this fixture, not the worst error across the entire test suite.

| Metric | Absolute error |
| --- | --- |
| Maximum logit difference | 8.94e-8 |
| Mean logit difference | 1.42e-8 |
| Loss difference | 4.77e-7 |
| Maximum parameter-gradient difference | 1.79e-7 |

Machine-readable evidence: [test results](../reports/milestone-one-tests.xml) and [numerical measurement](../reports/milestone-one-numerics.json).

Environment: Python 3.12.11, MLX 0.32.4, PyTorch 2.14.1, NumPy 2.5.4, Safetensors 0.8.0. Exact local package versions are recorded in [requirements-macos.lock](../requirements-macos.lock).

## Reproduce

```sh
.venv/bin/python -m pytest -q --junitxml=reports/milestone-one-tests.xml
```

See the [root README](../README.md) for environment setup and model usage.

## Remaining gates

- Actual CUDA forward/backward validation and MLX↔CUDA artifact exchange across hosts. The optional CUDA test currently checks CPU/CUDA logits only; it does not establish training portability.
- Portable optimizer state, scheduler, deterministic data cursor and training resume. Current checkpoints contain model weights only. Carrying in-memory optimizer state through the 100-step comparison is not a checkpoint-resume test.
- Full 81M model initialization and layer-depth parity, reduced precision and optimized kernels.
- Production BPE tokenizer, training data, teacher provider integration, complete training loop and evaluation corpus.
- Left padding and padded cached decoding are unsupported in the reference interface; right-padded non-cached batches and unpadded caches are supported.

The next implementation milestone is training-state checkpoint migration and deterministic resume, followed by validation on NVIDIA hardware before a substantial training run.
