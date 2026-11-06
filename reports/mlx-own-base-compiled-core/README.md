# Compiled own-model training core: tiny CPU verification

**Passed: six cases, 36 multi-update compiled/eager comparisons, and six exact fresh-process resumes. This does not establish GPU speed or model quality.**

`mlx_train_core.py` adds an explicit-device implementation of the existing GPT-2 architecture. Flat parameter names, tied token/output weights, LayerNorm epsilon, causal attention and tanh GELU match the original model. The implementation accepts a device explicitly; this experiment sets CPU before constructing any array and uses only the existing 27,360-parameter random fixtures.

The core captures initialized parameters and native MLX AdamW state in a compiled training function. It uses FP32 parameters and moments, bias correction, matrix-only decay, Torch-compatible global clipping, and target-count-weighted accumulation. The outer call evaluates updated state, loss and gradient norm together before recording elapsed time. Changing the learning-rate scalar between steps exercises compiled state updates rather than baking one learning rate into the graph. [MLX compilation](https://ml-explore.github.io/mlx/build/html/usage/compile.html), [lazy evaluation](https://ml-explore.github.io/mlx/build/html/usage/lazy_evaluation.html), [pinned AdamW implementation](https://raw.githubusercontent.com/ml-explore/mlx/v0.32.4/python/mlx/optimizers/optimizers.py).

The prospective `protocol.json` pins source and fixture hashes, tolerances and all six cases before execution. Seeds are 4817, 5209 and 6211; beta2 values are 0.95 and 0.99919886. Each case performs six updates with unequal microbatches of one and two rows, using 36 total targets per update, and pauses after update 3. Learning rates change from 0.001 through 0.0002. Every resumed child finishes from saved native moments, step, learning rate and cursor.

| Maximum absolute difference | Result |
|---|---:|
| Compiled versus eager weights | 1.3493e-6 |
| First moments | 9.8080e-9 |
| Second moments | 9.3133e-10 |
| Loss | 4.7684e-7 |
| Gradient norm | 2.3842e-7 |
| Unequal accumulation versus whole-batch gradients | 8.9407e-8 |
| New compiled first update versus fixed Torch weights | 4.7437e-6 |
| Forward logits versus fixed Torch reference | 1.1921e-7 |

All 88 arrays in each final checkpoint were bit-identical after fresh-process resume. Cursor, optimizer metadata, and subsequent loss/norm traces also matched exactly in all six cases. Twelve refusal checks rejected changed betas or missing moments. The fixed Torch comparison uses beta2=0.95; the two-beta multi-update comparison is compiled MLX versus eager MLX, not an independent Torch trajectory for beta2=0.99919886.

The CPU run took 34.86 seconds and reported 82,526,208 bytes peak parent-process RSS. Child resume processes run sequentially; their RSS is not added to that measurement. The recorded timings include actual evaluation, but compare tiny CPU operations and include first-call compilation. They are not an estimate for the M4 GPU or full-model training.

## Boundaries and reproduction

- No GPU operation, 124M model allocation, package installation, model download, live training change or old report modification occurred. The frozen foundation runtime hashes were checked unchanged after execution.
- FP32 only. Mixed precision, full-model Metal numerical behavior, sustained throughput, thermal behavior and memory remain future experiments.
- This is a training core, not a campaign controller. The snapshot format is a tiny feasibility format; it does not replace provenance validation, atomic checkpoint publication, reservation accounting, guards, STOP handling or production retention.
- The model has no stochastic operators. Replay uses deterministic, pre-generated batches and a saved cursor; the result does not claim restoration of a future random data sampler or cross-framework random streams.
- A nonfinite completed step raises an error and instructs its caller to discard that updated state. Production rollback belongs to the future controller.

Execution used the existing `.venv-mlx-own-base` environment with `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `VECLIB_MAXIMUM_THREADS=1` and `MLX_ENABLE_TF32=0`. The outer process enforced a 180-second timeout; each resume child has a 60-second timeout. Run `verify_mlx_train_core.py --protocol PATH` only with a new prospectively frozen protocol/report directory: the driver refuses to overwrite an existing execution directory.

Full metrics and snapshots are under `execution/`. `receipt.json` pins the resulting artifacts. No speedup or conversational capability is claimed.
