# Fresh-session, length and system-role diagnostics

Creator: Navneet Prabhakar

Date: 19 October 2026

## Result and decision

**The model fails all 16 diagnostic tasks in each tested condition.** Repetition and wrong content persist in fresh sessions, at a longer output budget, and after removing the initial system message. The existing eight-turn conversation score remains **5/100**. These diagnostics do not identify a training root cause or establish a population failure rate.

Next, use the existing individually reviewed 12-row SFT release as a small fitting control. It is too small for broad conversation training but appropriate for testing whether the full-size model can fit a handful of fixed references. Reuse the existing explicit-row publisher/reader and foundation-to-SFT transition rather than extending the broad research reader again. No new training has started.

## Frozen cases and references

`configs/iteration-four-fresh-scenarios-v1.json` selects 16 already reserved scenarios: two each for stopping/exact copy, reference selection, corrected quantities, quantities, negation, conjunctive constraints, conversation memory and style switching. They are diagnostic candidates, not a newly validated general benchmark.

All contexts and references were read before freezing and before their actual outputs. Arithmetic, ordering, colors/prices and supplied fictional meeting facts were checked directly. One manually specified caveman-style reference preserves the original facts; it is one acceptable reference, not a unique style oracle. The original source-case hash remains recorded.

The existing training guard rejects all 16 exact contexts both with and without the system message, and their reserved `eval-v1/` identifiers. No historical runtime/source file was changed. This proves exact-context/identifier protection, not exclusion of every paraphrase or semantically related training example. Supplied assistant turns in the scenarios are synthetic fixtures, clearly distinguished from actual generated student history.

## Actual paired results

| Condition | Tasks passed | Length cap | Learned message-end |
| --- | ---: | ---: | ---: |
| System message, 64-token budget | 0/16 | 15 | 1 |
| Same context, 256-token budget | 0/16 | 13 | 3 |
| Initial system message removed, 64-token budget | 0/16 | 15 | 1 |

Twelve scenarios have reviewed exact strip-only oracles. The other four require direct semantic/style judgments; all complete replies were read, with per-condition reasons retained. They omit the required corrected date, time and room and substitute unrelated repetitive text. Shortening/stopping alone does not count as task success.

The initial frozen diagnostic reserves **32 generations /5,120 maximum generated tokens** and actually emits **4,802** tokens. Every 64-token result is an exact prefix of its 256-token counterpart; fresh cache/history is used for every call. No generated reply is reused as context for another case/budget.

The follow-up system-role ablation is a **separate post-hoc frozen protocol**, after observing that the latest SFT train messages comprise 1,257 user and 1,257 assistant messages, with no system messages. It reserves **16 generations /1,024 tokens**, actually emitting **1,007**. Only the initial system message is removed; remaining fixture context stays exact. Removing it can remove the style instruction, so comparison is limited to exact/semantic task recovery. The original diagnostic ceiling and outputs are not edited or reset.

Total actual work: **48 local MLX GPU generations /5,809 tokens /zero new optimizer updates**. The model, tokenizer, dense-onehot FP32 implementation and greedy decoding stay fixed. No teacher, API, cloud or paid calls.

## Conditional reference measurements

One complete reference is teacher-forced per original scenario, with final-assistant content positions and structural targets checked against the actual serializer:

- Correct first reference token is greedy top choice in **3/16** cases; median target rank **79**. The three matches are generic opening tokens, not evidence of complete answer understanding.
- Message-end after the supplied correct reference is greedy top choice in **1/16** cases.
- EOS after the supplied reference plus message-end has conditional probability **0.995272–0.999923** across the 16 fixtures.

This supports a narrower conclusion than “stop tokens are missing”: the EOS-after-message-end association is strong on these forced contexts, while correct content selection and early message-end remain weak. Forced-reference probability is not free-generation success. Model undertraining, objective/data distribution, optimization and other explanations remain hypotheses until the fitting control. The fresh cases also differ from the earlier adaptive interview; they do not quantify the causal effect of erroneous history.

## Short-response source review

A separate deterministic train-only packet selects 16 of 47 eligible existing single-exchange dialogues: assistant content 16–64 tokens, user at most 100, whole prediction length at most 192. Every complete dialogue was read. Outcomes: **six considerations, one exclusion, nine deferrals**, human attestation false. Deferrals for facts/ambiguity/scope are not certified factual errors; this is not a population quality estimate.

Six considered rows contain **344 prediction positions /188 assistant targets**. They are not automatically admitted or merged. The sample includes a valid meeting-summary clarification; that topic should be kept out of the fitting control to retain the earlier review's conservative interview-domain isolation. The existing 12-row individually approved release already avoids those interview terms and provides **1,417 prediction positions /851 assistant targets**. Reusing it is the practical next control; do not create another broad admission layer solely to use the new six considerations.

## Checks and reproducible evidence

Four targeted tests pass: stable conditional probability/rank, final-assistant content/stop alignment excluding prior assistant targets, exact protected-context refusal, and rejection of repaired tokens/text/stops/counts. The actual checker reopens model-state checksums, both frozen protocols, all reservations, every raw response, paired prefixes, reference metrics and direct judgments without replaying generation. All prior checkpoint/source bindings remain valid.

- Freeze: `python -m slm.eval.fresh_session freeze`
- Main diagnostic: `python -m slm.eval.fresh_session run`
- Separately frozen ablation: `python scripts/diagnose-system-role.py`
- Actual checker/assessment: `python scripts/check-fresh-session-results.py`

These are one-shot publication/execution commands. Existing outputs cause refusal; do not rerun merely to reproduce displayed status or after an observation timeout. Exact artifacts remain in the ignored private data directories; compact raw results and reference metrics are also retained in reports.

Key evidence: `reports/milestone-sixty-five-fresh-session-assessment.json`, `reports/iteration-four-fresh-responses.jsonl`, `reports/iteration-four-no-system-responses.jsonl`, `reports/iteration-four-forced-references.jsonl`, `reports/iteration-four-short-control-review.json` and the test receipt. The full English/style/content/teacher/tool/MCP/MLX-CUDA/ESCI goal remains incomplete.
