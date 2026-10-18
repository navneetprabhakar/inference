# Reviewed-data reference pilot runner

Creator: Navneet Prabhakar

## Delivered

`python -m slm.train` now executes finite reference pilots over verified token shards, mixtures or curricula. This closes the general-runner implementation gap identified in milestone thirty. It does not complete a real language pilot or approve a model.

- Preflight binds explicit config, complete recipe, random seed, tokenizer/data/release hashes, cumulative update/position ceilings and checkpoint cadence/retention. Every leaf is checked against the existing approved-train reader, then its content is re-encoded and compared with actual token/mask payloads. Rehashed arbitrary tokens or unapproved lineage fail before backend model construction/output creation. Resume preflight can read canonical tensor payloads to validate their shapes/content.
- Relative bindings resolve against the input specification directory; saved `spec.json` uses absolute host paths. Logical identity uses content fingerprints, not those locations. Identical relocated artifacts and backend changes can resume without changing the logical plan. Config, recipe, seed, data or relevant reference-code changes cannot silently continue an old run.
- Fresh runs initialize random FP32 weights. Resume preserves model/moments, recipe, accumulation tails and global/stage counters. The runner has no pretrained initialization, teacher transport, download, cloud launch, spending or fallback path.
- Before an update, the entire next accumulation group must fit the cumulative processed-position ceiling. A boundary stop does not truncate data or claim the requested token total. Finite exhaustion before the update target is incomplete; no wraparound occurs. Invocation-update and soft wall-time stops save at safe boundaries. A wall-time limit is not a hard spend/termination guarantee.
- Streaming durable update events remain separate from checkpoint authority. Managed wrappers bind the run plan and stage receipts around the unchanged trainer checkpoint schema. Verified checkpoints publish atomically before pointer updates; bounded retention keeps at least two and ignores unrelated directories/symlinks. Broken final checkpoints cannot produce a completed report, and failure reporting searches for a prior verified state.
- Source/tokenizer/code and resume-checkpoint changes are checked during execution. Unexpected failures discard uncheckpointed work rather than publishing possibly interrupted optimizer state. Prior attempt logs remain intact; orphaned events and pointers cannot override an explicitly verified checkpoint.
- Curricula preserve stage-local recipes and global AdamW state. At every stage exit, including the final stage, execution pauses for checkpoint-bound evaluation evidence unless the existing stage evaluator recomputes `screen_passed` from an accepted policy and bound suite/results/reviews. Prior passed receipts must be supplied and revalidated on resume. No scripted adapter is substituted by this runner, and a screen is never production acceptance.
- Reports separate preflight, initialization/restore, update, checkpoint and evaluation time; process/allocator memory methods are recorded. New-invocation positions differ from resumed logical totals. These tiny control timings are not sustained throughput or deployment latency measurements.

## Validation

- Final full local suite: **608 passed / 15 skipped**. Runner suite: **27 passed / 2 CUDA skips**. Actual NVIDIA validation of the new wrapper remains open; earlier underlying CUDA trainer evidence is not relabeled as wrapper validation.
- Exact same-backend fresh/resume state on local PyTorch CPU and MLX GPU; tiny PyTorch → MLX → PyTorch wrapper transfer checks exact imported values and retained logical identity. These do not waive the failed full-size trajectory criterion.
- Controls cover sample-only releases, wrong vocabulary/context, rehashed payload/lineage, changed run identity, rehashed invalid moments, atomic-group budget stops, finite exhaustion, soft stops, input mutation during restore, unrelated-path retention, bad/orphaned pointers/checkpoints, interrupted updates and final-checkpoint corruption/recovery.
- Mixture counts are compared with independently read batch sizes. One retained initial failure assumed six full 64-position batches (384 positions); the finite mixture actually contained 339 positions because of short tails. The test now checks the real stream, without changing data or update/tolerance rules. Preliminary successful suites are retained separately and are not substituted for the final source-frozen verification.
- Actual student decoding is used for the curriculum binding control. An explicitly synthetic zero-threshold policy permits checking advancement while random-model human grades stay false. That fixture is not the production policy, real human review or capability acceptance. Proposed screens still block, and the next stage requires its own bound evidence.

## Separate-process audit

Six CLI invocations compare a full run against an interrupted/resumed chain on each local backend. All use handcrafted synthetic source data and explicitly simulated review decisions, never real public or teacher examples.

| Backend | Per-chain logical end | Exact values compared |
| --- | --- | --- |
| PyTorch CPU | 3 updates, cursor 6, 90 processed / 42 supervised positions | 86,688 weight/moment values |
| MLX GPU | 3 updates, cursor 6, 90 processed / 42 supervised positions | 86,688 weight/moment values |

Across full and resumed controls, twelve optimizer updates execute 360 positions in total. Repeated control work is not unique training exposure and is not a 1M-token smoke run. The current private fixture/spec/attempts are under `data/pilot-runner-audit-v2/`.

Evidence: `reports/milestone-thirty-one-tests.xml`, runner/initial/preliminary XML, `reports/milestone-thirty-one-cli-audit.json`, updated readiness audit and summary. Runtime source is frozen for final tests/audit; all current source/artifact hashes are recorded.

## Usage

Inspect an eligible specification without constructing a backend model:

```sh
.venv/bin/python -m slm.train --spec /absolute/spec.json --preflight-only
```

Run or resume into a fresh attempt directory:

```sh
.venv/bin/python -m slm.train --spec /absolute/spec.json --output /absolute/attempt-one --backend mlx --device default --max-new-updates 100 --wall-seconds 3600
.venv/bin/python -m slm.train --spec /absolute/attempt-one/spec.json --output /absolute/attempt-two --backend mlx --device default --resume /absolute/verified-checkpoint
```

`--max-new-updates` is invocation-local; the specification's `limits` are cumulative. `--gates` optionally supplies stage IDs mapped to `suite`, `result`, `policy`, `suite_review`, `output_review`, `baseline` and `baseline_review` file paths (nullable baseline bindings). Run actual evaluation with the existing evaluation CLI against the exact checkpoint model, complete its applicable reviews, and supply those files before advancement. A modified pointer, update log or precomputed decision alone is insufficient.

The saved synthetic specification demonstrates the schema; do not relabel its simulated reviews as actual source approval. See [runner contract](reviewed-data-pilot-runner.md).

## Remaining work

- The driver inherits the bootstrap reader's in-memory reviewed-record inventory. It is not a solution for production-scale corpus admission/intake or a frozen production tokenizer. Those remain the next engineering/data-policy work.
- Actual source/account evidence, source/teacher/style/suite reviews and the portability-policy choice remain pending. The 1M/10M target-model language pilots, sustained performance and learned conversation/tool capability remain absent. Main GCP pretraining still needs a separate budget.
- No new real teacher generation, Platform API call, cloud job, actual source approval or real-data training occurred. Teacher reservations remain 17/20; CUDA validation allowances USD 7/10, settled charges unknown. The full project goal is incomplete.
