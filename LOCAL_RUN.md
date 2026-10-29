# Authorized local campaign — 29 October 2026

User authorized a sustained real-data laptop benchmark followed by a 100M-token pilot if feasible. Cloud and paid API spending remain zero.

## What runs

1. `scripts/run_local_campaign.py` starts a 30-minute benchmark using fresh random seed 42.
2. It checks every feasibility condition and verifies source files have not changed.
3. If all checks pass, it starts a separate fresh-random-weight pilot with seed 43 and exactly 100,000,000 target tokens. Benchmark weights are not reused.
4. If any check fails, it records the reason and does not launch the pilot. No automatic expansion or retraining is allowed.

Model: 97,536,768 parameters, 12 layers, width 768, 16K newly trained byte-level BPE vocabulary, 512-token context, 2 sequences per microbatch, 8 microbatches/update (8192 target tokens). FP32 master parameters and AdamW state, BF16 forward/backward, global gradient clipping at 1, 2M-token LR warmup, cosine decay. The last batch masks unused targets to stop at exactly 100M.

Data: 99,999,912 FineWeb training tokens and 29,999,898 TinyStories training tokens; sampling mix 80/20. Independent validation files contain 999,925 and 367,602 tokens respectively. Original raw data remains unchanged in the archive. The tokenizer uses only training documents. Exact text duplicates are removed, and documents are split by canonical URL or normalized text hash. Near-duplicate and benchmark contamination are not comprehensively resolved; losses are diagnostic, not benchmark capability claims.

## Gates and controls

- At least 30 active minutes and 25 logged intervals, continuously on AC with no power/critical-thermal pause.
- Last five intervals average at least 1400 tokens/sec and at least 60% of the first five intervals' average.
- MLX peak under 12GiB; peak process RSS under 18GiB; swap growth under 1GiB; free disk at least 15GiB.
- All losses/gradient norms finite; final validation loss improves from random initialization.
- Checkpoint every approximately five minutes; preserve the two most recent complete checkpoints. Weight and optimizer files are written to a temporary directory before atomic publication.
- On battery or critical macOS thermal state, checkpoint and pause; resume after AC/cooling. An interrupted benchmark does not authorize the pilot.
- Pilot stops after 100M target tokens or 24 active hours, whichever occurs first. A STOP file or SIGTERM requests a checkpoint and graceful exit.
- Local `caffeinate -i` prevents idle sleep while the campaign lives; it does not override lid closure, shutdown, or a disconnected power cable.

## Status and control

Live files (intentionally ignored by Git):

- `runs/local-campaign-v1/campaign.json`: overall campaign state and child PID.
- `runs/local-campaign-v1/benchmark/status.json`, `metrics.jsonl`, `result.json`.
- `runs/local-campaign-v1/pilot/status.json`, `metrics.jsonl`, `result.json` when launched.
- Each phase's `latest.json` points to its latest complete checkpoint.

To stop the active phase gracefully, create `STOP` inside that phase's run directory. An interrupted run is not automatically relaunched. Resume explicitly with the same data and script hashes:

```sh
../inference-archive-20261029/.venv/bin/python scripts/train_local.py --mode pilot --seed 43 --output runs/local-campaign-v1/pilot --resume
```

Remove a STOP file before resuming. Do not run a second campaign: both supervisor and trainer hold exclusive filesystem locks.

The preserved environment is used as a library interpreter only; all trainer code and tokenization are new. Reproducible dependency versions are in requirements.txt. Tests cover causality, finite gradients, sampler resume across an epoch, exact optimizer/checkpoint state continuation for fixed gradients, and the partially masked final batch. BF16 embedding-gradient accumulation is not bitwise deterministic across GPU executions.

This is a base-language training pilot. It does not yet implement conversation/tool SFT and is not a usable conversational model release.
