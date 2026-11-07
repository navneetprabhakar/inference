# Sequential accumulation: prospective two-update fit experiment

Status: root-review proposal only. This is a distinct scheduling experiment, not a retry or continuation of the exhausted whole-graph benchmark. No runnable activation/controller is delivered here. The new tiny CPU core is verified; full-model/GPU feasibility is unverified.

## Fixed work and evidence

Use the same verified own124,439,808-parameter foundation endpoint and unchanged tokenizer,FP32 master weights/moments,AdamW groups/betas/epsilon/decay,LR6e-5,B2×T512×8,sourceoffset99,999,744. Root-approved input manifest must pin all prior source/neutral and Torch-reference receipts and rehash actual artifacts before load. Do not load another model or change architecture, vocabulary, precision, batch, clipping or targets.

At most **two sequential MLX updates,16,384 attempted targets,600seconds foreground wall including loading/compilation/comparison/teardown**, zero retries. No warmup beyond these two charged updates; timings are first-call/second-call observations, not sustained throughput. Each update reserves8,192targets durably before its first microbatch; a kill/guardfailure leaves the full reservation nonrefundable and no successful commit. Report per-microbatch timings and graph materialization, one optimizer call, actual cursor and complete resource trace. After update2, compare every weight/moment and traces to the hash-verified existing Torch CPU reference using unchanged old prospective tolerances. Do not claim MLX full-model exact resume: this short experiment does not run it.

A separate new output directory must be root-reviewed. Reuse prior neutral/reference read-only to avoid extra multi-GB copies; do not delete or rewrite prior evidence. At most64MiB new logs/metadata, no new full checkpoint or model weights. Keep at least20GiB free disk. Explicitly report old retained bytes and new bytes; new source conversion, checkpoint publication or expansion of output requires separate approval. Compare arrays in bounded chunks; release mmap/NumPy sources when no longer needed and do not hold duplicate native model states for convenience.

## Execution and guard policy

Reuse owned-child foreground watchdog/tickets, shared `runs/mps.lock`, global/foundation/ablation/priorbenchmark/newrun STOPs, mandatory AC and thermal monitoring. No concurrent intake/packing/training during the probe. Deadline includes metadata verification and bounded child termination/reap.90second heartbeat watchdog remains; the new core calls its boundary after each evaluated microbatch. Missing or timed-out mandatory telemetry fails; do not convert another monitor failure into permission to keep training.

Before creating GPU model state, install a fixed **1GiB cache limit** and **12GiB memory guideline**, recording prior settings. This is not an assertion that MLX prevents larger allocations. After initial synchronized load, record active/peak/cache/RSS and check before training. Reset peak only once before model construction; never reset between microbatches/updates. Maintain monotonically increasing reported phase peak.

At each synchronized microbatch boundary, before optimizer, and after optimizer:

1. Read and persist active/peak/cache before cleanup. Reject active or peak>=12GiB immediately, even if current active is tiny. Missing/nonfinite mandatory metrics fail.
2. Apply the **same fixed cache-clear operation at every boundary**, outside compilation, and record elapsed cleanup and post-clear retained cache. Require post-clear cache<=1GiB; do not selectively clear based on favorable performance. Report raw cache separately so cleanup cannot conceal transient retention. All cleanup time is included in fit timings. Independent allocator peak retains transient active allocations.
3. Sample process-group RSS; reject above18GiB at any boundary in this small probe. Parent independently checks RSS/swap/thermal at most every30seconds and before/after process launch. Swap growth>1GiB, serious thermal, missing telemetry, STOP, loss of AC or diskfloor failure stops. Post-boundary checks cannot guarantee no transient OS overshoot during a single kernel; report this limitation.
4. Only after both final update synchronization and all checks may the outer worker commit. Guardfailure poisons the core, prevents snapshots/continued steps and preserves previous accepted on-disk state. An after-optimizer failure may have changed RAM; its unchanged cursor must not be mistaken for rollback.

`check_memory` provides pure finite/threshold checking; it does not gather telemetry, clear cache, enforce deadlines or persist evidence. These remain explicit responsibilities of the future root-reviewed thin fit worker. It rejects high peak even with low active. No GPU worker has been authored or run as part of this CPU preparation.

Apple describes `set_memory_limit` as a guideline and `set_cache_limit` reclamation on the next allocation. Hence the explicit measurements, deterministic cleanup and abort rules above are essential; neither setter establishes a hard physical ceiling. [Memory limit](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.set_memory_limit.html), [cache limit](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.set_cache_limit.html).

## Pass boundary and next decision

Both updates must complete within resources, satisfy all original numerical tolerances and retain exact target/optimizer accounting. Otherwise the fit test is incomplete/failed with evidence retained, not automatically retried. Passing means only two-update FP32 fit/parity. It does not authorize production migration, a larger model, a speedup claim or long-running training. Sustained timing and full-model native fresh-process resume would require a later explicit reviewed allocation.
