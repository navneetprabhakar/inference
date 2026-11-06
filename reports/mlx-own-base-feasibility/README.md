# Bare MLX own-base feasibility

**Decision: a CPU-verified architecture port is feasible. Do not migrate or interrupt the current Torch campaign. Speedup is unmeasured.**

New code is limited to `mlx_base.py`, `verify_mlx_base.py`, and this report directory. The isolated `.venv-mlx-own-base` contains MLX 0.32.4, its required platform backend package mlx-metal 0.32.4, and NumPy 2.5.4. It uses approximately 262 MiB; fixtures/reports use approximately 3 MiB, below the 1 GiB cap. Installation used no package cache and downloaded no model weights. The live Torch environment and frozen runtime files were not edited.

## Frozen CPU result

The protocol was written and hashed before any MLX tensor execution: `6e1583010e1ae9f9fcf42d307762bb329786040c6d972fa1ceb3320259bb6025`. Three fixed random seeds use two layers, width 32, four heads, vocabulary 43, context 16, batch 2, and 12 input positions. Each model has 27,360 parameters. Torch exports its randomly initialized tensors into small NPZ fixtures; MLX reads those exact tensors. No model or dataset weights were downloaded.

All three cases passed every prospective tolerance. Worst observed absolute errors:

| Check | Maximum error |
|---|---:|
| Full logits | 1.1921e-7 |
| Mean next-token cross-entropy | 2.3842e-7 |
| Any parameter gradient | 8.9407e-8 |
| All-gradient relative L2 | 1.9874e-7 |
| Clipped gradient | 3.7253e-8 |
| Parameter after one AdamW update | 2.8252e-6 |
| Update relative L2 | 1.9526e-5 |
| First optimizer moment | 3.7253e-9 |
| Second optimizer moment | 4.6566e-10 |
| Causal prefix after suffix perturbation | 0 |

The update is numerically close, not bit-identical. It includes global gradient clipping, beta values (0.9, 0.95), epsilon 1e-8, matrix-only weight decay 0.1, and bias correction. The public MLX AdamW default disables bias correction, so relying on defaults would change the optimizer. The port enables it explicitly. [Pinned MLX optimizer source](https://raw.githubusercontent.com/ml-explore/mlx/v0.32.4/python/mlx/optimizers/optimizers.py).

The port keeps the original flat parameter names and shapes, pre-normalization blocks, LayerNorm epsilon 1e-5, QKV order, causal multi-head attention, tanh GELU, learned absolute positions, and tied token/output embedding. Shape arithmetic gives exactly 124,439,808 parameters for the full configuration; **no full model was allocated**. The GELU expression matches the tanh approximation in the [pinned MLX activation source](https://raw.githubusercontent.com/ml-explore/mlx/v0.32.4/python/mlx/nn/layers/activations.py).

The worker sets the default device to CPU before creating arrays and uses explicit CPU streams for native LayerNorm and attention. It refuses a non-CPU default. Actual lazy graphs were evaluated with `mx.eval`; results are not graph-construction timings. [Device selection documentation](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.set_default_device.html), [attention API](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.fast.scaled_dot_product_attention.html).

## What remains before any future migration

1. **Checkpoint conversion and ancestry.** Export only our verified checkpoint tensors; map optimizer moments by parameter name into the two MLX AdamW groups, preserving step, scheduler token count, corpus cursor and training provenance. Flat parameter names remove the need for a transposition mapping, but no full checkpoint conversion or cross-runtime optimizer resume was tested here. A new backend requires a new campaign identity and migration receipt, never a silent change to the frozen Torch campaign.
2. **Numerical trajectory and recovery.** Test several successive updates, gradient accumulation, mixed precision with FP32 master weights/moments, save/restore, and interrupted versus uninterrupted MLX execution. CPU FP32 one-step parity does not establish Metal BF16 or full-trajectory parity. Near-zero gradients can amplify small rounding differences during adaptive updates.
3. **Bounded exclusive benchmark.** Only after the live job releases the shared MPS lock, run the same 124M architecture, corpus blocks, context 512, effective batch 8,192 and optimizer objective under an exclusive process guard. Compare actual evaluated training, validation, checkpoint and restore time, not dispatch latency. Sustain long enough to expose thermal slowdown; compare against the Torch benchmark's approximately 1,257 late-window targets/s, not its short burst rate.
4. **Runtime integration.** Implement MLX-aware materialization, memory telemetry, clipping/nonfinite checks, bounded leases, durable token reservations, atomic retention, and corruption/STOP behavior. Lazy gradient accumulation must not retain an ever-growing unevaluated graph. Framework RNG/checkpoint formats are different; recovery cannot reuse Torch RNG tensors unchanged.

The small forward port is already implemented. A guarded future pilot is an estimated **2–4 engineering days**, not a measured delivery promise: checkpoint/optimizer migration and recovery tests are most of the work; an exclusive hardware benchmark is a separate prerequisite. A production-quality replacement is not justified by this diagnostic alone.

There is no evidence yet that MLX is faster for this model, that its GPU memory use fits the desired batch, or that it changes attainable language quality. The weights, architecture, data and learning objective should remain the same in a fair future runtime comparison. This is not an alternate student, corpus or pretrained-assistant path.

## Reproduction

The recorded attempt is preserved; the driver refuses to overwrite an existing result. To inspect, read `protocol.json`, `torch-reference.json`, `results.json`, `execution.log`, and `receipt.json`. In a fresh copied report location or a separately versioned experiment, the command was:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python verify_mlx_base.py
```

The existing Torch environment creates the CPU reference. The driver invokes `.venv-mlx-own-base/bin/python` only for the MLX checks, with a 120-second child timeout. The isolated environment does not contain Torch or mlx-lm. No protected conversation sets were read.
