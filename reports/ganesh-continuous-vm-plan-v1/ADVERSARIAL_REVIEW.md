# Adversarial review: Ganesh-base recovery proposal

Historical review retained. The superseded proposal files were consolidated into ../ganesh-launch-readiness-v1/LAUNCH_PLAN.md; current results are in ../ganesh-launch-readiness-v1/ADVERSARIAL_REVIEW.md.

17 November 2026. Verdict: **reject the previous plan as a launch-ready contract**. It is a useful program outline with serious execution and evidence loopholes. Same-assistant adversarial review; not an independent audit. Reviewed RECOVERY_PROGRAM.md, PLAN.md, authoritative handoff, frozen diagnostic contract/experiment card and actual nano_sft scheduling interfaces. No training, cloud mutation, evaluation exposure or source-code change performed.

## Findings and disposition

| Severity | Attack/failure path | Consequence | Required correction |
|---|---|---|---|
| Critical | Exact resume fails; no-resume fit passes; generic stage queue advances to production/release | Diagnostic exception becomes an unapproved production bypass | Separate terminal diagnostic branch. No-resume may run frozen fit only, then backup/STOP. Production requires all original qualification gates. |
| Critical | Provider STOP is only tested at final shutdown | Entire training campaign runs before its safety mechanism is qualified | Qualify STOP before production, accepting a controlled stop/restart if needed; count it inside the unchanged lease. Literal uninterrupted service cannot trump this gate. |
| High | $50 buys an arbitrary40hour ceiling, without admitted data or measured generation/transfer work | Budget appears engineered while actual completion probability is unknown | Withdraw launch recommendation until workload, SKU bill and stage sublimits are bound. No claim$50is minimum or sufficient. |
| High | Author generates, reviews and scores examples; percentages have undefined populations | Self-confirming success, easy prompts hide weak context behavior | Fixed category counts, scenario-group split, distinct review provenance; no independent acceptance claim without independent review. |
| High | Invalid first answer blocks later turns; denominator drops them or reruns until success | Inflated conversation score | Lock all scheduled turns, blocked-turn accounting, decoding and rerun policy; retain every raw attempt. |
| High | Choose base or fit checkpoint after observing results, with unspecified LR/schedule | Hidden model search and confounded curriculum result | Fix production parent to immutable base10B; bind optimizer and schedule before launch. |
| High | Tiny fit fails under64updates; conclude foundation cannot converse | False negative caused by budget, framing or insufficient optimization | Report failure under this recipe only. No automatic expansion, but also no claim of inherent incapability. |
| High | Good global English score masks weak long-history/correction cells | Release of a model still failing the user's main requirement | Conjunctive category gates, short/long strata, full generated-history tests, numerical counts and uncertainty. |
| High | Data plan promises2,000quality sessions despite low-yield organic review | Volume pressure encourages paraphrase duplicates, filler and weak references | Counts are conditional design targets; group-level provenance/review and actual target/packing exposure must pass first. |
| High | Uploaded checkpoints pass metadata checks but cannot load, or controller/worker share failed auth | Apparent backup/safety with no usable recovery | Fresh-process restore of GCS-readback payload; explicit dependencies and credentials, disk retained on failure. |
| High | Desktop sleeps, controller restarts, lease resets; capacity retry creates second VM | Cost overrun or concurrent writers | Fixed provider deadline, persisted lease/campaign ID, one-resource allowlist, restart/sleep tests and retry reconciliation. |
| Medium | 5%identity mass repeats two facts excessively | Identity memorization displaces English; unrelated replies mention identity | Treat5%as ceiling, report distinct target/exposure counts, include unrelated-task controls. |
| Medium | GPU remains allocated for local download/manual scoring | “Nonstop” becomes paid idle time | Finish cloud-essential work then STOP; local review/MPS checks may continue afterwards. |
| Medium | Frozen tests/templates leak into new generated data | Passing release does not show transfer | Audit all exposed historical probes, whole scenario groups and template families; new final suite locked before training. |

## What changed in the plan

Added controlling restrictions and an executable-receipt specification; separated no-resume diagnostic from production; fixed the production parent; specified proposed final-suite strata, candidate selection, blocked/error accounting and runtime invariants; tightened restore, lease and identity-mass requirements. Marked old PLAN.md historical. Handoff now records HOLD and this review.

These are documentary corrections. No launcher, contract, independent review system or new curriculum was implemented by this task. Existing frozen contracts/inputs and model weights were not edited. The source code's --max-updates and finite-epoch controls alone do not implement these new stage transitions.

## Acceptance tests required before launch

1. Simulate exact-resume failure + passing frozen fit: production stage must remain unreachable.
2. Simulate expired/mismatched runtime or contract hash: no worker launch.
3. Simulate failed fit or unresolved semantic review: no curriculum or release consumption.
4. Simulate controller restart/sleep: absolute deadline unchanged, no duplicate allocation/writer.
5. Simulate transfer slowdown, full disk, corrupt upload, credential expiry: preserve last-good copy; initiate bounded shutdown; retain recovery disk if required.
6. Simulate no backup reserve at next stage: stage refused, not shortened evaluation or extended lease.
7. Feed blocked turns, invalid frames, multiple attempts and harness errors to evaluator: none silently disappear or improve score.
8. Attempt model selection after viewing release outputs: refuse reuse for another candidate; preserve exposure record.
9. Restore real selected payload from verified GCS readback and load in fresh process; separately qualify local MPS.
10. Prove actual provider STOP before production. Its final observed shutdown is an outcome check, not prior qualification.

No claim these tests passed. Full independent semantic review is still a staffing/tooling blocker; this task did not delegate work or pretend a second read is independence.

## Decision

Do not request or spend a larger cap to compensate for unspecified work. First make data, scorer, contracts, lifecycle and workload concrete locally. Then price the queue and seek a finite cap. The prior$15/$50figures remain illustrative envelopes, not verified cost-to-completion estimates. A small diagnostic-only campaign may be worthwhile before preparing the full broad curriculum, but that is a separate scope choice, not a license to train production from diagnostic approval.

No promise of zero exceptions, zero data loss, zero invoice overrun or guaranteed English proficiency is supportable. Honest success is a correctly measured, reproducible result with retained weights and evidence; release additionally requires the predefined capability gates.
