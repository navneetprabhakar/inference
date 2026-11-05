# Astra foundation and feasibility

The random 124,439,808-parameter student passed decoder parity, single-batch learning and the bounded held-out pilot on the M4 Air. The pilot used 244 updates × 4,096 supervised positions with a 256-token training context. It ran for 835 seconds. Its checkpoints are diagnostic artifacts only.

| Diagnostic | Initialization | Unigram | After 999,424 targets |
|---|---:|---:|---:|
| Encyclopedia validation CE | 11.015 | 8.059 | 7.119 |
| Narrative validation CE | 10.948 | 6.183 | 4.162 |

Each loss uses a fixed 2,048-token sample per source. The broader manifest holds 43,069 encyclopedia and 43,410 story validation positions. The same prompt produced “A bridge is built to the other of the other of the other of the other of the other of the” at the end of the pilot. Conversation and tool accuracy require separate measurement.

## Evidence

- `foundation.json` records tokenizer checks, CPU/MPS errors, memorization, CPU resume and the confirmation fingerprint. The same operator authored the confirmation set during the disposable pilot and had access to its text. The trainer reads explicit training shards.
- `corpus.json` records split, counts, checksums, source limitations and sampled material. The local document manifest and article attribution index are in `data/feasibility-v1/`. Packing appends numeric EOT per document and allows training windows to cross that boundary.
- `pilot.json` records the exact config, results, output samples and retained checkpoint hashes. The average across the short pilot was 1,197 targets/s including evaluation and writes. The subsequent benchmark measured 1,018 end-to-end targets/s. See [the final run result](RESULT.md) for the budget decision, supervised diagnostic and stop reason.
- `runs/astra-foundation/`, `runs/astra-memorize-01/`, `runs/astra-pilot-01/` and `runs/astra-benchmark-01/` contain local telemetry or artifacts. Only sanitized results belong in Git.

## Reproduce

Use Python 3.12. Install dependencies with `uv pip install -r requirements-verify.txt`. Run `python tokenizer.py --fetch` once to provision the two pinned OpenAI files. The decoder parity checks instantiate random tiny reference and student models, copy tensors explicitly, and compare full logits, loss and all parameter gradients.

```sh
python verify_foundation.py cpu
python verify_foundation.py mps
python verify_resume.py
python verify_tools.py
python verify_dialogue.py
```

Training requires an exclusive MPS lock and a fresh run directory. The preparation command takes the archived `pilot-data-manifest.json` and a new output directory. Seeds, data policy, budgets and command entry points are in `prepare_data.py`, `train.py`, `pilot.py` and `benchmark.py`. Do not restart the old snapshot's jobs.
