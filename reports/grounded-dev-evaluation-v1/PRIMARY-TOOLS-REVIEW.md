# Primary tool development review

The grounded SFT candidate regressed severely. It is not a usable conversation/tool model and should not replace the previous candidate. Independent manual review yields **0/422 sessions and 16/583 turns**, against the previous **92/422 sessions and 203/583 turns**, under the same frozen exposed rubrics. This is a real capability regression, not an exact-expression or rounding artifact.

| Metric | Previous candidate | Grounded candidate |
|---|---:|---:|
| Raw complete sessions |78/422|0/422|
| Sessions after separate manual review |92/422|0/422|
| Raw turns |182/583|5/583|
| Turns after separate manual review |203/583|16/583|
| Required call sequence correct |151/453|4/453|
| Protocol failures |33/583|116/583|
| Faithful readback given actual observation, after review |338/475|29/115|

## What failed

- **Call selection collapsed:** 345/453 required-call turns produce no parsed call; 257 of those are otherwise protocol-valid responses. Across 464 expected slots, 356 proposals are missing, 68 use the wrong tool, 31 use the right tool with wrong arguments, four exactly match, and five present calls have unresolved expected dependencies. All 68 wrong-tool substitutions are requested conversions answered with calculator calls. There are no extra parsed proposals.
- **Generic learned text overrides the task:** “What is the second operand?” occurs 91 times, including 40 required-call turns. Complete arithmetic requests also receive “The display frame is 4.” or repetitive transport/permission prose. The model is producing recognizable curriculum phrases without reliably mapping the user's task to them. This supports a generalization/selection failure; it does not by itself isolate whether mixture, training trajectory or base representation is the cause.
- **Syntax also deteriorated:** 90 direct protocol failures plus 26 later turns closed because of an earlier failure. Example malformed output: `{"call":{"arguments":{"a":},"to":"day","value":},"name":"convert"}}`. Thus the reported 116 is not 116 independent first-turn syntax errors.
- **Arguments remain wrong when calls exist:** overlapping mismatch fields are a28, b24, op15, value4, from4, to4. No mathematically equivalent alternative was found among the 31 resolved same-tool mismatches; these are not commutative-expression false negatives.
- **Readback is mostly unavailable or unsupported:** 407/522 expected readbacks lack an observation. Of115 with one,28 pass automatically and one more passes manual review. Among86 failures,55 cannot bind the expected conversion unit after a wrong tool call; those are not established numeric-copy failures. The remainder contains25 wrong/absent numeric readbacks, two incomplete answers and four error/status failures. The original declared nine-significant-digit display rule is honored when classifying numeric readback.
- All five automatically passing turns are follow-ups, not successful requested computation sessions. No forbidden or unknown tool succeeded, but abstaining from most requested calls makes that insufficient evidence of useful tool control.

## Manual overlay, not rescoring the raw report

All27 pending turns were reviewed against their exact original prompts/rubrics. Ten missing-divisor replies asking for the “second operand” pass: in division that operand is the divisor, and the rubric does not mandate a particular noun. Six missing-start replies fail because the starting quantity is the first operand; two destination-unit replies and eight addition-identification replies also fail. One bare `1.` numeric-status answer passes under the prior root precedent: it faithfully repeats the actual1.0 result from an incorrect11/11 call and implicitly confirms a numeric return. It does not establish the requested calculation or rescue the session.

The separate overlay therefore adds11 passes and16 failures, leaves zero pending, and leaves all422 sessions failed. Raw0-session/5-turn/27-pending values remain immutable. Every decision and its exact rubric is preserved in primary-tools-manual-review.json; all expected call slots, family/mode/tool breakdowns and representative raw generations are in primary-tools-analysis.json. The reproducible analysis script checks original input hashes after execution. No evaluation content was used for training and no private cases were accessed.

## Practical next steps

1. Do not run another identical template epoch or promote this candidate. Preserve both endpoints and the fixed rubric so subsequent work has a real regression baseline.
2. Before another long run, measure full124M-model training feasibility and inspect base-language/held-out learning evidence. Correct data serialization and mathematically exact teacher answers were necessary, but they did not produce usable task generalization.
3. Bound the next causal experiment around call selection and mixed-language interference, with a small predeclared public capability check. Require improved complete sessions, not merely lower teacher-forced loss or cleaner JSON. Do not train on these failed case texts or adjust their criteria.
