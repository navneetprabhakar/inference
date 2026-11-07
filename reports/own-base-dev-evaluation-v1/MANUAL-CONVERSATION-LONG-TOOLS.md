# Conversation and long-tool manual review

All49turns across20sessions were read against their original frozen prompts/rubrics, including actual generated frames and tool traces. This is one unblinded assistant review, not an independent blinded experiment. Raw reports and scores remain unchanged; the companion JSON binds their hashes and records per-turn decisions. No private cases, new inference or training occurred.

| Corpus | Full sessions passed | Turns passed after manual review | Manual-rubric turns reviewed |
| --- | ---: | ---: | ---: |
| Public conversation |0/12|0/25|19|
| Four-call sessions |0/8|0/24|24|

All43manual-rubric turns fail. This resolves22previously unresolved turn-pass judgments in the raw summaries; other manual-content turns already had functional failures from protocol/call-sequence checks. Six exact-answer conversation turns remain failed. The lack of a delivered answer after a closed session is a failure, not an untested success.

- **Conversation:** generic writing-review/rewrite boilerplate appears regardless of request. The model misses supplied facts and corrections, fails missing-input clarification, does not provide usable drafts or hobby suggestions, and repeats. It retains a stale label after correction; even explicit list copying and middle-item recall fail. Surface fluency and valid JSON do not establish instruction understanding.
- **Tool chains:** seven sessions execute only one call per requested two-call turn and stop at an intermediate value; the eighth fails its first frame and closes. None completes the requested four operations. Six correct first calls show partial interface learning, not successful chaining. Later turns select wrong operations/operands and fail to acknowledge correction-without-recalculation.
- **Observation grounding:** actual21900 is answered120000, and actual308 is answered138. Some intermediate readbacks are accurate, but the required sequence is absent. The automatic long-tool readback denominator is0 because these manual rubrics are not an automated readback metric; it must not be described as evidence of perfect fidelity.
- **Permissions:** no forbidden/unknown successful calls were reported. This remains separate from relevance, correctness and completion.

Next intervention should address basic prompt grounding and short connected responses as well as tool sequencing. Do not deploy or blindly repeat this same SFT mixture. Audit the dominance of generic rewrite responses, then prospectively freeze a balanced short grounded curriculum with varied request types, fact/observation substitutions, corrections and complete tool chains. Keep these exact public examples excluded from training. Improvement must be shown on actual complete sessions; the existing acceptance gates remain unchanged.
