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

The pilot completed exactly 100M tokens in 11h22m. Local evaluation is complete: see [the full report and actual generations](reports/evaluation-v1/REPORT.md). Loss improved on held-out text, but conversation, grounding, and tool probes fail. A bounded extension to 300M total is recommended as an experiment; no additional training has started. Cloud/API spend is zero.
