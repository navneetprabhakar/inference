# Numerical repeatability repair

**Validated a deterministic embedding-backward path for this bounded model/input test.** Historical source and stopped experiment remain unchanged. This repair does not establish model capability or certify arbitrary workloads.

- Isolated repeated-token lookup reproduced native gradient variation. Maximum difference from the FP32 accumulation reference, rounded to BF16, was 0.375 in the native probe.
- Custom VJP retains forward indexing but accumulates lookup gradients in FP32 on CPU before casting to the embedding compute dtype. Tied output projection continues to use the same weight through the original linear path.
- Repaired isolated gradients repeated exactly and matched the reference exactly in three trials. Actual combined model gradients also repeated exactly.
- Independent PyTorch/MLX numerical checks passed the original tolerances. Canonical parameter ordering matches post-update ordering before the first step, stabilizing reduction order across reloads.
- Three uninterrupted optimizer steps matched one step + save/reload + two steps **bitwise**, including weights, moments, RNG and optimizer metadata. Both endpoint checkpoints are preserved locally. Exact save/reload passed separately.
- Fresh optimizer moments/counters started at zero and reached step 2 with the prescribed warmup learning rate.

## Harness correction and accounting

The initial validation reached its final fresh-optimizer assertion after eight updates, then failed because literal `8e-6` differs from the computed Python float `2e-5*2/5` (`8.000000000000001e-06`). This was a test expectation defect, not a changed learning-rate schedule or relaxed equality threshold.

The failed validation, STOP and ledger are preserved. A separately recorded correction reran only the fresh check for two updates, compared against the specified expression, and saved state before asserting. Its ledger carries the preceding eight updates: **ten aggregate engineering updates**, below the twelve-update cap. This correction was explicitly announced before execution; no trajectory tolerance changed. The earlier scope's stop instruction was narrowed for this diagnosed harness-only defect, under the user's continuing authorization; this was not a failed model gate retry.

See [result](result.json), [isolated probe](probe.json), [full-model repeat](model-repeat.json), [numerical comparison](numerical-preflight.json), [correction](fresh-check/correction.json), [aggregate engineering ledger](fresh-check/ledger.json).

The [repaired continuation](../teacher-bridge-execution-v2/PLAN.md) carries the original study ledger and frozen data forward, with this separately charged engineering overhead. No engineering snapshot seeds the main study. CPU/GPU transfer performance at larger batch/context sizes is unmeasured; probe timings are not throughput benchmarks.
