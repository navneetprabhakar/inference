# English conversation and tool calling from scratch

Updated 31 October 2026. This repository contains the restarted, laptop-first project: a 97,536,768-parameter English language model initialized with random weights, a fresh tokenizer, native MLX training, and offline tool-call evaluation. It is an experimental model, not a production assistant.

## Current state

**All training and the repetition-penalty evaluation are complete and stopped for review. No further training is authorized. Cloud and paid API spending: USD0.** Electricity and developer time have not been costed.

- Hardware: Apple M4 MacBook Air, 24GB unified memory.
- Model: 12 layers, width 768, 16,384-token byte-level BPE vocabulary, 512-token context; FP32 master weights and BF16 compute.
- Pretraining: 100M-token pilot completed; separate continuation reached 200M total and stopped. No 300M run.
- Revised V2 SFT: two 5M-input-slot arms on the 100M base completed (LR 1e-5 and 3e-5). The two planned 200M-base arms did not run.
- V3 repair: two 2M-input-slot arms completed from the 100M + 5M SFT LR 3e-5 checkpoint. Development selection chose **repair-lr3-2m**.
- Penalty sweep: 1.2, 1.3, 1.4 and 1.5 evaluated on the same 550 development cases. Keep 1.2 under the predefined regression gates; stronger global penalties damage tool chains.

## Measured results

V3 test release: 1,000 cases, selected model and two references on the same cases. Selection used development data only. This test set has now been inspected and must not be described as fresh for future tuning.

| Metric | Starting LR 3e-5 reference | Selected V3 repair |
|---|---:|---:|
| Single-tool full success | 14/200 | 122/200 |
| Tool-chain full success | 0/150 | 103/150 |
| Result-only exact answer | 99/150 | 135/150 |
| Grounded exact answer | 9/100 | 70/100 |
| Clarification accepted reference | 0/150 | 150/150 |
| Clarification canonical exact | 0/150 | 71/150 |
| Error canonical answer | 0/100 | 100/100 |
| No-tool canonical answer | 0/50 | 50/50 |
| Chat mean repeated four-gram fraction | 9.81% | 9.82% |
| Chat EOS termination | 83% | 79% |
| FineWeb perplexity | 59.71 | 57.38 |
| TinyStories perplexity | 6.92 | 6.39 |

Tool cases use synthetic, template-correlated offline fixtures. These numbers do not establish production tool reliability or broad English competence. Chat quality is not human-certified. Canonical and accepted-reference clarification scores measure different things.

| Development penalty | Chat repetition | Single-tool success | Chain success |
|---|---:|---:|---:|
| 1.2 | 9.45% | 56% | 74.67% |
| 1.3 | 2.06% | 55% | 72% |
| 1.4 | 0.39% | 55% | 69.33% |
| 1.5 | 0.01% | 54% | 48% |

Reducing repetition alone does not establish coherence. Some prompts request repetition; future scoring must distinguish legitimate repetition from loops.

## Documentation and evidence

- [Current plan and constraints](PLAN.md)
- [Local operation, setup and recovery](LOCAL_RUN.md)
- [Completed pretraining continuation](CONTINUATION_RUN.md)
- [Architecture, data and evaluation](docs/ARCHITECTURE.md)
- [Experiment history and artifact map](docs/EXPERIMENTS.md)
- [V3 comparison and actual outputs](reports/sft-v3/experiment/REPORT.html)
- [Completed penalty comparison and actual outputs](reports/sft-v3/penalty-sweep-v1/REPORT.html)
- [V3 dataset readiness](reports/sft-v3/READINESS.html)

Top-level documents and docs/ describe the current project. Dated reports and configs are immutable experiment evidence, including failed or superseded approaches; their launch-time status fields are not live authorization.

## Setup and verification

Use Python 3.14 on Apple Silicon with Metal support:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Tests exercise small models and fixtures; they do not launch a training campaign. Existing measurements used `../inference-archive-20261029/.venv/bin/python` as a dependency environment only. Archived trainer code and model weights were not inherited.

Git contains code, configs and reports. Raw data, token arrays, checkpoints and runtime state are ignored and remain local. A clone alone cannot reproduce the reported generations without the matching local assets and hashes. See [the runbook](LOCAL_RUN.md) before invoking any preparation or training script.

## Restart boundary

The previous project is preserved on `codex/archive-before-scratch-20261029` at `309c9accdaf2bad074e16fe702e313049abc86f7`. Its ignored files remain in the sibling `inference-archive-20261029`; relocation evidence is in `reports/archive.json`. Historical reports are retained for provenance, not carried forward as current capabilities. No archive deletion or Git history rewrite is required.
