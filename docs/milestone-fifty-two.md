# Second-iteration training and direct conversation assessment

Creator: Navneet Prabhakar

Date: 19 October 2026

## Result

The selected 81M model completed the frozen local foundation schedule. Held-out loss improves substantially, but **all eight conversation tasks fail**. Direct five-dimension assessment is **1/20, normalized to 5/100**: limited local grammatical coherence earns one point; understanding, relevance, context/corrections and instruction following each earn zero. This is a development-conversation rubric score, not readiness or population accuracy. The previous iteration scored 0/100; the second model still demonstrates no successful requested task.

## Actual training

- Original continuation session 78903 exited with code 0; worker PID 85369 is absent after termination. No restart or extra training was launched during monitoring.
- Selected LR 0.0003, fresh canonical seed 20261019, 80,765,440 parameters, 16K tokenizer, full FP32/dense embedding recipe and frozen source/schedule identities from milestones 47–49.
- Final step/cursor **9,984**; **10,223,491** logical processed/supervised positions. Continuation itself executed 9,728 updates / 9,961,347 positions after the selected screen's 256 / 262,144.
- Including the discarded optimizer screen: **10,485,635 physical training positions**, within the unchanged 10,485,760 ceiling. No third trial or replay was added.
- Terminal status is `data_exhausted_before_target`, as predeclared: the complete finite schedule ends 125 positions below its declared ceiling. `completed_update_target:false` is preserved; it is not relabeled as target attainment. All scheduled batches were consumed.
- Final checkpoint `000000009984-44136fa355b3`; wrapper manifest SHA-256 `4ff572d2ced0ead0c532befae1a758430ef0557eb3a7d732feaf30ee0ae9a76f`. Previous checkpoint 9,856 remains retained.
- Continuation wall time 10,227.27 seconds (170.45 minutes); update time 9,825.10 seconds, checkpoint time 341.62 seconds, preflight 49.11 seconds. Update-only throughput 1,013.87 positions/second. These exclude the two earlier screens and are not total experiment wall time.
- Process peak RSS 6,090,440,704 bytes; allocator peak 4,027,989,136 bytes. Unified-memory measurements overlap and must not be summed. No controlled thermal/performance comparison is claimed.

## Frozen held-out loss

Same 64 validation groups, 32 per source, full selected conversations and predeclared source-balanced aggregation. Initial canonical weights reconstructed after training; no test model scoring.

| Metric | Initial | Terminal | Improvement / 95% paired bootstrap interval |
| --- | ---: | ---: | --- |
| Foundation NLL, nats | 9.767147 | 5.042328 | 4.724819 / [4.611715, 4.845656] |
| Assistant-target NLL, nats | 9.780451 | 5.087246 | 4.693204 / [4.538920, 4.856318] |

The frozen foundation smoke passes its declared minimum improvement and positive lower-bound requirements (10,000 source-stratified bootstrap resamples, seed 20261019). This measures teacher-forced next-token prediction on this held-out selection. It does not establish interactive ability, factuality, tools, broad English coverage or cross-backend training quality. The selected terminal checkpoint and contiguous update events are verified against the frozen plan and optimizer selection.

Evidence: [terminal diagnostics](../reports/iteration-two-terminal-score.json), [training completion receipt](../reports/milestone-fifty-two-training-completion.json).

## Actual conversation

Eight turns, raw cached greedy decoding, maximum 64 new tokens per turn, no teacher/retrieval/repair/tool fallback. Follow-ups were chosen after reading each reply. All failing assistant replies remain in subsequent context. No truncation or exception occurred; each response stops at message end. Full prompts, replies, token IDs, context hashes and timings are retained in the [published assessment](../reports/iteration-two-conversation-assessment.json).

| Turn | Requested task | Observed failure |
| --- | --- | --- |
| 1 | Say hello to Mira in one sentence | Repetitive claim that the word a is a popular language; no greeting/name |
| 2 | Exactly Hello Mira | The best language is a is a; ignores exact words |
| 3 | Recall name only | Repeats preceding irrelevant response |
| 4 | Two apples plus one, number only | Unrelated sentence about days in a week; no answer |
| 5 | Correct name to Tara and count to two | Generic welcome/ideas sentences; neither corrected fact |
| 6 | Professional meeting change from 3 PM to 4 PM | Generic welcome/ideas sentences; omits meeting/time |
| 7 | Caveman style, meeting at 4 PM, at most 12 words | Generic filler, no time/style, exceeds word limit |
| 8 | JSON recap with explicitly restated corrected facts | Repeated prose, invalid JSON, none of the requested values |

Representative exact replies:

> The best language is "a" is "a"

> You are welcome! I'm glad you have a great idea. I'm glad you have a few ideas for you.

All eight task judgments are failed. Coherence receives **1/4** for isolated grammatical sentences despite repetition, malformed syntax and disconnected/contradictory filler. Every other dimension receives **0/4**. Direct review is `delegated_expert`, with `human_attestation:false`. Automated publication checks verify evidence integrity and aggregate explicit judgments; they do not judge quality.

The same initial prompt, budgets and rubric as iteration one permit a limited developmental comparison. Adaptive later prompts and shared failed history prevent interpreting 5 versus 0 as a reliable population improvement. Mature-content settings and actual tools/MCP are untested here. Evaluation transcripts remain unadmitted for training.

## Next iteration

1. Preserve this completed foundation checkpoint, failures and protected evaluation families. Do not repeat the exhausted schedule or silently increase its exposure ceiling.
2. Diagnose conditioning/serialization and the actual fraction of assistant supervision before blaming capacity. Use existing held-out loss and raw responses; avoid selecting prompts merely to obtain a passing transcript.
3. Prepare a separately reviewed **assistant-target SFT** release: initial bounded research admission covers foundation only. Review full dialogues for factual/constraint quality and privacy, freeze group-based splits and audit masks/end-of-message supervision. Broader screened rows are not automatically SFT-approved.
4. Predeclare the next finite local schedule, learning-rate choice, processed versus supervised exposure, replay caps, checkpoint migration/optimizer policy, validation criteria and regression checks before launching. Retain the foundation checkpoint as a baseline; do not train on this interview or protected scenario variants.
5. After that iteration: terminal verification, an actual adaptive conversation, direct rubric/turn judgments, published transcript and failure-driven next steps. Add broader independent held-out task/style coverage before claiming usefulness.

A bigger model or paid pretraining is not justified by these results alone. Separate teacher training-use rights/category review, mature-content settings, learned tools/MCP, actual MLX/CUDA resumed-training quality, quantization and later ESCI remain open. No new teacher/API/cloud calls or spending were used for this milestone. The full project goal remains active and incomplete.
