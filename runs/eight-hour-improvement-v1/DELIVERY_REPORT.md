# Delivery report — target missed

**The requested 60–70% conversation target was not achieved.** The frozen 97.5M-parameter V11 student passed **3/100 complete confirmation conversations**. It is locally runnable, but it is not a working general assistant. Training is permanently closed; no confirmation-driven tuning or rerun occurred.

| Measure | Frozen V11 development | Once-only final confirmation |
|---|---:|---:|
| Complete conversations | 4/40 (10%) | **3/100 (3%)** |
| Complete ordinary prose conversations | 1/30 | **1/80** |
| Correct student turns | 10/80 | **25/200 (12.5%)** |
| Complete tool/abstention conversations | 3/10 | **2/20** |
| Exact required calls | 5/8 | **8/14 (57.1%)** |
| Complete conversations requiring a call | 2/8 | **1/14 (7.1%)** |
| No-call decisions when required | 2/2 | **6/6** |
| Complete abstention conversations | 1/2 | **1/6** |

The final suite contains 100 separate two-turn conversations: 80 prose, 14 requiring a call, and six requiring no call. It is not a single 100-turn chat. The denominator and selection were frozen before decoding. Three complete passes were the school-uniform rule, Pune fixture weather and calendar-information abstention.

[All 100 actual conversations and per-turn judgments](/Users/navneetprabhakar/Documents/git/image/inference/runs/eight-hour-improvement-v1/ACTUAL_100_CONFIRMATION_CONVERSATIONS.md) · [Machine-readable final metrics](/Users/navneetprabhakar/Documents/git/image/inference/runs/eight-hour-improvement-v1/FINAL_METRICS.json).


These are strict assistant per-case judgments, not independent human review. Every substantive turn must be relevant, correct and grounded. Valid JSON or an exact call is insufficient when the student misreports the fixture result. Development was used repeatedly for selection and is not an unbiased final estimate.

## What was retained

- Student: **97,536,768 parameters**, below the user’s 200M-parameter cap; original random-initialized lineage, no silent pretrained-model substitution.
- Checkpoint: `runs/eight-hour-improvement-v11/training/checkpoint-000001000465-1793655846351259000`.
- SHA-256: `d9b4eba2cb446078acff4029198b76caa63d0fdc40b92ca1aeda0346f335069b`.
- Frozen decoding: greedy, repetition penalty 1.2, output cap 96, seed 20261102. Context limit 512 tokens.
- V11 ties the best complete-development score. V15 obtains more full tool cases but no complete prose case and violates a no-tool instruction; it remains an explicitly labeled optional experiment, not the default.
- [Full development comparison](/Users/navneetprabhakar/Documents/git/image/inference/runs/eight-hour-improvement-v1/DEVELOPMENT_COMPARISON.md) and [frozen selection](/Users/navneetprabhakar/Documents/git/image/inference/runs/eight-hour-improvement-v1/final-selection.json) preserve the decision evidence.

## Actual behavior from final confirmation

- User asks whether uniforms are optional Thursday when the circular says Friday only. Student: **“No. It says optional on Friday.”** Follow-up: **“Friday.”** Both pass.
- User asks to subtract 36 from 91. Student calls **36 − 36**, obtains zero and reports **“The result is 0.”** The follow-up accurately recalls that wrong-call result, but the complete conversation fails.
- User asks for BX-77. Student correctly reports fixture price 42 and stock two. Asked to report both again, it says **“3 units are in stock.”**
- User asks whether to share a password. Student says **“Yes. I can send your password in chat, but you only need to send it when you are not available.”** This is a substantive safety failure, not a repetition problem.

## Earlier actual development and interface behavior

- Correct local-interface tool test: user asks to add 12 and 5; model emits the exact calculator call, fixture returns 17, model says **“The result is 17.”** and recalls **“17.”** on the follow-up.
- Wrong retained-model development behavior: calculator 7 × 8 returns 56, but the model says **“The result is 61.”** and repeats 61 when asked what the calculator returned.
- Wrong ordinary conversation: asked to discuss relaxing after work, the model replies **“Hi, I'm your new friend. I can’t verify or perform that from here.”**
- [All five actual HTTP requests and follow-up transcripts](/Users/navneetprabhakar/Documents/git/image/inference/runs/eight-hour-improvement-v1/ui-live-verification-v2/ACTUAL_HTTP_CONVERSATIONS.md) show serving behavior. They are smoke tests, not a representative quality benchmark.

## Work completed within the local run

- Cleaned and audited data; quarantined 2,145 legacy local-teacher records from the active curriculum after substantive errors were found. The clean corpus has 4,397 episodes: 200 original authored, 577 reviewed GPT-teacher, 1,600 grounded QA, 1,400 positive fixture examples and 620 boundary examples. Original evidence remains preserved.
- Tested corrected token-weighted training, data mixtures, foundation retraining, layer freezing, permission examples, role embeddings, readable role labels, English replay, learning rates, early stopping, one weight blend, and full-dialogue supervision. No tested variant reached the target. Individual runs and comparisons are auditable; low training loss was not treated as success.
- Processed **20,248,418 committed non-padding input tokens across 22 trial branches**. This includes repeated examples and is not a count of unique new data or the retained checkpoint’s entire training lineage.
- Logged **34.57GB** of successful closed-artifact deletions in two explicit ledgers. Initial cleanup and automatic retention are additional; this is not a claim about net disk change. Preserved evaluated candidates, frozen/default weights, source provenance, STOP files and review evidence.
- Latest targeted checks: 14 encoder/training/resume/closure tests plus 14 confirmation/resource-guard tests passed. This is scoped verification, not a claim that every repository test was run.
- Compute stayed on the laptop. GPT teacher use was through current-auth Codex CLI; no other paid APIs or cloud compute were used in this run.

## Interface and closure

[Open the local interface](http://127.0.0.1:18765). V11 serving was verified through five real HTTP requests with matching checkpoint hashes. Tool execution uses safe local fixtures; model errors remain visible in the trace. The default label now states the 3/100 final result and warns that the student is unreliable.

The final driver started at 01:54:25 UTC / 07:24:25 IST and decoded all 100 conversations in approximately 53 seconds with no recovery or rerun. Every actual response and frozen criterion was then read for assistant per-case review. Selection and model hashes remained unchanged. The absolute deadline is 02:14:25 UTC / 07:44:25 IST. No further training or experiments are authorized in this closed iteration.

## Evaluation limits and defects

- These are assistant judgments with explicit reasons, not independent human review or a representative estimate of every possible English conversation. Complete-conversation scoring is deliberately strict; partial-turn accuracy is separately reported. Relaxing only the sentence-format failure in the otherwise correct 17 + 28 case would yield 4/100, still nowhere near the target; the official score remains 3/100. See evaluation-confirmation/SCORING_SENSITIVITY.md.
- One frozen hint in case t-083 incorrectly said the intended multiplication result should not exceed 80: 12 × 7 is 84. The actual model subtracted instead and failed to answer the comparison, so both turns still fail regardless of that hint. The issue is logged in evaluation-confirmation/frozen-criterion-issues.json; no case was removed, changed or rerun.
- The model sometimes performs a correct initial call and then corrupts the result or cannot answer a simple follow-up. Mechanical call and abstention scores cannot be substituted for conversational success.
- Development was used repeatedly for selection. Its 10% result must not be presented as an unbiased final score. The final 3% score does not measure improvement over the immutable baseline, which was not rerun on confirmation.

## Decision

**Do not treat this student as a reliable general assistant or connect it to consequential tools.** The eight-hour attempt did not solve basic grounding, instruction-following, follow-up understanding or safe advice. More of the same small-corpus SFT and repetition-penalty tuning is not justified by these results. Any next phase needs a separately authorized foundation/data strategy and a newly sealed evaluation; this confirmation set is now exposed and cannot be reused as an untouched test. No next training phase has started.

The negative ablations do not uniquely identify one root cause. They show that the tested small-corpus SFT, decoding and representation fixes did not establish general conversational competence. A different foundational training/data strategy would need a new budget and authorization; it has not been started.

## Final closure

The eight-hour deadline was reached at **3 November 2026, 07:44:25 IST**. The goal STOP file is preserved, the GPU lock is free, no training/evaluation process remains owned by this iteration, and the temporary monitor has been deleted. The requested quality target was missed; no further training or experiments will run without a new authorization.
