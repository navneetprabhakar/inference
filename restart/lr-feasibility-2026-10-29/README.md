# Learning-rate, feasibility and preservation reassessment — 29 October 2026

**Calibration passed; common LR selected: 5e-4. Retained training has not started. The original 90-minute study ceiling is not supported by the conservative runtime projection.**

[Calibration results](result.json) · [Feasibility assessment](assessment.json) · [Preservation decision](PRESERVATION_DECISION.md)

## Completed authorized work

Six disposable runs, 100 updates each: three predeclared learning rates (2e-5, 1e-4, 5e-4), each with replay coefficient 0 and 0.5. Every run started from the same original foundation with fresh optimizer state, identical diverse-curriculum order and seed. The earlier 12-update calibration was explicitly imported once into the aggregate study ledger; its capped source ledger remains unchanged.

All six completed with finite parameters, losses, gradients, update norms and checked optimizer moments. Common-LR selection used only an independently sampled **training** probe of eight examples per task, never development/final performance. Each task's endpoint/source loss ratio had to be <=1.10 under both replay settings; late mean training loss also had to be <=1.10 of early mean loss. Among eligible rates, select the lowest mean task-loss ratio across both settings, breaking ties toward lower LR. The rule was frozen before execution.

| Learning rate | Mean endpoint/source task-loss ratio | Eligible |
|---|---:|---|
|2e-5|0.2979|Yes|
|1e-4|0.1176|Yes|
|5e-4|0.1111|Yes — selected|

Lower ratios are better. The margin between 1e-4 and 5e-4 is modest, and 1e-4 was slightly better in the no-replay condition alone. The declared common-rate rule still selects 5e-4. This is not evidence that it is universally optimal, stable for 1,000 updates, or better on unseen instructions. Calibration checkpoints remain disposable; retained arms must start from the original foundation, not the selected calibration child.

New work: **600 optimizer applications and 124.93 active-model seconds**, including timing checks. Cumulative study accounting: **612 updates, 1,391,872 positions, 29,416 assistant/EOS targets, 626,688 narrative targets and 139.26 active seconds**. A reservation for the 601st new calibration update was rejected without work. Exactly 4,000 retained updates remain in the proposed 4,612-update envelope. No old exhausted ledger was reset.

## Feasibility

The measured main-training estimate is approximately 817 seconds using the slowest observed p95 update time for each replay setting across all learning rates. That is only part of the cost. Full evaluation can require 309,248 autoregressive forwards if every reply reaches its 32-token cap.

The conservative projection uses the largest measured per-forward latency from training-token prefix timing for every generated token, even shorter contexts. It includes the full source/sentinel/endpoint schedule, held-out native NLL, carried calibration time, and a 25% reserve on remaining work:

- **121.2 active-model minutes projected**, exceeding the proposed 90-minute ceiling.
- **40,909,360 input positions** in the no-early-EOS accounting bound, below 50M.
- **221,052 assistant/EOS targets and 4,722,688 narrative targets**, below the proposed caps.
- Current calibration artifacts occupy about **1.02 GiB**; checkpoints and raw outputs remain private.

This is a conservative empirical planning envelope, not proof that the real run would take over 90 minutes or a guaranteed runtime. Shorter contexts and early EOS may materially reduce cost. Single-device timing and the first 100 training batches do not establish all future performance; checks remain necessary during execution. No natural-dialogue generation or additional seeds are included in this envelope.

**Proposed budget change:** raise only the active-model ceiling to **150 minutes total**, carrying the 139.26 seconds already consumed. Keep the four arms, 1,000 updates per arm, all evaluation cases, 50M positions and other resource limits unchanged. This provides margin above the conservative estimate without dropping the last arm or weakening evaluation. The larger ceiling is proposed, not authorized or applied. The frozen old launcher still has a 90-minute policy; never silently alter an existing ledger's policy row.

## Preservation decision

The foundation's 0/80 conversational behavior baseline cannot support a five-point no-regression gate. That result remains INCONCLUSIVE. Keep the cases as acquisition evidence and use the frozen native narrative validation set to quantify retention of the foundation's trained distribution.

The next screen is explicitly **acquisition-versus-native-narrative-retention research**. Keep acquisition thresholds unchanged; report native NLL and its change alongside acquisition for every arm, including failures. Do not turn the historical +5% NLL line into an automatic stop or promotion rule. Do not call an acquisition-qualified point “preservation passed.” Keep the original source and compare the full tradeoff; no checkpoint is promoted automatically. The [decision](PRESERVATION_DECISION.md) was fixed without consulting development scores.

This resolves the operational policy for the research screen, not the eventual preservation requirements for a usable conversational model. That later claim still needs representative behavioral evidence.

## Readiness and next decision

- Engineering optimizer/resume calibration: passed in the previous 12-update phase.
- Common LR: selected at 5e-4 using training-only evidence.
- Preservation scope: explicitly resolved as research tradeoff, no production acceptance claim.
- Position/target budget: fits the complete declared schedule under the calculated bound.
- Active-time budget: request 150 minutes rather than assume 90 will suffice.
- Retained training: **not approved, not started**.

Before a retained launch, prepare a new frozen launch revision implementing the approved preservation policy and, only if authorized, the 150-minute ceiling. Create a reconciled successor ledger with one audited import of all 612 updates and associated charges/time; preserve the current ledger and its policy unchanged. Scope artifact checks across the entire successor study directory, not only the historical runner directory. Verify the launch revision and charge import before its first update. Use fresh source weights for all four arms and retain endpoint-only comparison.

No additional calibration or retained updates are implied by this report. Human input needed next is approval or rejection of the proposed retained research screen and its revised time ceiling.
