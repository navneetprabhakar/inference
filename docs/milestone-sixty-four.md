# Actual SFT completion and direct conversation assessment

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

**The bounded SFT experiment completed, but conversational quality remains inadequate: 5/100, zero of eight tasks passed.** Validation loss improved; this did not produce demonstrated request understanding, correction handling or useful replies. Do not advance to learned tools/MCP or claim broad conversational/style capability on this evidence. The next iteration needs a small diagnostic and learning-control experiment before another broad run; see `docs/iteration-four-plan.md`.

## Actual optimizer comparison

All rows use the frozen 109 validation dialogues and original 64 source-balanced retention groups. Lower NLL is better. These are reference-response diagnostics, not factual correctness scores.

| State | Assistant mean group NLL | Foundation-retention NLL |
| --- | ---: | ---: |
| Foundation baseline | 4.649042 | 5.042328 |
| 1e-5, 64 updates | 4.603233 | 5.007073 |
| 5e-5, 64 updates | 4.561189 | 4.982953 |
| Selected 5e-5, 475 updates | 4.462861 | 4.925162 |

Both equal-exposure screens pass the baseline +0.2-nat retention guard. The 5e-5 rate wins the frozen primary-loss rule by more than the 0.01 tie margin. Its exact recorded 64-step checkpoint/optimizer resumes to the planned endpoint; no reset, changed recipe, early stopping or rerun.

Terminal mean paired assistant improvement is **0.186181 nats**, with descriptive bootstrap interval **[0.172477, 0.200052]**, 10,000 resamples / seed 20261019. The predeclared NLL smoke passes. The same validation groups select the learning rate, so this is not an independent generalization test or unbiased capability estimate. No test model losses were used.

## Execution and accounting

- Selected chain: **475 updates / 1,900 whole-dialogue microbatches / 800,130 prediction positions / 716,288 assistant targets**, terminal `update_target_reached`.
- Both screens plus selected continuation: **539 physical updates / 915,325 prediction positions**. All 950 groups appear twice in the selected chain; 256 also appear in the discarded screen, giving three physical passes for those groups and two for the remaining 694. No hidden replay.
- The 411-update continuation invocation takes **760.623 seconds**, including its input verification/checkpoints. This excludes the earlier screens, scoring and conversation; it is not an end-to-end experiment time or portable throughput guarantee.
- Actual process peak Metal allocation **5,949,588,156 bytes**. Allocator cache and RSS have different overlapping meanings and must not be added to infer physical usage/headroom. Exact counters remain in the training report.
- Existing 12,664-position disposable synthetic preflights are reused; no additional synthetic gradient probe. No new teacher, API, cloud action, dataset acquisition or spending.

Actual retained terminal checkpoint:

`data/iteration-three-sft-experiment-v1/runs/selected-continuation/checkpoints/000000000475-44136fa355b3`

Exact state, all update events, scored checkpoint identity, logical plan, source/tokenizer and shared ledger are verified before scoring and interview. Historical runtime/stage/preflight source bytes stay unchanged.

## Actual conversation

Eight adaptive turns use the original first prompt, 64-token raw greedy replies and unchanged five-dimension rubric. Every actual answer is retained as subsequent history. All eight responses exhaust the length cap; none emits a learned stop token within the budget. No repair, teacher fallback, ideal-answer substitution or selective removal.

| Turn | Requested task | Observed failure |
| --- | --- | --- |
| 1 | Greet Mira in one short sentence | Unrelated word discussion and repeated fragments |
| 2 | Correct the reply by copying the exact greeting | Continues repeated unrelated fragments |
| 3 | Apply the corrected name Arun | Does not return the name |
| 4 | Count two apples plus one; output one digit | Repetitive miles/hours discussion, no answer 3 |
| 5 | Name one fruit other than an apple | Recipe/list fragments, no fruit answer |
| 6 | Rewrite a file request professionally | Continues recipe fragments |
| 7 | Caveman style while preserving two apples and tomorrow | Unrelated meal text; meaning/constraints lost |
| 8 | Recall the corrected name | Invented letter/name and hours text |

Scores: understanding **0/4**, relevance **0/4**, coherence **1/4**, context/corrections **0/4**, instruction following **0/4**. Total **1/20 = 5/100**; **0/8 tasks succeed**. Limited grammatical openings justify the coherence point; dominant repetition prevents a higher score. The previous foundation pilot also scored 5/100. Different adaptive follow-ups and a single unblinded development conversation do not support a causal or population-level comparison.

Full raw token IDs, exact answers, history hashes, generation timing, per-turn judgments and limitations are in `reports/iteration-three-sft-conversation-assessment.json`. Delegated review, `human_attestation:false`, `training_approved:false`. No tool, MCP, mature-content, broad-style or CUDA-quality acceptance follows.

## Focused post-assessment accounting

All 950 actual train batches contain a supervised terminal EOS; there are 1,257 supervised assistant message-end targets per pass. Thus stop supervision is present. This does not establish that the model learned to use it or identify the cause of degeneration.

Actual assistant content lengths: **1,257 turns, median 261 tokens, mean 283.164; 120 turns at most 64 tokens**. This supports investigating short-answer/control learning and length distribution. It does not explain away ignored requests or justify changing the published evaluation budget/score. Both accounting reports are post-hoc diagnostics, with zero gradients and unchanged decoding.

## Evidence and next step

- `reports/iteration-three-sft-optimizer-selection.json`
- `reports/iteration-three-sft-training.json`
- `reports/iteration-three-sft-terminal-score.json`
- `reports/iteration-three-sft-conversation-assessment.json`
- `reports/iteration-three-sft-termination-accounting.json`
- `reports/iteration-three-sft-assistant-lengths.json`
- `reports/milestone-sixty-four-actual-sft-evidence.json`

The frozen implementation's 67 mechanics/data/evaluation checks and separate overlapping 28 conversation checks remain the relevant code tests. This milestone executes that unchanged code on the actual model and validates its actual artifacts; it adds no implementation change requiring repeated test runs. The full goal remains active/incomplete. No subsequent training iteration has started before this assessment and its failure-driven plan.
