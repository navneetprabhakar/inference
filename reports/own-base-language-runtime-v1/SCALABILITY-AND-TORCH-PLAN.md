# Scalable schedule helpers and minimal Torch continuation

CPU preparation only. No real corpus was packed, admitted or trained. Existing frozen trainers, benchmark files and protected checkpoints remain unchanged.

## Measured helper correction

The first helper recomputed source token totals per row, copied a growing exposure interval map per update, and replayed every prior update during resume. Those costs were unsuitable for a substantive run. The original helper is retained as `data-helper-before-scalability.py`; before/after receipts and a reproducible synthetic profile are adjacent.

The revised helper caches capacities and one ordered document index per source/pass. Checkpoint state now contains only per-source pass/offset/target/unique/repeat counters. Exact unique exposure comes from the complement of complete-pass target coverage: each pass omits its first input token plus its declared final incomplete-row tail, at most one row length in total. Intersecting these small omissions across completed passes yields exact new/repeated source-document-position counts. It does not claim semantic novelty or deduplication across document IDs/sources. Resume derives source quotas from cycle arithmetic, not update replay.

Synthetic170,000-document, three-pass profile (257tokens/document; no model or real-corpus reads):

| Measurement | 512 layout | 1024 layout |
|---|---:|---:|
| Initialization |1.317s|1.411s|
| First20updates including initial ordering |0.476s|0.491s|
| Next1,000updates |0.102s|0.071s|
| Cold resume at12,000updates |1.387s|1.379s|
| Warm resume at12,000updates |0.000019s|0.000019s|
| Serialized cursor state |240bytes|240bytes|

The old512helper took1.646s for its first20updates and1.210s to replay those same20updates; state was already13,877bytes. The new cold-resume measurement covers98,304,000targets across multiple passes, and reports43,690,000unique versus54,614,000repeated positions. Profile peak RSS was395MB then485MB cumulatively in a process holding original plans and multiple helper instances; it is not isolated training memory. A real-plan import should avoid retaining redundant copies after freeze. Profiles establish metadata practicality, not training speed.

Nine tiny tests pass, including independent brute-force token-position sets across five seeds/three passes, compact-state reconstruction, atomic failure after one source row has already been proposed, both layouts, variable-length validation and tamper rejection. No Torch/MLX import occurs in helper or tests. Run `python3 verify_own_base_language_data.py`.

## Actual input prerequisites

- `data/language-mixture-v1/partial-candidate-manifest.json` is explicitly `partial_incomplete_not_admitted`. Its candidate SQLite, input/candidate verification, legacy custody and public-development custody receipts exist. They must be reconciled with the new source-specific quality/admission policy and exclusions before stream publication. Its older target allocations are not adopted as this experiment's budget.
- `data/cosmopedia-intake-v1/receipt.json` and `reports/cosmopedia-intake-v1/independent-inventory-verification.json` establish intake/inventory, not training admission. The new candidate projection protocol explicitly forbids packing/admission/split assignment; it preserves seed relations for a later split policy. Final complete candidate proof, semantic review, cross-pool family splits, legacy/public custody exclusions and independent packing verification remain required. Do not read a live candidate database as a completed artifact.
- `data/balanced-continuation-v1/manifest.json` belongs to an older corpus. It is not a substitute manifest for the current narrative/expository/broad-English experiment. Older OpenStax admission decisions likewise cannot certify Cosmopedia.
- No helper-generated synthetic profile record is usable as an admitted document. GPT2tokenizer identity, numeric EOT50256, uint16 byte layout, full text provenance and exact document ranges must come from real verified packing receipts.

## Minimal delivery sequence for substantive Torch fallback

1. **Admission/virtual stream adapter:** new `own_base_language_streams.py` reads only immutable admitted manifests, source indexes and token files. Require hash-bound candidate/quality/split/custody/independent-packing receipts, exact row counts, no excluded IDs, cross-source family split reconciliation, contiguous nonoverlapping document byte ranges, valid token IDs and terminal EOT. Map helper `(source,document,offset,count)` spans to memory-map slices and concatenate only each512/1024row. No whole-source recopying, downloads, repairs or inferred source quotas. Verify each file once per startup; fail if any receipt is incomplete or stale. Tiny fixtures validate that assembled inputs and shifted targets exactly match virtual document order, including EOT boundaries.
2. **New narrow control:** `own_base_language_control.py` retains Campaign's atomic accepted checkpoint, reservation and rollback semantics but uses newly reviewed finite target/active/calendar ceilings; the old100M/36h/7day ceilings stay frozen. Separate committed goal, attempted replay allowance, evaluation targets, per-source positions and unique/repeated exposures. All amounts remain unspecified until admitted yield, explicit pass policy and measured Torch throughput justify them. Preserve global/ancestor/run STOP, single GPU lock, resource guards, cumulative leases and measured save margin.
3. **One Torch trainer:** `own_base_language_continue.py` reuses selected-parent verification and frozen GPT2math. Load exact preserve-095 parent weights, complete optimizer moments/groups/steps and CPU/MPS RNG; initial optimizer step14,648. Save a step-zero checkpoint. Propose the next helper update, reserve its exact8,192targets, construct microbatches, accumulate target-normalized loss, clip once, step once, synchronize, then commit the returned cursor state. Checkpoint includes optimizer/RNG, compact source state, full parent/data/code identities and evaluation history. Uncommitted or rolled-back attempts are never refunded. No imported SFT optimizer-reset path.
4. **Evaluation:** consume frozen one-window-per-held-out-document manifests; one variable-length FP32forward avoids padding mistakes. Store per-document summed NLL/actualtargets, document mean, token mean and length-stratum/coverage output; preserve source-specific regression histories. Keep original web/context/raw-generation diagnostics as a distinct unchanged transfer series. Save evaluation state transactionally; reserve evaluation cost again if interrupted/replayed.
5. **Bounded CPU integration:** tiny Torch parent→continuation and interrupted save/resume equality, exact assembled token rows, optimizer/RNG/cursor equality, attempted-budget nonrefund, source exhaustion, admission tamper refusal and validation interruption. These are necessary new behavior tests, not a broad test-suite rerun. Only after those and data admission should root freeze a launch specification.

512 remains the measured fallback layout candidate;1024requires its own bounded workload/resource evidence before activation and never becomes an automatic fallback. Current MLX full-update experiment exceeded the intended peak envelope: its guard checked active allocations after update and merely logged peak, so neither resource fit nor production migration is established. No same-benchmark retry or MLX migration is proposed here.

The user's1Bmaximum does not decide final model size. This minimal path preserves the existing124Mcontrol. A larger own-random architecture needs a separately budgeted shape/training-memory/speed decision; it cannot inherit124Mmoments as a purported identical continuation. No training budget, source mixture or useful-model ETA is fabricated by this implementation plan.
