# Full own-model MLX feasibility benchmark — proposed, not executable

**Status: protocol for root review. No GPU run, conversion, download or production migration is authorized by this file.** The current foundation and three-arm optimizer queue keep exclusive priority. This experiment can begin only after that queue reaches its expected successful endpoint, its supervisors exit, and the shared GPU lock is free. A failed, interrupted, partial or stopped queue requires review; it must not trigger this benchmark automatically.

The question is whether the existing, independently initialized 124,439,808-parameter model can execute correctly and usefully through MLX on this M4 Air. This is an execution experiment. Its updates are disposable and never become a training or chat candidate. Lower wall time does not establish language quality.

## Current implementation and gaps

`mlx_train_core.py` preserves the architecture's flat parameter names, tied embedding/output projection, causal attention, LayerNorm epsilon and tanh GELU. Its CPU evidence covers three tiny random fixtures, beta2 values 0.95 and 0.99919886, compiled/eager updates, unequal accumulation, and exact fresh-process native-optimizer resume. It currently executes FP32 throughout.

The frozen Torch trainers instead keep FP32 parameters and AdamW moments while wrapping each microbatch forward/loss in MPS BF16 autocast. They accumulate eight microbatch gradients before one globally clipped optimizer update and explicitly synchronize MPS. The MLX core compiles all eight microbatches into one captured graph and evaluates state/loss after the update. That difference can affect peak memory and scheduling; it must be measured, not assumed beneficial.

The existing neutral bridge is a tiny CPU fixture converter, not a validated production checkpoint loader. The core snapshot also does not contain complete architecture/ancestry, campaign budgets, RNG provenance, scheduler identity or crash-safe publication semantics. A production adapter must keep optimizer step distinct from branch/campaign step and the corpus cursor, especially for a preserve-moments ablation whose optimizer step includes its parent. These deficiencies block production migration today.

## Fixed selection and identities

1. After the queue ends, choose the exact protected foundation endpoint as the common benchmark source: `runs/own-base-foundation-01`, trained and reserved targets both 99,999,744. Using this predetermined common parent avoids selecting whichever ablation gives attractive timing. No implicit `latest` selection is permitted once this receipt is bound.
2. Verify parent campaign checksum and immutable specification, terminal supervisor identity, protected checkpoint inventory, checkpoint byte count/SHA, architecture, tokenizer, corpus hashes, original own-random lineage and all source-code hashes. Confirm that the chosen checkpoint is the durable ledger's accepted endpoint, not an unreceipted file.
3. Freeze a machine-readable benchmark specification with the exact filename/SHA, optimizer groups and steps, data offset and bytes, package/environment versions, code hashes, order, tolerances, resource limits and every comparison below. Pin both the existing Torch implementation and any new benchmark adapter. This prose document is not that executable freeze.
4. Use one fixed contiguous development-training slice starting at source offset 99,999,744 in the already verified GPT-2 corpus. Reserve 16,777,216 targets plus the final boundary input; verify it fits without wrapping. The same first 2,048 updates are available to each timed path. No validation or protected conversation cases enter updates. This slice is reused only across disposable comparisons, not represented as fresh or statistically independent training.

## Budgets and resource admission

Proposed ceiling for this first **FP32 feasibility version**: 180 active GPU minutes, six calendar hours from benchmark launch, and 24,993,792 attempted training targets across all phases and repeats. Reserve attempts before updates; warm-up and correctness updates also consume the token ceiling. Neither an interrupted update nor replay refunds attempts. The per-phase ceilings below cannot expand the aggregate ceiling.

- Stage A correctness and conversion: at most45 active minutes.
- Stage B warm-up: at most5 minutes for each of three runtime configurations, at most15 total.
- Stage C sustained comparison: exactly30 active minutes per configuration, at most90 total.
- Stage D native resume and reporting: at most15 active minutes.
- Remaining15 minutes cover controlled setup/teardown and one explicitly logged retry for infrastructure failure; no retry may replace an unfavorable numerical or performance result. Any phase that cannot finish within its cap is incomplete, not passed.

Additional benchmark disk is capped at4GiB. Before launch, require actual free space at least20GiB plus a conservative forecast: two full-state files sized at `ceil(1.1 × parent_checkpoint_bytes) + 16MiB` each, one512MiB gradient/reference allowance, and256MiB for inputs/logs/metadata. If this forecast exceeds4GiB or does not fit above the20GiB floor, stop prepared without touching protected or user files. Given the retained foundation/ablation checkpoints, disk admission may fail; do not conceal that by deleting evidence.

Only newly created, explicitly disposable conversion/reference files may be removed after their needed comparisons are recorded and the protected source remains verified. Never retain more than one native checkpoint plus its in-flight atomic replacement. Stream parameter comparisons in bounded chunks; do not write several full snapshots just to simplify testing.

Run one GPU subprocess at a time, under the existing `runs/mps.lock` convention. Respect global `runs/STOP`, the foundation STOP, all ablation STOP files and the new benchmark STOP. Retain AC-only sleep handling, serious thermal stop, repeated RSS above18GiB or swap growth above1GiB,20GiB disk floor, unavailable-telemetry stop and30-second telemetry checks. Additionally stop a benchmark allocation path if reported active GPU allocations reach12GiB. Framework GPU allocations and process RSS overlap in unified memory and must not be added as independent physical usage. Pin the initial system swap baseline and record driver/cache memory separately.

Keep the source optimizer archive memory-mapped on CPU where possible. Release each runtime subprocess before starting another; do not hold complete Torch/MPS and MLX/GPU models concurrently. A watchdog enforces phase and aggregate wall bounds even if compilation or a device operation stops returning.

## Stage A: correctness before performance

A production-shaped neutral conversion adapter must be implemented and reviewed separately before this phase. It must map optimizer parameter IDs through the actual instantiated Torch model/optimizer parameter objects, never assume integer IDs correspond to a guessed name order.

**Exact conversion gate, CPU:** all148 parameter tensors, all first/second moments, shapes, FP32 dtypes, matrix/nonmatrix group membership, decay, betas, epsilon, bias correction, learning rate and per-parameter optimizer steps must agree byte-for-byte after export/import/export. Reject missing/extra tensors, mismatched steps, nonfinite values, negative second moments, altered hashes and wrong ancestry. Preserve original Torch CPU/MPS RNG bytes opaquely; do not claim they are equivalent to an MLX random stream. No stochastic operator is needed for these fixed batches. Keep original corpus offset, campaign step and optimizer step as distinct explicit fields.

**Full FP32 cross-runtime gate:** compare Torch CPU reference, Torch MPS FP32 and MLX GPU FP32 on two predetermined complete B2×T512 microbatches, sequentially and with explicit synchronization. Compute all-parameter gradients against the same causal targets. Compare every tensor, not only a sampled layer. Full logits can be compared one microbatch at a time, without keeping them across the eight-microbatch update. Then perform two complete B2×T512×accum8 updates from the same restored source state, using preserved moments and fixed LR6e-5 in both runtimes.

Prospective ceilings, to be frozen before execution:

| Quantity | Required maximum |
|---|---:|
| Mean FP32 causal loss absolute error | 1e-4 |
| Full-logit RMS difference | 1e-4 |
| Full-logit maximum absolute difference | 1e-3 |
| All-gradient global relative L2 difference | 1e-3 |
| Per-tensor gradient maximum absolute difference | 1e-4 |
| Global gradient-norm relative difference | 1e-3 |
| Two-update weights maximum absolute difference | 5e-5 |
| Update-delta global relative L2 difference | 0.02 |
| First moments maximum absolute difference | 1e-5 |
| Second moments maximum absolute difference | 1e-5 |

Report absolute and relative errors together. Relative denominators use `max(reference_norm, 1e-12)`; a small denominator does not excuse a failed criterion. These are engineering feasibility gates, not proof that long trajectories are identical. Any failure stops the comparison and preserves outputs. Do not relax tolerances after observing results; diagnose with a separately versioned protocol.

Also verify causal-prefix invariance, identical target shift/EOT interpretation, precisely8,192 loss targets/update, single clipping after all microbatches, correct repeated-token embedding-gradient aggregation, and one native AdamW step per update. LR changes must enter the compiled graph as values, not cause an unintended constant schedule. No dropout, quantization, changed vocabulary, altered architecture, shorter sequence or changed effective batch is allowed.

## Stage B/C: three explicitly labeled runtime configurations

Run in this fixed order, starting each from identical source weights, moments and data offset:

1. Torch MPS FP32, same production arithmetic with autocast disabled.
2. MLX GPU FP32, new compiled core with FP32 master parameters and moments.
3. Torch MPS BF16 autocast, the actual frozen production precision policy.

The matched-precision comparison is1 versus2. Comparison2 versus3 measures whether the present FP32 MLX implementation is competitive with the actual production baseline, but is **not a matched-BF16 framework speedup claim**. Do not substitute MLX BF16 weight storage for the missing mixed-precision policy.

For each configuration, perform at least10 warm-up updates, with a five-minute cap. Record compile latency, warm-up targets, peak memory and exceptions separately. Then restore initial model/optimizer/cursor state in-place while retaining compiled kernels, and perform two untimed settling updates from the initial slice. The measured window starts on the next identical corpus position for all configurations. If an in-place restore invalidates the cache, record recompilation and repeat warm-up only within the original cap; otherwise mark the run incomplete.

Measure30 active minutes using B2×T512 and eight accumulated microbatches for every optimizer update. Stop at the last committed update within the window; never report the throughput of a partial update. Stop if the fixed2,048-update slice is exhausted before30minutes and mark that configuration's sustained test incomplete rather than cycling the data. Increasing this slice would require a new prospectively frozen benchmark version.

Every timing interval must include actual completion: `torch.mps.synchronize()` for Torch and `mx.eval(updated_state, loss, norm)` for MLX. Capture input acquisition, forward/backward, clipping and optimizer work. Report whole-window targets/second and separate contiguous five-minute bins, especially the last10minutes. Do not time lazy graph construction, isolated matmuls or inference and call it training throughput.

Run one identical fixed development loss check after each window and record its cost separately. Measure one atomic full-state save/readback and report it separately, then present a conservative periodic-checkpoint throughput estimate using the production ten-minute save interval. Keep sample-generation/evaluation overhead separate; the benchmark is not a complete replacement controller. Record thermal state, RSS, active/cache/driver memory, swap growth and system load through every window. If thermal/resource state makes the sequential runs incomparable, report that limitation and withhold a speedup conclusion; do not selectively rerun the slow configuration.

## Stage D: native full-state resume

For the MLX configuration, compare a fixed four-update uninterrupted branch against a branch saved after update2 and restored in a fresh process. Starting source, inputs, hyperparameters and compiled policy must match. Compare every parameter, native moment, group step/LR, corpus cursor and subsequent loss/norm trace. Require exact arrays and trace for this deterministic native-resume gate. If Metal nondeterminism prevents exactness, fail this gate and quantify the difference; a later tolerance policy needs a new protocol, not a retrospective waiver.

The save must use checksum-verified atomic publication with an accepted receipt and preserve the old good file on failure. Test truncated-file, changed-receipt and wrong-identity refusal with disposable copies. This establishes a native boundary save/restore only. It does not replace full campaign tests for token reservations, crash recovery, interrupted publication, resource cooldown, lease accounting and protected retention.

## Mixed precision and migration decision

The current core has **no production-comparable mixed-precision path**. That is an implementation gap, not evidence that MLX cannot support one. Before any BF16 MLX performance run, a new adapter must preserve FP32 master weights/moments and explicitly reproduce the observed Torch dtype policy: embedding/residual streams, normalization, projection operands/results, causal attention, GELU and loss reductions. First instrument the actual frozen Torch path; do not assume every operation runs BF16. Verify finite FP32 gradient accumulation and optimizer arithmetic. A blanket BF16 parameter cast is ineligible.

Such an adapter needs new tiny CPU tests where supported and new full-model GPU parity gates against Torch BF16, plus a fresh fixed benchmark version with30-minute sustained runs for each comparable configuration. No MLX BF16 numbers or speedup are projected from this FP32 experiment.

Even a passing full-model benchmark does not authorize production migration. Migration additionally requires a complete lineage-aware converter and controller, separate optimizer/campaign cursors, architecture and tokenizer identity in snapshots, schedule-boundary tests, loss/diagnostic transactional recovery, STOP/thermal handling, cumulative active/attempted budgets and checkpoint-publication recovery. Preserve the existing frozen campaigns; start any future MLX campaign under a new explicit identity and budget.

A suggested engineering preference is at least25% sustained improvement over the actual production baseline, with all correctness/recovery gates passed and no worse resource behavior. This threshold is a project choice, not a published guarantee. A smaller/no gain means retain Torch and focus on data and optimization. Any result is reported as execution feasibility only; conversation/tool quality remains independently evaluated.

## Primary implementation references

- [Apple MLX compiled training graphs](https://ml-explore.github.io/mlx/build/html/usage/compile.html): captured mutable state, first-call compilation and explicit timing synchronization.
- [Apple MLX lazy evaluation](https://ml-explore.github.io/mlx/build/html/usage/lazy_evaluation.html): evaluate updated state and loss together; scalar access can cause partial execution.
- [Apple MLX numerical precision](https://ml-explore.github.io/mlx/build/html/usage/precision.html): pin reduced-precision flags; nominal FP32 alone does not specify all backend arithmetic.
- [Pinned MLX0.32.4 optimizer implementation](https://raw.githubusercontent.com/ml-explore/mlx/v0.32.4/python/mlx/optimizers/optimizers.py): native state and explicit bias correction.

Before launch, re-check the installed version and these semantics against the frozen adapter. No package upgrade is part of this protocol.
