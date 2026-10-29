# Blinded acceptance review — 29 October 2026

**Review completed: 20/24 exact label agreement; adjudicated grades are 13 Accept, 2 Borderline and 9 Fail. Training remains paused.** The user authorized a separate blinded review agent. It received only the shuffled packet, without author labels or conversation history, and attested that it read no other task evidence. This is separation from the author, not human validation or evidence from an independent model provider.

Read the [reviewer's complete reasons](BLIND_REVIEW_RESULT.md), [case-level comparison](review-adjudication.json), and [integrity verification](review-integrity.json). All 12 author-acceptable and all six author-failed examples retained their labels. Four of six author-borderline cases changed. The sample is a small authored calibration set, so 20/24 agreement is descriptive, not a model-quality or reviewer-reliability estimate.

| Case | Author | Reviewer / adjudicated | Resolution |
|---|---|---|---|
|05|Borderline|Fail|“The bench” identifies the destination but does not restate the updated instruction. Preserve action and object as well.|
|09|Borderline|Fail|“Easy to reach” is an unsupported accessibility claim; the correct location does not excuse it.|
|16|Borderline|Fail|A bare timestamp does not fulfil the explicit request to write a reminder. A useful reminder identifies the event and time.|
|24|Borderline|Accept|“Keep it safe” is a supported inference from rain entering through the window. Repeating the exact causal words is unnecessary.|

Cases 15 and 22 remain Borderline: vague actions and weak causal explanations are not automatic passes. All other grades remain unchanged. Adopt the reviewer grades prospectively; do not change old student scores or overwrite frozen author examples to manufacture agreement.

## Rubric clarification

This supplement supersedes the permissive minimal-reminder sentence in the original frozen contract **for natural reminder-writing tasks**. It does not alter the structured time-extraction scorer or retroactively rescore model results. A future natural scorer must separate copying a correct value from performing the requested act. “18:25” can satisfy “time only,” but not this packet's “write the reminder.” If downstream structured clarification tests accept a bare time, report them as clarification/value tests, not natural reminder-writing success.

Supported contextual inference is allowed. A motive directly supported by the supplied causal narrative can answer “why”; an unrelated physical property cannot be added merely because it is plausible. Exact keyword matching would incorrectly reject case 24 and incorrectly reward case 09.

## Coverage findings and next work

- The repeated fourth-turn weather question does not retrieve earlier task state. These six four-turn anchors demonstrate topic switching and missing-information handling, not recall after interruption. Add genuinely earlier-fact follow-ups in a new version before claiming that coverage.
- The 240 natural candidates still use only six main dialogue patterns. This review of 24 anchors does not validate those candidates or the 20 instruction strings per prerequisite task.
- The existing 48-token natural reply allowance still permits context overflow under worst-case generated history. Review completion does not resolve that constraint.
- Next preparation should broaden natural dialogue frames, add interruption-and-return cases, define diversity honestly as surface variants unless a stronger taxonomy is validated, and settle context plus the training budget. Then reassess before training.

No student inference or optimizer updates were performed during this review. All three existing frozen manifests were verified unchanged. The original 12/6/6 distribution remains historical author labeling; use the adjudication overlay for current calibration. Training readiness remains false.
