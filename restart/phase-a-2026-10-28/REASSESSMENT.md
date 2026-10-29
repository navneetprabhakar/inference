# Phase A reassessment — 28 October 2026; review updated 29 October

**Preparation, inference and separate-agent blinded acceptance review are complete; training remains blocked by benchmark and experiment-scope decisions. No optimizer updates occurred.**

The [29 October adjudication](REVIEW_ADJUDICATION.md) records 20/24 author/reviewer agreement and current grades of 13 Accept, 2 Borderline and 9 Fail. This is model-agent review, not human validation. The original frozen 12/6/6 labels remain provenance; the adjudication is the current calibration overlay. The new evidence narrows one bottleneck: the grounding adapter can copy novel clock values when the familiar instruction and order are retained, but fails sharply under changed instruction form/order. This is stronger evidence than the previous unmatched training/development comparison.

## What was delivered

- 24 labelled acceptance conversations, with required facts, prohibited additions, expected dialogue acts and state after every turn; a separate shuffled blind-review packet.
- Two balanced 3,200-conversation curriculum candidates, with identical facts and assistant targets; version 2 shares multi-attribute worlds across different questions.
- A 1,024-conversation fact×wording matrix,256 paired counterfactual records and a balanced 1,000-update schedule. The schedule is prepared, not executed.
- 240 prospective natural final candidates, explicitly unreleased because linguistic/scenario independence and human calibration are unresolved.
- 76,424 CPU contract checks passed for prepared-v2. Additional checks give a known-bad stale-answer system a correct first answer, then verify that repeating it fails all 384 subsequent state/clarification turns. Budget fixtures forbid optimizer reservations, enforce caps and close the ledger cleanly.

## Fresh inference: four frozen historical checkpoints

Full-vocabulary greedy decoding; normal EOS; no answer repair or fallback.128 one-turn name/time cases plus eight three-turn state cases under generated and gold history produce 704 responses. Teacher-forced token ranks/log probabilities are diagnostic and never replace generated output. A follow-up on the same 16 time values adds 128 responses. Total:832 generated responses,332,898 charged input positions and 53.35 active-model seconds. The original Phase A4 cumulative 30-minute/5 M ceilings carry forward across the follow-up; they were not reset. All four parameter hashes and checkpoint hashes remained unchanged.

### Grounding adapter: same task, controlled changes

With no numeric ID:

| Task/fact status | Original prompt | Changed prompt |
|---|---:|---:|
|Names already in its curriculum|5/8|1/8|
|Names absent from that curriculum|4/8|1/8|
|Times already in its curriculum|8/8|0/8|
|Times absent from that curriculum|8/8|0/8|

Across 64 paired wording contrasts, there were 44 losses and zero gains. These contrasts reuse underlying facts and are not 64 independent samples. Numeric-ID addition produced one name gain and one name loss, with no time-answer losses. Therefore numeric IDs are **not the main observed cause in this particular probe**; this does not establish universal numeric-distractor robustness.

### Follow-up isolates the time-prompt components

Each row uses the same 16 values: eight seen and eight unseen. No numeric IDs.

| Fact sentence | Instruction | Order | Correct |
|---|---|---|---:|
|Original|Original|Fact first|16/16|
|Original|Original|Instruction first|1/16|
|Changed|Original|Fact first|15/16|
|Changed|Original|Instruction first|0/16|
|Original|Changed|Fact first|0/16|
|Original|Changed|Instruction first|3/16|
|Changed|Changed|Fact first|0/16|
|Changed|Changed|Instruction first|0/16|

Original instruction: “Copy the complete time only.” Changed instruction: “Please return only HH:MM.” Moving the original instruction before the same fact sharply degrades copying. Changing only the fact sentence largely preserves it. Typical failed replies include a bare hour such as`21` rather than`21:20`, or an unrelated word. This supports dependence on an instruction/order pattern in this checkpoint. It does not establish which representation or optimization mechanism caused that dependence, and one alternate instruction is not representative of all paraphrases.

### History propagation is not the dominant issue on this small state packet

| Checkpoint | Generated-history turns | Gold-history turns | Complete conversations, generated/gold |
|---|---:|---:|---:|
|Original foundation|0/24|0/24|0/8,0/8|
|Factual child A|24/24|24/24|8/8,8/8|
|Broader child B|19/24|19/24|4/8,4/8|
|Grounding adapter|24/24|24/24|8/8,8/8|

The state packet uses familiar narrow update forms; success does not establish natural multi-turn dialogue. Original foundation/A/B score zero exact full-name/time answers across this packet, but “seen” was defined relative to the grounding adapter, so cross-checkpoint differences cannot be attributed causally to one intervention. Within-checkpoint matched contrasts carry the useful diagnostic signal.

## Readiness decisions

| Gate | Status | Consequence |
|---|---|---|
|Structured labels, prefix/mask/shift, pairing and counterfactuals|PASS|Prepared-v2 is mechanically usable as a diagnostic candidate|
|Same facts, different attribute questions|PASS|400 shared worlds across four attribute tasks; all eight tasks remain balanced|
|Budget/zero-update enforcement and immutable historical weights|PASS|Inference results are valid under the declared resource scope|
|Separate-agent blinded acceptance calibration|COMPLETE, scoped|20/24 agreement; four borderline labels revised; no human validation|
|20 independent linguistic families per task|NOT ESTABLISHED|There are 20 candidate strings, not a verified independent-family taxonomy|
|Representative natural final benchmark|NOT READY|240 templated candidates use six main flows; need broader independently reviewed scenarios|
|Natural generated-history context guarantee|FAIL at current 48-token allowance|78/714 candidate turns and 6/60 anchor turns can exceed 256 under worst-case generated histories|
|Training authorization|NOT GIVEN|No calibration updates, optimizer sweep or PhaseB arm may start|

The context finding is conservative headroom, not observed overflow. All gold histories fit. The prerequisite packet itself fits under its 32-token allowance, so a bounded prerequisite study could be scoped separately once the review/taxonomy issues are resolved; it need not wait for a full natural-chat context extension.

## Revised next step before training

1. Apply the completed blind-review adjudication prospectively, including the reminder-writing distinction. Add real interruption-and-return cases: the current fourth-turn weather question does not test earlier-state recall. Do not retroactively change old campaign grades.
2. Freeze an honest instruction-diversity definition. Either independently establish the proposed family taxonomy or revise the future comparison to “20 surface variants plus balanced order” without claiming 20 independent linguistic families. Both arms already balance order, preventing order coverage from becoming a hidden treatment difference.
3. Keep the current 240 natural cases as development/context fixtures. Build a broader independent final set later; do not silently declare this prototype representative.
4. Choose whether the immediate next experiment is the short prerequisite pilot or the full natural-conversation target. For the latter, validate context headroom first. No automatic context increase or decoder-cap reduction was made.
5. Recompute the PhaseB budget for its actual grouped training implementation and full evaluation schedule. Inference timings here do not certify backward-pass throughput or a three-hour training ETA.

The data-diversity hypothesis now has a concrete, narrower target: **instruction interpretation and position robustness while preserving task selection**. This supports testing the planned controlled diversity/replay comparison; it does not justify skipping its control, choosing a larger model, or claiming that broader pretraining is unnecessary.

## Review limitations

Primary agent authored the packet and performed deterministic/semantic construction checks. A separate blinded model agent reviewed the 24 anchors on 29 October; human validation and independent review of the remaining curriculum and natural candidates are still absent. The inference sample uses eight convenience-selected facts per cell, with one changed prompt form and a focused two-level follow-up. Report paired counts, not population confidence or broad capability percentages. Final-test payloads were never used for inference, and no student response was used to alter a frozen scored case. Version 2 is a prospectively separate preparation improvement; frozen v1 and both inference manifests remain intact.
