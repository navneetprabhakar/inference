# Bounded conversation SFT diagnostic — behavioral gate failed

Owner authorized preparation, a carefully reviewed subset, formatting/masking correctness checks, and a short SFT experiment with before/after responses and foundation regression checks. This is a separate diagnostic on our own 15,191,712-parameter checkpoint; it does not resume the failed foundation-recovery experiment.

## Result

**No reliable conversation improvement: 0/24 fully correct before and 0/24 after.** Responses remain repetitive story-like continuations. No output emitted an EOS end-of-turn token; all 24 after responses reached the 48-token limit. A response beginning with a relevant location but continuing into fabricated events was retained intact and failed the whole-response rubric.

| Metric | Before | Selected checkpoint |
|---|---:|---:|
| Development assistant NLL | 6.421895 | 5.871369 (8.6% lower) |
| Test assistant NLL | 5.897426 | 5.323741 (9.7% lower) |
| Foundation narrative NLL | 1.343035 | 1.380192 (2.8% higher) |
| Fully correct diagnostic responses | 0/24 | 0/24 |

Numerical correctness and loss-improvement gates passed; behavioral success gates failed. Training stopped at the fixed budget. No candidate was promoted, no extra epochs were run, and the original reference remains unchanged.

## Data, format and correctness

Frozen selection: 64 training plus 10 development plus 10 test conversations. All 84 were directly reviewed; two training records were held and not replaced. Final train: 62 conversations, 8,690 content tokens, 3,704 assistant-content tokens and 3,830 supervised targets including 126 EOS tokens per pass. Development/test contain 547/542 supervised targets. Whole task families remain split apart. All sequences fit the actual format within 256 next-token positions without truncation.

Format: one BOS, then each user message encoded as `User: text\nAssistant:`, followed by separately encoded assistant content and EOS. Segment encoding is the authoritative format at both training and inference. Loss covers assistant content and EOS only; user/role-label targets and padding are zero-masked. Exact prompt-prefix equality was checked for every assistant turn.

Native MLX BF16 with FP32 masters/moments was checked against independent Torch FP32 masked loss and all parameter gradients: absolute NLL difference 0.002218, relative gradient L2 error 0.01919, cosine 0.9998165. Changing only zero-masked targets or right-padding inputs changed masked loss by exactly zero. Tolerances were frozen before inference; no numerical tolerance was relaxed.

## Budget and checkpoints

Fresh SFT AdamW state; original parameters/architecture/tokenizer preserved. Batch 8, max 3 passes/24 updates, LR 5e-5 with two-update warmup, norm clip 1. Hard training stops: nonfinite values, gradient norm above 100, foundation NLL >5% above baseline, development NLL >10% above baseline. The planned 45-minute clock and 2M-position ceiling include setup repairs.

Consumed: 24 updates, 11,490 supervised target exposures, 730,528 student positions across correctness, training and evaluations, 97.7 seconds on the original aggregate clock. Peak reported MLX memory 1.76 GiB. No teacher calls or downloads.

Epoch 2 was selected solely by development NLL among checkpoints within the foundation-regression limit: 16 retained SFT updates and 7,660 retained SFT target exposures. Epoch 3's 8 updates/3,830 exposures remain charged but are not selected. Test NLL and final responses did not select the checkpoint.

Research checkpoint: `attempt-3/epoch-2.pt`. Original source: `restart/foundation-resolution-v1/B/checkpoint.pt`, SHA256 `bf45241501cee600bd618677dc1a3ae666e6f50d9c628e29e7326ee9c87d338d`. Child checkpoints include fresh optimizer state, own weights, RNG state and separate foundation/SFT provenance. No weights are pushed to Git.

## Setup repairs and evidence

Two setup defects stopped before any inference positions or updates: missing upstream import path, then the wrong adapter return type. Both failed attempts and their stops are preserved. Attempt 3 corrected those dependencies; it reused the original clock and aggregate work/training caps. This was an infrastructure repair, not a retry of a failed numerical or scientific gate. See `attempt-2/repair-receipt.json` and `attempt-3/repair-receipt.json`.

Detailed local response evidence: `attempt-3/private/before-responses.json`, `attempt-3/private/after-responses.json`, `attempt-3/private/response-assessment.json`. Dataset/selection/review files remain private. Public receipts include data counts, numerical checks, epoch history, hashes and aggregate decisions.

## Interpretation

The update moved the model toward demonstration tokens but did not produce reliable instruction-following or learned stopping. Three passes over 62 conversations are too small to establish the limits of SFT or the under-100M objective. These results do not justify scaling this schedule automatically. Further work requires a separately scoped decision about foundational language quality and a focused format-learning diagnostic; this run is closed.

`runner.py` is the reusable public implementation with probe inputs externalized. Exact executed source snapshots contain private probe text and stay local; `source-manifest.json` records their hashes. No historical source snapshot was edited after execution.
