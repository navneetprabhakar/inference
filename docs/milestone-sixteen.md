# Curriculum transitions and version-3 training state

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

A finite curriculum now switches between reviewed token mixtures, including foundation → assistant-masked SFT, without resetting model weights, AdamW moments or global bias-correction steps. Stages have independent processed-token learning-rate clocks and accumulation sizes. Checkpoints retain a hash-bound plan and independently recomputable per-stage progress.

Local suite: **286 passed / 9 unavailable-CUDA skips**. A short full **80,765,440-parameter** MLX own-resume probe passes. This completes reference curriculum mechanics; it does not establish language quality, production data approval, or accepted full-size cross-backend training trajectories.

## Execution contract

- Pin the entire ordered plan before training: unique stage IDs, mixture manifest hashes, complete schedules and base recipe. Runtime bindings supply paths separately. Reordering/appending stages or changing a recipe creates a different plan identity and cannot silently resume an old run.
- Stages consume complete finite mixtures. A final short accumulation group is consumed within its stage; no group spans objectives or stages, and no batch wraps implicitly.
- Preserve global AdamW step and FP32 first/second moments. Base betas, epsilon, decay, clipping, loss implementation and embedding implementation remain fixed across the plan. Stage schedules may change peak learning rate, warmup positions, accumulation steps, cooldown positions and final learning-rate fraction.
- Learning rate is evaluated after each update using **that stage's processed prediction positions**. It is peak rate × linear warmup fraction × linear cooldown fraction. Warmup/cooldown must fit without overlap; zero cooldown requires final fraction one. The final update reaches the declared final fraction. SFT compute clocks include masked input positions, while supervised positions remain a separate counter.
- The next `update()` after a completed stage starts the next stage. This mechanism does not evaluate capability exit gates. Callers must save/evaluate boundary checkpoints before deciding to continue real training. Reviewed data and measured quality gates remain required; automatic plan completion is not model acceptance.
- Optional replay is explicit: repeat a mixture under a new stage ID. A **global processed-position family cap** sums exposure across all stages, independent of their supervision masks. Shared parent-family mappings must agree. Record content fingerprints occurring in multiple stages are reported; cross-objective unique-token or semantic-uniqueness accounting is not claimed.
- Upfront bounds: 16 stages, one million combined scheduled batches, one million lineage record occurrences and 128 MiB combined lineage inputs. Existing per-mixture limits also apply. Repeated artifacts count again against these limits because the reader opens each stage separately. This remains a bounded reference implementation.

## Checkpoint compatibility and integrity

`CurriculumTrainer` emits training state **version 3** using the existing portable model/optimizer files and atomic update-boundary save. It records the plan hash, next stage, completed-stage count, local cursor/update/processed/supervised counters for every stage, global updates and the stage-specific accumulation policy. Resume recomputes these from verified artifacts and rejects inconsistent counters, altered plans, unsupported policies or incomplete optimizer state.

Standard `Trainer` continues to read/write its historical version-1/version-2 contracts. It refuses curriculum data and version-3 schedules; use `CurriculumTrainer`. There is no silent conversion of existing single-dataset checkpoints or extension of a completed curriculum. Plan a full run before starting it; checkpoint migration/branching remains separate future work.

The base trainer now exposes internal hooks for update extent, learning rate, result metadata and checkpoint validation. Progress is committed only after numerical work and result-receipt checks succeed. The base trainer still imports without the optional tokenizer dependency; curriculum readers require the tokenizer extra.

## Evidence

| Check | Evidence and limitation |
| --- | --- |
| Stage semantics | Foundation and SFT objectives, different accumulation sizes, final tails, stage-local warmup and cooldown, exact counts, exhaustion and no implicit reset. Analytic rate checks use independent formulas. |
| Manual optimizer control | Curriculum parameters and both moment slots match a separate stage-by-stage PyTorch run after every update, with its moments/global step explicitly retained. |
| Own-resume | Exact tested MLX and CPU continuations from mid-stage, exact boundary and next-stage checkpoints. Dense embedding is explicit for MLX exactness controls; native CPU resume is also tested. |
| Cross-backend | Tiny MLX → CPU checkpoint import, two continuation updates, CPU → MLX return and continuation pass existing bounds. This is local CPU evidence, not actual NVIDIA validation. |
| Failure recovery | Second-microbatch failure on entering SFT and result-receipt failure leave prior weights, moments and counters unchanged. Retry matches resumed state exactly on each tested backend. Interrupted plan publication leaves no partial output. |
| Rejection checks | Rehashed state counters/receipts, boolean counter substitution, removed optimizer, recipe mismatch, changed plan, stage IDs, invalid schedules, wrong mixture hash, unsupported transition/clock, raw audit input, family cap, report totals and live component mutation. |
| Artifact portability | Rebuild and relocated paths preserve plan identity; CLI resolves relative paths against configuration location. |
| CUDA | One new tiny CPU/CUDA curriculum test exists but skips locally. All nine local skips require unavailable CUDA. No actual CUDA curriculum execution is claimed. |

## Full-model local probe

`scripts/audit-curriculum.py` prepares temporary synthetic mock-reviewed sources, a synthetic exact-size tokenizer and two very small verified mixtures. The tokenizer is not a production candidate and no real source review is modified. It starts random full-model weights and explicitly uses `dense-onehot-v1`, legacy loss and epsilon 1e-8. The base accumulation size is three; stage schedules specify three for foundation and two for SFT, with no warmup/cooldown in this bounded probe.

- Foundation: two microbatches / **64 processed and supervised positions**, one short-tail update at learning rate 3e-4.
- Save/resume at the stage boundary: all **242,296,320 weight/moment values** import exactly with global update one preserved.
- SFT: two microbatches / **36 processed, 16 supervised positions**, one update at learning rate 1e-4. Uninterrupted and resumed branches have identical metrics and all state values.
- Logical totals: **two updates, four microbatches, 100 processed / 80 supervised positions**. Actual executed work across branches: **three updates / 136 processed positions**.
- Temporary checkpoint: **969,245,741 bytes**. Process peak RSS 5,092,900,864 bytes; MLX allocator peak 3,759,260,724 bytes, while holding two trainer states. Unified-memory figures overlap and must not be added. No sustained throughput or single-trainer memory claim follows.

Evidence: `reports/milestone-sixteen-full-curriculum.json`, source/plan/checkpoint hashes, exact-state digests and local test XML. Fixtures/checkpoints were removed after the probe. The earlier repeated-token trajectory failures remain failed; this milestone neither changes bounds nor selects dense as production. Actual dense CUDA validation remains open.

## Usage and remaining work

Create configuration JSON with `stages`, optional full base `recipe`, and `family_processed_cap`. Each stage contains `id`, `dataset_hash`, `path`, `components` (component-ID/path mapping) and a complete `schedule`:

```json
{"lr":0.0003,"warmup_tokens":4096,"cooldown_tokens":0,"final_lr_fraction":1,"accumulation_steps":16}
```

Budgets must fit the actual finite mixtures. Build with:

```sh
python -m slm.data.curriculum --config CURRICULUM.json --tokenizer TOKENIZER --output PLAN
```

Open `CurriculumBatches(PLAN, stage_bindings, TOKENIZER, expected_fingerprint=HASH)`. Import `CurriculumTrainer` from `slm.common.curriculum`, construct with model/config and the reader, and use `update`, `save`, and `CurriculumTrainer.resume`. Read `batches.progress(trainer.cursor)` for the recomputed stage receipt. Do not use the ordinary Trainer with curriculum data.

Next work: language/constraint evaluation and stage acceptance reporting, current source review and English/privacy/quality gates, production tokenizer selection and bounded real language pilots. Structured tool SFT, executable MCP runtime, reduced precision and ESCI remain open. No teacher generation, Platform API, new cloud job or paid run occurred. CUDA planning allowances remain USD 5 of USD 10; settled charges remain unknown.
