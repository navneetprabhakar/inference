# Phase A acceptance contract

Status: prepared for review; not a training release or a claim of acceptable model capability.

The pilot answers from supplied English context, asks for missing information, explains stated causes, follows constraints and incorporates corrections across two to four turns. A topic switch must change the active question without erasing relevant earlier facts. It must not invent owners, times, causes, prices or forecasts. Broader knowledge and tools remain later milestones.

Each turn is graded separately for factual support, requested dialogue act, instruction/format compliance and termination. A conversation passes only when every turn passes. A final correct time does not repair a failed first clarification. Explicit “name only”, “HH:MM only” and “one step” instructions are requirements. Semantically equivalent wording is acceptable for natural tasks; extra unsupported claims fail. Vague replies that omit a required action, entity or cause are not made correct by sharing a keyword.

The 24 public anchors contain 12 acceptable,6 borderline and 6 failed conversations. They are never training or final-test records. The borderline labels are author judgments awaiting independent adjudication, not permission to count them as passes. A minimal time-only reminder can be adequate when the meeting is unambiguous; its content, requested form and earlier clarification must still be graded separately.

Review [BLIND_REVIEW.md](BLIND_REVIEW.md) before opening the labelled [acceptance examples](ACCEPTANCE_EXAMPLES.md). Record Accept / Borderline / Fail and the failing turn/reason. Primary-author checks do not count as independent agreement.

## Context contract

Prerequisite diagnostics use 256 context and 32 generated tokens per turn. All prepared-v 2 records fit even when every prior generated reply consumes that allowance. Natural candidates and anchors are checked at 48 tokens per reply: gold histories fit, but 78 of 714 candidate turns and 6 of 60 anchor turns can overflow under worst-case generated histories. No truncation was applied. This establishes a headroom gap, not observed runtime overflow on those candidates.

Before natural acceptance, either validate a larger context under the unchanged under 100 M constraint or explicitly select and validate a shorter response allowance that still supports the intended conversations. Do not quietly shorten or remove difficult final cases to manufacture a pass.

## Authorization boundary

This phase permits preparation and bounded inference only. Zero optimizer updates were made. Historical training ledgers and stops remain unchanged. Phase B requires a resolved readiness packet and a separate training approval, as requested by the user.
