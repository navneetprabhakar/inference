# Consolidated acceptance registry

One campaign now owns model selection and final acceptance. Existing assets keep their original identities/hashes and historical grades. “Unseen” is never restored by moving or renaming a file.

| Existing asset | Current role | Permitted campaign use |
|---|---|---|
| PhaseA24 acceptance examples + review-adjudication overlay |Public rubric calibration:13Accept,2Borderline,9Fail |Calibrate reviewers; never training or final testing. Original12/6/6 author labels remain provenance. |
| PhaseA24-case blind review |Completed separate-agent calibration,20/24 three-way agreement |Evidence of disagreements, not a certified human preference model or validated new threshold. |
| PhaseA prepared-v2 matrix/counterfactuals |Repeatedly exposed development diagnostics |Regression/error reporting only; no final selection score. |
| PhaseA240 prospective-final candidates |Unreleased, templated/context-limited development fixtures |Never convert to the new final set. |
| PhaseA-completion24 natural scenarios/88turns |Reviewed development references, six functions,24 frames |Regression/context checks and reviewer examples. Review validity does not imply student success. |
| Binding probes, contrastive/pair-fit/tiny-copy packets |Exposed research diagnostics |Regression and hypothesis evidence; exclude from primary new selection/final benchmark. |
| Historical foundation options/stories |Exposed language diagnostics, unstable story grading |Audit/calibration only; fresh readiness packet required. |
| Legacy untouched final bank |Legacy sealed asset |Remain closed; not needed to run this campaign. Its scope is not a substitute for new acceptance. |

## One product contract

The first milestone is **coherent short English conversation grounded in supplied information**:2–4 turns, at most32 native generated tokens including EOS per reply, all history within256 tokens. Six functions: supplied-fact grounding, comprehension, clarification/uncertainty, corrections and continuity, following instructions, and short explanations. No external knowledge accuracy, tools, long chat or unrestricted essays are certified by this milestone.

A passing turn is understandable English, relevant, satisfies the requested act/constraints, uses supplied facts correctly, carries relevant prior state, and introduces no material unsupported claim. Semantically equivalent phrasing is valid unless the user requests an exact string/format. Borderline is not a pass. A conversation passes only if every turn passes; a correct final answer cannot repair an earlier wrong answer.

EOS remains normal. No hidden truncation of history, suppression of EOS, answer repair, fallback model or oracle substitution. Exceeding the output/context cap fails. All references and worst-case generated histories must fit prospectively; if the scope cannot accommodate a required scenario, stop preparation and revise the product contract before any outcome is seen. Do not selectively drop difficult final cases.

## New packets required before launch

These counts/coverage rules are fixed; the packets are **not yet authored, independently reviewed or sealed**. This audit is a campaign design, not a claim that missing data exists.

- **Readiness:**60 native continuations,15 each for everyday situations, procedural prose, explanatory prose and narrative;120 passage-grounded four-choice cases,30/domain, plus empty/shuffled-passage controls;60 distinct grammar contrasts. No chat role markers for foundation language testing. Prefixes≤128 tokens, continuation cap64; options jointly encoded with verified prefix boundaries. Continuation grading ignores only the final incomplete cap-cut fragment, retains all earlier generated text, and reports caps/EOS/BOS separately; no EOS requirement is imposed on native continuation diagnostics. At least one complete sentence is required to pass.
- **Conversation development:**120 new conversations,20/function,2–4turns. At least four different dialogue structures overall and three per function: direct follow-up, correction/repair, interruption-and-return, and multi-constraint request. No more than25% of cases may share one abstract dialogue structure overall. Authoring IDs are kept out of prompts. Include both concise and full-sentence valid answers.
- **Sealed final:**240 new conversations,40/function, same scope/structure quotas but disjoint scenario source families, concrete events and value assignments. Created/reviewed by a custodian separate from training/example selection; store payload privately. Only schema/counts/coverage/hashes are exposed to training work. No tuning against outputs or references. Each family includes at least10 interruption/continuity cases and10 answerability contrasts; quotas may overlap. These requirements also apply proportionally to development (five each).
- **Preservation anchor:**the fresh foundation-readiness packet becomes the fixed language regression packet after readiness passes. Native NLL is an additional proxy; it cannot replace behavioral retention.

Exact matching is only for explicit exact-copy/format requests. Natural quality requires semantic judgments. Reuse the existing aggregation discipline (complete turn coverage, explicit flags and reasons); add language, relevance, continuity, unsupported-claim and contradiction fields. The final protocol cannot accept keywords as semantic proof.

## Review, sealing and uncertainty

Expand the24 public anchors with12 new calibration cases: total36, including24 clear and12 borderline cases after adjudication. Two reviewers must each get≥23/24 clear-anchor binary judgments correct. Borderline judgments must include a reason and count as non-passes. On actual outputs require≥90% turn-pass agreement and≥85% whole-conversation-pass agreement before accepting measured gates. A single fixed re-review pass with shuffled order is allowed; persistent disagreement stops the campaign as **measurement invalid**, not model failure. The conservative final label requires both reviewers to accept; unresolved disagreements are not promoted to passes.

Reviewers are blinded to arm/checkpoint identity and each other's scores. Separate model agents do not imply independent providers or human validation. Human review is welcome but must not be claimed unless performed. All final outputs are reviewed, not a favorable sample. Report raw denominators and conversation-level uncertainty; repeated turns and paired variants are not independent observations.

All training labels receive a semantic review by a nonauthor;20% receive a second review stratified across functions/structures. No unresolved label defect is admitted. Only one batch of pre-launch revisions is allowed, followed by rechecks; repeated admission failure terminates preparation. Do not use student outcomes to repair the benchmark.

The final set is opened **once**, only for the selected, independently confirmed endpoint. Failed final outcomes terminate this campaign; the exposed set becomes regression evidence for a different future study, never a fresh retry.
