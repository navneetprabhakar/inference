# Research admission, actual tokenizer candidates and pilot preparation

Creator: Navneet Prabhakar

## Outcome

- A self-contained, checked **research-training v3** release now admits **2,113 train / 265 validation / 279 test** reference passages. **243 passages** are quarantined at whole-group level. Screening failure reasons: four attention flags, 34 low-English-score cases and 194 terminal-punctuation cases; group quarantine can exclude additional members. These are experimental policy assignments, not individual human verification or estimated defect rates.
- Actual train-only byte-BPE candidates reach **16,384** and **24,576** IDs on **2,113 records / 2,630,768 UTF-8 bytes**. The corresponding target architectures have **80,765,440** and **84,959,744** parameters.
- **16K is frozen only for this pilot**, retaining the planned smaller vocabulary head and 81M architecture. Nine handcrafted development slices do not select a production tokenizer, and reference prose does not supply dialogue/slang/tool/product breadth.
- Actual token preparation yields **599,379 prepared prediction positions**. The finite schedule contains **1,048,230 positions**, with **448,851 repeated exposures**, at most two passes, no implicit wraparound and no partial-batch truncation. These are distinct prepared positions, not unique words or semantic facts. Maximum per-family scheduled exposure is **4,617 positions**, below the 32,768 cap.

## Admission and runtime contract

[The research contract](research-admission.md) records the delegated source decision, source evidence, residual risks, exact snapshot bindings, complete signal/output coverage, derivative reconstruction and policy markers. The accepted policy was frozen before measuring its admission yield. Original source snapshots and heldouts are included as evidence; they are not tokenized as training text. The existing 42-row explicit conversation release remains separate.

Managed preflight enforces foundation-only local MLX/CPU execution, at most 1,048,576 cumulative positions / 2,048 updates / 100M parameters / two passes, a single research component and exact resume bindings. CUDA training, excessive positions/updates/model size/repetition and synthetic-scope relabeling are rejected. This does not authorize paid training, production corpus release or arbitrary low-level code use.

The source/quality decision is expert review under the actual delegation, with `human_attestation: false`. The ten context-development judgments are not an unbiased corpus audit. Language scores and lexical screens are uncalibrated; factual errors, bias, public biographical details and outdated claims can remain. No blanket correctness/privacy/SFW/legal guarantee is claimed.

## Prepared actual run

Private artifacts:

- `data/context-research-release-v1`: self-contained v3 research release, checked before yield.
- `data/context-research-tokenizers-v1`: complete 16K/24K candidates and comparison.
- `data/context-research-pilot-v2`: immutable token shards, finite mixture, pilot-only tokenizer freeze and checked run specification.
- `data/context-research-pilot-v2/evaluation-prefixes.json`: **32 distinct validation groups / 4,096 next-token targets**, frozen before student training. No test text is used in this metric.

The comparison is predeclared: same 128-target prefixes, initial versus final mean NLL in nats, paired group bootstrap (10,000 resamples, seed 20261019), mean improvement at least 0.1 nats/token and a positive lower 95% bound. This is a local prose-learning smoke criterion, not broad conversation/tool quality, full-corpus perplexity or accepted MLX/CUDA resumed-training quality.

Pilot spec: random canonical initialization, seed 20261019, 24 layers / width 512 / 16K vocabulary, context 1,024, one microbatch per update, reference FP32 dense embeddings, legacy loss, AdamW learning rate 0.001, 32,768-position warmup, clip 1, decay 0.1, checkpoint every 128 updates and retention two. The finite schedule can end below the numerical ceiling; actual counters must be reported. Free local filesystem space was about 96 GiB before launch preparation; no reservation or hard storage guarantee is inferred.

Commands after verification:

```sh
.venv/bin/python -m slm.train --spec data/context-research-pilot-v2/pilot.json --preflight-only
.venv/bin/python -m slm.train --spec data/context-research-pilot-v2/pilot.json --backend mlx --device default --output data/context-research-run-v1 --max-new-updates 2048 --wall-seconds 3600
```

A wall-bound stop is a terminal invocation with a saved checkpoint, not a failed observation or permission to restart from random weights. Resume through the checked checkpoint in a separately named attempt, retaining prior logs. Never relaunch solely because a tool observation timed out.

An earlier context-256/four-microbatch preparation is preserved in the explicitly named `*-context256.json` reports and private v1 data folder. It was superseded before any student initialization, aligning the actual run with the plan’s 1,024-token context. Its schedule and preflight hash are historical, not the run specification.

## Verification and state

- Full local suite: **730 passed / 15 hardware-dependent skips**. Earlier focused admission/review/runner check: **67 passed / two CUDA skips**; final full coverage additionally includes narrower parameter/repetition cap tests.
- Tests cover heldout exclusion, group quarantine, source/derivative reconstruction, resealed text/missing/extra/blocked rows, complete signal/window coverage, false human flags, cap escalation, CPU-only restrictions and actual tiny training/resume through the new reader. No new NVIDIA result is claimed.
- Data admission, both tokenizers, the complete schedule, evaluation-prefix freeze and actual-spec preflight ran successfully. Preparation records **zero public-data student updates**; a running or completed student attempt must be reported separately from this preparation snapshot.
- No teacher calls, Platform API calls or cloud jobs. Teacher reservations remain 17/20; conservative CUDA allowances USD 7/10, settled costs unknown. Full goal active/incomplete. Next is the actual bounded local run and measured heldout comparison, followed by broader data and staged capability work.
