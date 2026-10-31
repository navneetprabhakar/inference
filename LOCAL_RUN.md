# Local operation — 31 October 2026

## Current state

Training is stopped. V3 repair and the penalty sweep both finished awaiting review. No automatic resume, further pretraining or paid compute is authorized. Keep existing STOP files. Continue on battery if a future run is authorized; charger removal is not a pause condition. Critical thermal and memory/disk limits remain applicable.

See README.md for environment setup. The measured environment is `../inference-archive-20261029/.venv/bin/python`; use that executable path directly rather than resolving its symlink. Requirements are pinned in requirements.txt. Metal-backed tests require compatible Apple hardware.

## Inspect without starting work

- `runs/sft-v3/campaign.json`: completed repair campaign; old child PID fields may remain after exit.
- `runs/sft-v3/penalty-sweep-v1/status.json`: completed sweep, model unchanged, recommendation 1.2.
- `reports/sft-v3/experiment/selection.json`: development-only checkpoint selection.
- `reports/sft-v3/penalty-sweep-v1/comparison.json`: completed penalty metrics and guards.
- `runs/continuation-v1/campaign.json`: stopped at 200M total.

Check process existence as well as status files; a recorded PID alone is not evidence of a running job. Final completed_penalties and report files take precedence over the last periodically written cases_completed counter.

## Assets and checkpoint

Selected local checkpoint: `runs/sft-v3/repair-lr3/milestones/2000000`.

Model SHA-256: `93bb235b29c8bdff5efe4e14bac223b92b5bc70fecc3023a22d8ed2d9b6fd781`.

Frozen V3 manifest SHA-256: `7f05e6cfe9bc5b24b8380c10303fe52e02afd2ef5bd2f568914b400eef1b0c0e`.

Data, runtime state and checkpoints are ignored by Git. Preserve them locally; Git push is not a model/data backup. The manifests, receipts, config and code hashes document the dependencies needed to recreate a run. Checkpoints and datasets are not bundled as a downloadable release.

## Resource controls

Run GPU workloads sequentially. The initial overlap attempt and uncapped MLX buffer cache caused swap growth. The fix caps MLX cache at 256MiB and observes active plus cache allocations. V3 inference ended around 0.43GiB allocator usage; training ended around 2.25GiB. Neither is total system memory.

Retain 12GiB MLX allocation/peak limits, 1GiB additional swap per session, at least 15GiB free disk and critical-thermal protection. System sleep and lid closure can suspend execution; caffeinate does not guarantee execution through lid closure.

## Recovery only after renewed authorization

Inspect the failed stage, checkpoint, logs, code/data pins and resource state before resuming. Never delete a STOP file merely because a script suggests resumption. Do not bypass hash mismatches. Preparation scripts can overwrite generated datasets; isolate a new version before any rebuild.

Current implementations are `run_sft_v3.py`, `train_sft_v3.py`, `evaluate_sft_v3.py` and `evaluate_repetition_v3.py` under scripts/. Older campaign and overlap scripts are retained as experiment history and must not be used as the default entry point. A launch-time authorized flag in a config does not grant continuing permission.

Run `python -m unittest discover -s tests -v` in the prepared environment for regression checks. Tiny test-model gradient updates are verification, not additional checkpoint training. Do not launch campaign drivers as a smoke test.
