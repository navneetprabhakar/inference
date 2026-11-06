# Tiny own-model optimizer conversion and MLX resume

**Result: passed for all three frozen CPU fixtures. No migration or change to the live Torch campaign. Speed remains unknown.**

This adds `mlx_checkpoint_bridge.py` and `verify_mlx_base_resume.py`. It reuses the earlier CPU architecture port, isolated bare-MLX environment, and exact random initial tensors. No full 124M model, live checkpoint, protected conversation set, GPU operation, pretrained weights, or new package installation was involved.

## Experiment and results

Protocol SHA-256: `fd621afc0620f84134e7ea17a1292bf2b864696b0e33ac536790a64af20cb63c`. It was frozen before execution, including tolerances and negative controls.

Each seed uses the same two-layer, width-32, four-head, context-16 decoder with 27,360 parameters. Torch performs three updates, producing nonzero AdamW moments. The bridge exports parameter-named FP32 weights, first/second moments, per-group step and learning rate, model configuration, token cursor, source RNG bytes and an explicit target-runtime key into checksummed NPZ/JSON. Native MLX AdamW receives these moments and step counters; they are not reset.

Both backends then perform five more updates. Every update accumulates unequal microbatches of one and two sequences, each with 12 targets, normalized by all 36 targets before clipping. This tests weighted accumulation rather than incorrectly averaging microbatch means. The native MLX whole-batch gradient is checked separately against its accumulated gradient.

All 15 cross-framework updates passed. Maximum absolute errors across seeds and updates:

| Check | Maximum error |
|---|---:|
| Mean causal loss | 4.7684e-7 |
| Full logits | 1.7881e-7 |
| Parameter gradients versus Torch | 8.9407e-8 |
| Accumulated versus whole-batch MLX gradient | 1.3411e-7 |
| Updated weights versus Torch | 1.7459e-6 |
| First optimizer moments | 7.9162e-9 |
| Second optimizer moments | 9.3132e-10 |

The Torch-to-neutral-to-MLX-to-neutral state conversion was exact for all three seeds. Each backend uses bias-corrected AdamW, betas (0.9, 0.95), epsilon 1e-8, learning rate 0.001, matrix-only decay 0.1, and global clipping at 1. The public MLX state setter accepts the named moment tree and group counters; bias correction is explicitly enabled rather than relying on its different default. [Pinned official MLX optimizer implementation](https://raw.githubusercontent.com/ml-explore/mlx/v0.32.4/python/mlx/optimizers/optimizers.py).

## Fresh-process resume

The uninterrupted MLX branch saves at step 5 and continues to step 8. A separate CPU Python process restores step 5, chooses remaining batches from the saved cursor, and finishes step 8. Across all three seeds:

- All **90 arrays per checkpoint** were bit-identical: weights, moments, group learning rates and steps, explicit MLX PRNG key and preserved Torch RNG bytes.
- Subsequent losses and explicit PRNG canary values matched exactly.
- Cursor matched exactly: step 8, 288 trained targets, offset 288.
- All seven negative controls per seed were refused: changed bytes, missing moment, inconsistent optimizer step, missing RNG key, inconsistent cursor, wrong decay, and wrong experiment identity. Structural corruptions were given recomputed checksums, so those tests exercise semantic validation as well as digest checks.

There were **21 successful refusal checks**. The result files retain every per-seed/per-update metric and refusal reason.

## Boundaries of this evidence

- **RNG algorithms are not interchangeable.** Torch RNG state is retained opaquely as provenance. A new, explicit MLX random stream is assigned at conversion; it is not claimed to reproduce Torch random draws. The decoder has no dropout or stochastic training operators. Per-update canaries verify target-runtime RNG restoration, not cross-framework stochastic equivalence or a future corpus shuffler.
- **The bridge operates on reconstructed CPU model/optimizer objects and small neutral bundles.** It does not parse the production campaign's complete `.pt` archive, verify its parent acceptance chain, or authorize an actual migration. Those checks remain mandatory for a future converter.
- **No production controller is implemented.** This checks one valid optimizer-boundary save and fresh-process resume. It does not establish crash-safe publication, fsync guarantees, token reservations, retention, concurrent readers, thermal recovery or STOP behavior. The bridge's simple file writes must not replace the current campaign checkpoint machinery.
- **The schedule is constant here.** Scheduler transitions, reserved-versus-committed counters, full corpus traversal, mixed precision, long numerical trajectories and full-model Metal memory/performance remain untested.
- Torch and MLX updates are numerically close, not bit-identical. Only MLX uninterrupted versus MLX restored execution is bit-identical in this experiment.

This removes uncertainty about parameter-name/moment mapping and tiny CPU continuation. It does not justify interrupting the current tranche. A future exclusive GPU benchmark must wait until the current trainer releases its lock and use a new frozen backend identity and bounded protocol.

## Artifacts and reproduction

`protocol.json` pins the implementation and previous random fixtures. `references.json` pins the Torch reference NPZ files. Each source, paused and final checkpoint bundle contains a checksummed `receipt.json` and `state.npz`. `results.json`, `resume-*.json` and `trace-*.json` record outcomes. `receipt.json` at this report root pins all artifacts and the unchanged production runtime checks.

The existing Torch environment creates the reference; the isolated MLX environment runs conversion/resume. Torch is not installed into the MLX environment. The recorded driver command was:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python verify_mlx_base_resume.py
```

The driver refuses to overwrite existing reference results. A repetition requires a new experiment version. The MLX worker is bounded to 180 seconds; each fresh resume child is bounded to 60 seconds. The environment plus both feasibility report trees remain well below the 1 GiB additional-disk ceiling; exact allocated sizes are in the root receipt.
