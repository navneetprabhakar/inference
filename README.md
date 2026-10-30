> Current SFT status: v2 data and evaluation corrections are validated; the four-arm local campaign is authorized and launching. See [readiness report](reports/sft-v2/READINESS.html). Earlier v1 baseline artifacts are retained; its evaluator stopped on a now-fixed retention-scoring error.

# English conversation and tool calling from scratch

Random initialization. English text. Total model parameters below 1B. Laptop-first development on an Apple M4 MacBook Air, 24GB unified memory. No old model, tokenizer, trainer, or evaluation policy is inherited.

## Current state

The old project is preserved in Git branch `codex/archive-before-scratch-20261029`, commit `309c9accdaf2bad074e16fe702e313049abc86f7`, pushed to origin. All working files, including ignored data and checkpoints, were moved intact to `../inference-archive-20261029`. The earlier `../inference-history-20261021` archive remains intact. `reports/archive.json` records relocation verification. The archive branch stores versioned files; ignored payloads are local-only. Git history was not rewritten or pruned.

Fresh branch: `codex/english-tools-from-scratch`.

This branch contains a read-only local data inventory, bounded random-weight MLX benchmark, cost calculator, and a proposed pilot. A sustained local benchmark followed by a conditional 100M-token pilot is authorized; see [LOCAL_RUN.md](LOCAL_RUN.md) and the live files under runs/local-campaign-v1. No cloud resource or paid teacher API is used. Short synthetic benchmarks are throughput measurements, not language-quality results.

## Reproduce

Create a fresh Python 3.14 environment and install `requirements.txt`. Measurements in this session used the preserved environment's interpreter directly; no archived project code was imported.

```sh
python scripts/inventory_data.py --archive ../inference-archive-20261029 --output reports/local-data.json
python scripts/benchmark_mlx.py --hidden 512 --layers 8 --seconds 45 --output reports/benchmark-33m.json
python scripts/benchmark_mlx.py --hidden 768 --layers 12 --seconds 60 --output reports/benchmark-97m.json
python scripts/estimate_cost.py --parameters 150e6 --tokens 20e9 --runs 2
```

See [PLAN.md](PLAN.md) for the revised budget and sequence. Existing corpus counts are not approved training splits: identify duplicates and source lineage before reuse. Do not sum archived versions and derived datasets as independent data.

## 100M pilot outcome

The pilot completed exactly 100M tokens in 11h22m. Local evaluation is complete: see [the full report and actual generations](reports/evaluation-v1/REPORT.md). Loss improved on held-out text, but conversation, grounding, and tool probes fail. A bounded extension of another 200M tokens is authorized. See [the continuation protocol](CONTINUATION_RUN.md) for the fresh corpus, power guard, and evaluations at 200M and 300M total. Live status is in `runs/continuation-v1/campaign.json`. Cloud/API spend is zero.

## 200M review checkpoint

Training and evaluation completed at exactly 200M total tokens. The campaign has stopped for user review; no training beyond 200M is authorized. See [all 36 actual outputs and nine loss sets](reports/continuation-v1/200m/REPORT.md). Compared with 100M, fresh held-out web/Wikipedia/Pressbooks perplexity improved from 45.10/50.03/44.55 to 38.73/24.84/33.56, while unseen TinyStories worsened from 5.99 to 13.19. Mean greedy repeated-four-gram fraction increased from 0.636 to 0.846 on the same 12 prompts. Outputs remain unsuitable for conversation or tool calling. The evidence does not justify automatically continuing the same recipe to 300M.

## Bounded chat/tool SFT experiment

Authorized: four full-weight SFT copies (100M/200M bases × peak LR 1e-5/3e-5), each capped at 5M processed input slots including padding. This is approximately 2.07M non-padding input tokens and 776K supervised targets per arm, not 5M answer tokens. All arms share the exact exposure order. Baseline and SFT decoding sweeps use development cases only; final reports preserve actual held-out outputs and local fixture execution metrics. Chat coherence requires human review. Battery training remains enabled; no cloud or paid APIs.

Live state: `runs/sft-v1/campaign.json`; per-arm `status.json`. Final output: `reports/sft-v1/REPORT.md`. The supervisor exits for user review after four arms and evaluations; it never resumes pretraining. Frozen base checkpoints are checked unchanged. Details and exact data counts: `configs/sft_experiment.json`, `reports/sft-v1/data-manifest.json`, and `reports/sft-v1/data-verification.json`.

Run with the preserved environment: `python scripts/run_sft_experiment.py`. Resume an inspected interrupted campaign with `--resume`; code/data hashes must match. A root `runs/sft-v1/STOP` file stops training safely and blocks subsequent jobs. Evaluations already in progress may finish; no next job starts. SIGTERM to the supervisor terminates the child, allowing the trainer to checkpoint. Never remove a user STOP file without renewed authorization. Retain source data/checkpoints locally; Git excludes their large files.
