# Actual foundation pilot launch and frozen validation scorer

Creator: Navneet Prabhakar

Date: 19 October 2026

## Actual training attempt

The 80,765,440-parameter model is training from canonical random FP32 weights on the local Apple M4 MLX GPU. This is the first actual public-prose foundation pilot, separate from previous synthetic mechanics and preparation reports. Source commit at launch: `59e7c677f867ea473328500a140644130ebe90b2`. Logical plan: `2ba1fe964d06202f8b9bf8e016af3fc68917ac1d7b21203eb7b83abd8fbb06a7`.

The launch command is the actual context-1,024 specification from milestone thirty-nine:

```sh
.venv/bin/python -m slm.train --spec data/context-research-pilot-v2/pilot.json --backend mlx --device default --output data/context-research-run-v1 --max-new-updates 2048 --wall-seconds 3600
```

At the recorded observation, **256 updates / 262,144 prediction positions** had completed; checkpoint **256** was saved with its wrapper checksum verified. `reports/milestone-forty-launch.json` is a dated running snapshot, not a terminal result. The live execution handle is session 8649. Process observations and update events do not substitute for checked checkpoint state. Continue observing that handle; do not restart from random weights on a tool timeout.

The immutable schedule remains 1,048,230 positions, including 599,379 distinct prepared positions and 448,851 repeated exposures, across 1,025 batches with at most two passes. A normal finite-data completion reports `data_exhausted_before_target`: the 2,048-update number is a ceiling, not a requirement to repeat data until reaching it. A soft wall stop requires a separately named, checked resume attempt and retained prior logs.

Concurrent Java, Docker and desktop activity was observed. The user received resource guidance; no other process was stopped automatically. These running timings are not a controlled sustained-throughput benchmark. No cloud job, teacher call, API call, credit purchase or reset occurred.

## Frozen heldout scorer

`slm.eval.foundation_smoke` implements the comparison fixed before launch in the committed milestone-thirty-nine freeze receipt. It reconstructs the 32 canonical validation groups and their 128-target prefixes from the checked release, verifies the actual specification/tokenizer/recipe/seed, and rejects changed rows or prefixes even when a modified protocol is resealed. No test text is scored. The tracked receipt and its prelaunch Git history anchor the freeze; a locally editable receipt is not an independent trusted timestamp or a signature.

The command requires a terminal, single-attempt, canonical-random run with the complete finite schedule and at least one million processed positions. It verifies the full managed checkpoint, counters, source/data plan, event checksum and terminal report before scoring. It does not label a periodic checkpoint or a live run as final. If the run needs multiple resumed attempts, extend and test chain verification before using the scorer; this command currently rejects resumed attempts.

The initial model is reconstructed from the exact initialization seed when scoring. Its loss has **not** been observed yet; only the selection, seed and metric were frozen before launch. Initial and final weights use the same backend, embeddings, loss implementation, token arrays and masks. MLX and PyTorch CPU scoring are supported; this does not establish cross-backend resumed-training quality.

The metric is mean token NLL in nats. Every group contributes exactly 128 targets. Compare initial minus final group losses with 10,000 paired group-bootstrap resamples, NumPy seed 20261019 and the percentile 95% interval. The smoke criterion requires mean improvement of at least 0.1 nats/token and a strictly positive lower interval bound. Preserve negative results; never substitute training loss for this comparison.

After the actual finite run ends:

```sh
.venv/bin/python -m slm.eval.foundation_smoke \
  --spec data/context-research-pilot-v2/pilot.json \
  --protocol data/context-research-pilot-v2/evaluation-prefixes.json \
  --freeze reports/milestone-thirty-nine-evaluation-freeze.json \
  --run data/context-research-run-v1 \
  --backend mlx \
  --output reports/milestone-forty-heldout-smoke.json
```

## Verification and next action

- Focused scorer tests: **18 passed**, including deterministic canonical selection, split isolation, minimum coverage, tampered receipts/specification/rows/tokens, direct-logit NLL checks on local MLX and PyTorch, paired-bootstrap reproducibility and retained failing criteria. These tests use synthetic data and do not measure the actual student's quality.
- The previous full-suite result remains 730 passed / 15 hardware-dependent skips. It predates this scorer; the full suite has not been rerun concurrently with the active training job.
- Actual frozen-protocol verification passed: the checked release reconstructs all 32 groups / 4,096 targets with the unchanged pilot plan identity. Receipt: `reports/milestone-forty-protocol-verification.json`. No model was scored by that verification.
- Continue the exact live attempt, then inspect its terminal report and checkpoint, run the frozen comparison and record actual timings/memory/checkpoint overhead with concurrency limitations. A source-bound prose smoke pass cannot establish professional/casual/caveman conversation, content controls, tool correctness, MCP task completion, broad English quality or production readiness.
- Broader train-only data/tokenizer work, the 10M pilot, staged cloud training, conversation/style/tool learning, accepted resumed-backend quality and later ESCI remain required. Teacher transport stays CLI-only, reservations 17/20; CUDA allowances remain USD 7/10 with settled costs unknown. The full project goal remains active and incomplete.
