# Next foundation continuation — proposal only

**Training remains paused. Recommended next experiment: at most 299,892,736 additional training targets, with an eight-hour total deadline and an obligatory halfway progress check.** This is a learning-curve experiment, not a prediction that conversation readiness occurs at a known token count. All numeric behavioral targets below are proposed engineering thresholds, not published guarantees.

## Why this amount

The own 15,191,712-parameter checkpoint has 78,774,272 retained target exposures and is at update 601 of the reference's 1,000-update warmup. Its small response diagnostic found readable phrases but no coherent continuations among eight examples. These facts support testing additional foundation learning, not a claim that conversation fine-tuning will fix it. The existing native training corpus contains 1,004,262,627 token positions, not that many semantically unique or fully audited usable tokens. No data download is needed for this experiment.

No measured learning curve currently establishes the additional tokens required for conversation competence. This run would reach 378,667,008 total retained targets, under 3% of the 13.1072B full reference recipe. Neither that ratio nor a tokens-per-parameter heuristic establishes readiness.

## Resume and time budget

Explicit approval of this proposal would adopt our benchmark checkpoint `restart/mac-native-benchmark-v1/confirmation/checkpoint.pt`, SHA256 `194f0d3d0574ce86cddeff9a88e38993bf00837b583c1dea2f6c0f506d8255b2`, as the continuation origin. Preserve its weights, optimizer, schedule, data cursor and RNG state. No new initialization, public model weights, warmup reset, architecture change or conversation data. Native MLX BF16 with FP32 master state; microbatch 16, accumulation 32, context 256, 131,072 targets/update. The existing controller defaults to the older benchmark origin: it must be adapted and verified to load step 601 before this run, not invoked unchanged.

| Milestone | Additional updates | Additional targets | Total targets | Estimated elapsed time |
|---|---:|---:|---:|---:|
| First review | 572 | 74,973,184 | 153,747,456 | 1.9 hours |
| Mandatory halfway gate | 1,144 | 149,946,368 | 228,720,640 | 3.8 hours |
| Maximum endpoint | 2,288 | 299,892,736 | 378,667,008 | 7.7 hours |

ETA uses the conservative measured final-ten-minute throughput of 13,029 targets/s plus 20% overhead. The prior benchmark changed from battery to AC, so sustained rate is uncertain. Run on AC. Eight hours covers preflight, all evaluations, saves and reporting, with a five-minute shutdown reserve. Stop on elapsed time even if token targets are unfinished. Preflight is capped at 30 minutes; failure to prepare a valid run ends the attempt. A separate ledger caps aggregate training plus evaluated input positions at 320M; generated-token counts alone must not undercount autoregressive recomputation. Previous budgets remain intact. No deadline resets, automatic retries or extensions.

## Freeze evaluation before the first update

Materialize and hash a reusable development packet: 100 unseen narrative prefixes (at most 64 current-tokenizer tokens each), 100 grammar minimal pairs, 100 four-choice short passage-completion questions, and a fixed 131,072-target heldout narrative loss sample. The baseline is the actual step-601 checkpoint on that same packet, not the earlier step-220 equal-work validation value. Check evaluation text against training where possible and report unresolved native-shard split leakage limitations; this is not a new leakage-free corpus certification. Evaluation labels and prefixes are never training data. If this cannot be prepared and checked within preflight, stop without training.

Generate one continuation per story, at most 96 tokens, temperature .7/top-p .9, with frozen seeds. No chat templates, teacher answers substituted into student outputs, best-of sampling, or selective regeneration. The primary agent reviews all outputs and GPT-6 Luna grades independently (up to four bounded review requests, 240 seconds each, at most 48,000 observed output plus reasoning tokens). Disagreements conservatively fail. These are agent/teacher development grades, not the two human graders required by the original final English gate.

Coherence rubric: score grammar, topical continuity, entity consistency, causal/temporal consistency and local coherence, each 0/1/2. A pass requires at least 8/10, no zero, no premise contradiction, and no incoherent sentence. A trailing unfinished sentence at the generation cap alone does not fail. Degeneration means over 20% repeated 4-word-gram occurrences after first occurrence, or any sentence repeated at least three times.

## Decisions and hard stops

- **At +75M:** publish comparable baseline/current loss, behavior scores and raw outputs. Stop for correctness/resource breaches or fixed validation NLL regression over .20 nats. This checkpoint comes after the original warmup ends; no early chat-obedience requirement.
- **At +150M, all required to continue:** fixed validation NLL improves by at least .10 nats; at least 20/100 story continuations pass; and coherence improves by at least ten percentage points over the freshly measured baseline. Otherwise stop at about four hours and diagnose. Lower loss alone cannot release the remaining budget.
- **Success by +300M, all required:** fixed validation NLL improves by at least .20 nats; at least 80/100 coherent continuations; at least 90/100 grammar pairs and 75/100 grounded completions correct; no more than 5/100 degenerate outputs; correctness/resource checks pass. Stop early if all endpoint criteria are met at an earlier checkpoint.
- **Immediate operational stop:** any nonfinite loss, gradients, weights or optimizer state; checkpoint/RNG/data-cursor correctness failure; GPU memory or process RSS over 12GiB; additional system swap over 512MiB relative to the recorded run baseline; free disk below 60GiB; critical thermal pressure for 60 seconds; loss of AC power. No baseline resets or tolerance changes after a stop. Check within updates, not only at milestones.

Save full recoverable state every 100 updates (roughly 17–20 minutes) and before every quality review. Preserve the original checkpoint, latest recovery point and milestone checkpoints; reserve ample local storage within the 60GiB floor. Hash saves, verify reload, and retain the full optimizer/schedule/data/RNG state. One GPU training process, at most two input-prefetch workers. All charged or interrupted work remains recorded; no automatic recovery training after a hard stop.

## What passing means

Passing establishes useful progress in the small narrative foundation, not broad English competence. The original English gate includes ordinary web/expository prose and more demanding independent tests; TinyStories alone cannot establish that coverage. Its thresholds are not silently replaced by these smaller development checks. The next report must state whether more foundation learning, broader admitted data, or formal-gate preparation is needed. Conversation SFT remains conditional on passing the existing formal English gate (or an explicitly approved replacement) and separate training approval. The 16 reviewed teacher correction seeds remain unused. No full run, conversation training or tool training is authorized by this proposal.

Evidence: [benchmark](../mac-native-benchmark-v1/report.json), [retained checkpoint](../mac-native-benchmark-v1/confirmation/checkpoint.json), [latest response assessment](../conversation-readiness-v1/REPORT.md), [unchanged English gate](../ENGLISH_GATE.md), [machine-readable proposal](proposal.json).
