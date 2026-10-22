# Fresh English foundation proposal — approval pending

> Model size and tokenizer remain unapproved. The [latest FineWeb salvage](fineweb-salvage-reviewed-v1/REPORT.md) leaves 72,116 training documents / 15,317,518 content tokens, including only 51 individually reviewed FineWeb records / 22,245 tokens. Bulk FineWeb filtering failed fresh validation. Earlier volume estimates are superseded. The 17.3M model recommendation is withdrawn; its tensor-shape calculation is retained only as a design candidate.

Owner: Navneet Prabhakar (Forge). 21 October 2026, Asia/Kolkata.

## Decision

Use the current local corpus for a **bounded research feasibility test**, not a claim that we have enough data for a broadly competent English foundation. The previously proposed **17,308,032-parameter decoder** is an unapproved candidate, not a current recommendation. No initialization, training, checkpoint inference, cloud access or data acquisition is authorized by this proposal.

The currently admitted data supports only short narrative language experiments; expository FineWeb data is quarantined. It cannot establish broad conversational pragmatics, reliable factual knowledge, varied adult writing or robust reasoning. The acceptance gate is deliberately capable of rejecting this design. Repeated exposure does not close missing-domain gaps.

## Measured facts

- Local hardware: M4 MacBook Air, 10 CPU cores, 10 GPU cores, 24 GiB unified memory. No new throughput measurement was taken; no old training timing or capability score informs this design.
- The selected original-snapshot census and fresh audit live in `data-census.json` and `sample-language-audit.json`. Source data and provenance are retained under `/Users/navneetprabhakar/Documents/git/image/inference-history-20261021/data/`.
- The current admitted pool is 80,038 documents / 16,997,435 content tokens under the preserved 16,384-vocabulary BPE; training alone is 72,116 / 15,317,518. This includes only 51 individually reviewed FineWeb documents. Counts are exact for the manifest, with sample-based semantic admission rather than individual certification. Smaller-vocabulary token counts will differ.
- Local snapshots are sparse, selected ranges/samples; upstream corpus size is irrelevant. Alternate releases and token shards are transformations of these sources, not more unique English. Local filesystem inventory covers all archived files; the content census is of the explicitly named original snapshots, not an additive census of every historical transformation. Uncounted small legacy samples remain excluded unless separately reconciled to originals.

## One architecture

| Setting | Proposed value and reason |
|---|---|
| Decoder | 8 pre-normalized causal Transformer blocks; width 384; SwiGLU width 1024; 6 attention heads, 6 KV heads; head dimension 64 |
| Parameters | 17,308,032 with an 8,192-entry total vocabulary and tied input/output embeddings; calculated from tensor shapes without allocating tensors |
| Position / norms | RoPE theta 10,000; RMSNorm epsilon 1e-5; no linear biases; no dropout initially |
| Window | 512 content/prediction positions. Preserve document boundaries; document-isolated attention when packing. Segment longer documents without duplicating overlapping targets; all segments stay in one family/split. Report long-document coverage lost. |
| Runtime | Local MLX candidate, PyTorch CPU as small correctness reference. Reuse inspected source as components, not as an approved trainer. Validate loss/masks, tokenizer IDs, optimizer and save/reload before real data updates. The existing unfused reference implementation may be too slow. |
| Precision | Conservative initial FP32 reference. A mixed-precision implementation is a separate validation change, not an assumed speedup. Do not change precision mid-run to rescue a deadline. |

This size limits compute and memorization risk relative to the available corpus. It does not follow a universal tokens-per-parameter rule. TinyStories research supports investigating small models on restricted language; its deliberately simple synthetic language does not establish ordinary-English coverage ([paper](https://arxiv.org/abs/2305.07759)). Compute/data scaling results motivate reporting both model size and token budget, not extrapolating guaranteed competence from a ratio ([paper](https://arxiv.org/abs/2203.15556)).

## Tokenizer decision

**Retrain an 8k byte-level BPE after the new family split is frozen.** Preserve old tokenizers for comparison and reproducibility; do not automatically reuse their fitted vocabulary/provenance. The fresh tokenizer must see only eligible training families. Fit on a deterministic, source-balanced <=32 MiB training-only sample; no tokenizer work is performed now.

Use disjoint content/control IDs and lossless UTF-8 byte coverage. The 8,192 total includes reserved control IDs; ensure rounding in the trainer does not change the parameter count. Acceptance criteria are in `ENGLISH_GATE.md`: 100% roundtrip/integrity, each-domain median <=1.6 and p95 <=2.5 tokens/word, aggregate >=3.0 UTF-8 bytes/token. Also report compression relative to preserved 16k BPE on exactly the same development documents. If 8k fails, revise the design and parameter calculation before model initialization; do not silently substitute 16k. An 8k tokenizer's token budget cannot be inferred exactly from 16k estimates.

## Data and split contract

- Base objective: causal next-token cross-entropy over prose plus EOS; no assistant-only masking, role conditioning, teacher answers or chat template. Dialogue occurring naturally inside prose is ordinary text. Reserve explicit chat/instruction records for the later stage.
- Candidate base sources: TinyStories train ranges, FineWeb-Edu sampled web documents, and Cosmopedia expository/story text with reviewed source ancestry. TinyStories is simplified synthetic narrative; Cosmopedia is synthetic and textbook-heavy. FineWeb provides the principal real-world prose anchor. Exclude SQuAD and its Wikipedia families from base training for grounded comprehension diagnostics. Reserve Dolly, UltraChat, SmolTalk and OpenAssistant for conversation-stage research, not current foundation volume.
- Normalize only for duplicate detection, retaining original bytes for model input. Exact hashes alone are insufficient. Build cross-source connected families using original IDs/URLs, mirrored/same-site pages, prompt and seed ancestry, tree IDs, article/paragraph IDs and verified near matches (5-word-shingle Jaccard >=.8). Keep all segments, variants, translations and synthetic descendants together. For web, use registrable domain as a conservative grouping unit where feasible; report any resulting source skew.
- Holdout precedence: known evaluation/development/official-test ancestry excludes the entire family from training. Specifically remove the 318 freshly detected TinyStories training-row matches and connected relatives. Existing test material remains protected even if it reduces candidate volume.
- Freeze remaining families into 90% train / 5% development / 5% sealed loss holdout by salted stable family hash, with domain-stratified count/coverage checks. Fit tokenizer only after this split. New authored capability cases are separate from corpus loss samples. Reject a split that cannot meet gate counts.
- Admission requires explicit source evidence, English verification, corruption/contact/credential/repetition checks and a direct semantic sample audit: target 200 sampled records/source, >=95% readable complete English and <=2% major corruption/off-topic boilerplate. The completed assistant review read all 200 TinyStories and rejected FineWeb after 31 full texts under a rejection-only stopping rule declared before reading FineWeb; see the semantic review for evidence and limitations. Factual verification is separate; synthetic assertions are not automatically ground truth. Exclude seed sources whose retained ancestry does not establish permission/appropriate use. The current policy-admitted volume is recorded in the completed semantic review; it is not a whole-corpus semantic certification.

## Mixture and curriculum — proposed bounds

- Total real-data budget across feasibility and continuation: **<=120M predicted tokens, <=3 exposures per original document, <=72 hours of local training wall time**; the first limit reached stops the run. Any toy correctness updates are counted separately and included in the feasibility time/update receipt. No retries or alternate-seed sweeps are preauthorized.
- First 10M exposures: 60% narrative, 25% real web prose, 15% synthetic exposition. Remaining <=110M: 25% narrative, 45% web, 30% synthetic exposition. Percentages are by supervised content tokens, not file bytes. At the full cap this gives 33.5M narrative, 52M web, 34.5M synthetic exposures. A source/doc exposure cap overrides these targets: stop early or revise before launch if eligible supply is insufficient; never replenish it with heldouts or automatically renormalize away the web anchor.
- Final admission must report distinct normalized training documents, unique content tokens after the final tokenizer, source totals and predicted exposures/doc. “Unique tokens” means token occurrences in one deduplicated corpus pass, not vocabulary types. Repeated epochs count as exposures only. Do not count packed overlap twice.
- Batch target: 8,192 predicted positions/update, microbatch 4 x 512 with 4 accumulation steps; mask padding/boundaries and normalize by the actual predicted-token count. Maximum 14,648 full updates plus one partial update at 120M tokens. If memory limits force smaller microbatches, retain the same token batch by accumulation and remeasure throughput.
- Optimizer proposal: AdamW, beta=(.9,.95), epsilon=1e-8, weight decay=.1 on matrix weights only; clip global gradient norm at 1.0. Peak learning rate 3e-4, warmup first 1M predicted tokens, cosine decay to 3e-5 at the predeclared token cap. Freeze seed, optimizer math, data order, schedule and code hash before launch. These are hypotheses, not inherited winning settings.

## Feasibility before committing

A later approval may authorize only this bounded test first:

1. Correctness suite, <=20 toy updates. Then one random-initialized candidate, <=2M real-data predicted tokens (<=245 updates), <=2 hours elapsed, no model-size/LR sweep. All initialization and updates remain prohibited now.
2. Proposed prerequisites to continue the same candidate: all correctness checks pass; loss finite; development loss lower than its initial value by >=5%; zero lineage/mask violations; process peak RSS <=16 GiB; system swap growth <=512 MiB over the sustained window; final 10 minutes sustain >=600 predicted tokens/sec at the intended batch/context. Require at least 15 minutes of training at the intended batch/context. If the token cap is reached sooner, report sustained-throughput/thermal stability unmeasured; no extra updates beyond the cap. Full continuation remains a separate decision.
3. Record thermal/throttling observations and actual checkpoint/evaluation overhead. Calculate remaining runtime from measured sustained throughput before proposing continuation. Feasibility loss improvement is **not** the English gate. Full-run continuation still requires Forge's explicit approval.

## Runtime, storage and stopping rules

- **Assumed, not measured:** at 600–1,500 predicted tokens/sec, 120M exposures take 22–56 hours of update time; allow 15% overhead, roughly 26–64 hours. At 200/sec this exceeds 160 hours before overhead and should fail the local feasibility decision. No hardware peak-TFLOP estimate is a throughput measurement.
- 17.3M FP32 parameters plus gradients and two Adam moments are approximately 277 MB before framework/activation/logit overhead. Budget <=16 GiB process RSS and >=20 GiB disk headroom. Actual allocations and thermal limits are unknown until the approved test.
- Save resumable state every 5M exposures or 60 minutes at a safe boundary, plus before a clean stop. Retain latest two complete checkpoints and one best-on-development checkpoint; append counters and hashes before pruning. Rough FP32 model+Adam state is 208 MB/checkpoint plus metadata; reserve 2 GiB for retained states/temporary publication, separate from data and logs. Never resume a pre-restart model. Resume after an interruption needs the exact same experiment ID/data/tokenizer/code/seed and explicit authority for remaining bounds; it does not reset counters.
- Development loss check every 2M exposures on a fixed 200k-target development subset, full development/generative diagnostics every 10M. Only the best predeclared development candidate gets sealed evaluation once.
- Stop immediately on nonfinite loss/gradients, incorrect counters, hash/lineage/mask failures, loss explosion >2x median of prior 100 updates for 20 consecutive updates, or repeated identical-token degeneration in >=50% of the fixed 20-prefix development smoke set. Preserve the failure receipt; no automatic rescue/restart.
- Stop for no relative development-loss improvement >=1% across three consecutive 10M-exposure checkpoints, or a >10% worse development loss on two successive full checks. Loss-based stopping selects a candidate but never passes the English gate. Enforce token/update/time/RSS/disk limits at boundaries and report any in-flight boundary overrun; no claim of a hard OS kill deadline. A fresh approval must specify whether stricter process supervision is needed.

## Decisions requiring Forge

1. The later “use the new model” instruction referred to the chat model and is resolved. It does not change the training boundary.
2. After reviewing admission and custody prerequisites, explicitly approve **only** the <=2M-token / <=2-hour local feasibility test if desired. The <=120M / <=72-hour full run is a later, separate decision informed by measurements.
3. Nominate the independent acceptance-set custodian/grader (Forge can hold it). No new data purchase/download, cloud run or budget reset is proposed. Unknown derived artifacts are retained; no cleanup deletion decision is needed for them now.
