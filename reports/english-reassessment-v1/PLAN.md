# Own English reassessment — compute stopped

17 November 2026. User instruction: kill everything and reassess. **No automatic restart, retry or further paid experiment.** The previous $15 approval is not permission to resume after this stop instruction. Subsequent authorized cleanup deleted all four VM records and three disks after verifying required backups. Selected models and required GCS artifacts remain; no local retry/training or HTTP process is active. See reports/gcp-cleanup-20261117/REPORT.md for current retention.

## Decision

Stop broad corpus searching and cloud qualification loops for now. The next work should answer two separate questions: (1) why does the optimizer produce different results after restart, and (2) can Own learn the frozen short English examples at all? Neither more organic rows nor another GPU allocation answers both. The project has repeatedly spent on infrastructure diagnosis without completing the bounded English learnability experiment. That is a sequencing problem, not a reason to relax quality.

## New evidence from the existing run

The local `analyze_trace.py` reads only the saved hash-verified evidence archive; no training, downloads of weights or cloud mutations are needed. It aligns semantic event/step boundaries rather than comparing raw trace-file positions across a restart.

- All12recorded boundaries in two independent fresh first updates match.
- In the resumed second update, the before-collection state, all four input/label and gradient observations, and immediately-before-optimizer state match the uninterrupted branch.
- The first recorded difference is **after optimizer.step()**:16model tensors and1optimizer tensor. They are the MLP output projection weights and a factored second-moment buffer.
- Recorded model/optimizer fingerprints include tensor content/layout; RNG and packing snapshots also match before the update. This is strong localization to optimizer execution, not proof that every private temporary, compiler cache or internal kernel input is equal.
- Maximum weight/state absolute difference is4.3847e-6;54,869,350elements differ; no NaNs/Infs. A large mismatch count is not a measure of conversational harm.
- Aggregate development CE is4.202723798 versus4.202542806: absolute difference0.000180992, approximately0.00431%. All quality guards still have zero strikes and stopped=false in both branches. Their numeric loss histories differ; **their stop decisions do not**.
- The pinned upstream optimizer uses compiled fused Muon and AdamW functions. Compilation, temporary buffer construction or another internal optimizer path is a plausible lead, not an established root cause. Do not attribute this to compiler nondeterminism without a controlled reproduction.

Backup integrity and continued numerical identity are different claims. Four surviving bundles were uploaded/read back and validated by the worker; local evidence archive hash matches the GCS closeout receipt. This run does not establish checkpoint corruption or data loss. Conversely, small numerical differences alone do not prove resumed training is safe over a long trajectory.

PyTorch documents platform/version limits and deterministic-operation controls: https://docs.pytorch.org/docs/2.9/notes/randomness.html . This is background, not an explanation of a same-version/same-device failure and not permission to waive the current exact gate.

## What should change

### 1. Finish local diagnosis before another GPU request

Build a minimal optimizer-step reproduction from the retained checkpoint/gradient evidence, targeting the failing projection group. Existing traces contain hashes, not raw gradients: a new replay may be needed to materialize exact gradients; do not pretend hashes can reconstruct them. First inspect parameter ordering, optimizer group membership, temporary/scalar tensors, dtype/stride, accumulation and schedule values against saved state.

Prepare paired tests that change one factor: compiled versus eager optimizer execution; fresh versus restored optimizer; model compilation held fixed. Preserve the base optimizer moments. Do not simultaneously reset optimizer, change LR, hardware and corpus. Test serialization/reload identity exactly, and capture actual fused-kernel inputs/outputs if another CUDA reproduction is eventually approved. A local CPU test can verify plumbing, never CUDA equivalence.

Deliverable: a reproducible hypothesis and small diagnostic harness, with explicit expected distinguishing outcomes. No more full checkpoint-transfer campaign merely to rediscover that final tensors differ. Bound future diagnosis to one predeclared experiment; failure returns to local review rather than automatic retries.

### 2. Keep three separate gates

- **Durability/control:** exact saved/loaded state and input hashes, complete optimizer/RNG/data/schedule recovery, truthful upload receipts, one writer, finite STOP and backup failure recovery. These remain nonnegotiable.
- **Numerical continuation:** the current exact-restart gate remains failed. Prefer fixing/simplifying the diagnosed optimizer path. Any proposed tolerance-based criterion must be justified from controlled repeatability measurements and defined before a new run; never choose tolerance from this failure or relabel it a pass.
- **English capability:** generated multi-turn behavior. A durability or numerical pass is not model acceptance; loss decreases do not establish conversation quality.

An uninterrupted, no-resume fit diagnostic could theoretically isolate learnability from recovery, but it would require a separately reviewed contract: checkpoint export still verified, interrupted runs never resumed, no promotion, and explicit user resumption. It is an alternative proposal—not a bypass implemented now.

### 3. Make the next learning experiment answer one question

After local diagnosis and explicit user resumption, aim to complete exactly one frozen24-session/72-turn English fit diagnostic. Keep the existing native2K format, input hashes, 64update/64epoch ceiling, LR<=.25, packing1 and regression stops. Do not use the external-source shortlist or modify the frozen set. Predeclare parent and optimizer policy.

Evaluate raw generated conversations at0/16/32/64when reached, plus best/last, with actual generated histories. Preserve blocked/invalid turns in denominators. The existing >=23/24complete-session, zero-invalid/forbidden-action fit gate remains. If fit fails, diagnose protocol/end-token/optimization versus foundation limitations; do not spend on broader data. If fit passes, test transfer before any production curriculum/release decision. Two failed learning pilots force HOLD; infrastructure failures are recorded separately and are not misleadingly called failed completed fit pilots.

### 4. Put cost and observability ahead of allocation

Before future paid work, show measured startup, compilation, training, evaluation, checkpoint upload and readback timing separately. A60minute lease is not60minutes of useful learning. Require working remote status and a stage heartbeat before starting the expensive phase; SSH failed in this run, and sparse GCS checkpoints were inadequate progress visibility. Fix access or provide a tested GCS status fallback without broad firewall/IAM changes.

Use a supervising process that follows allocation through qualification, backup and termination; a capacity loop that exits at allocation is not end-to-end hands-off execution. Detect failures promptly, persist status, and publish concise progress at the requested cadence. Provider STOP and retained recovery disk remain independent safeguards.

The last successful allocation cost approximately$2.2077compute before storage/transfer, not an invoice total. Retain the reserve and reconcile all retry staging costs. Do not infer the full remaining balance from $15minuscompute alone. No lease extension for failed qualification. Future cap and scope must be explicitly reconfirmed after this stop instruction.

### 5. Resume curriculum work only when it serves measured failures

Four OASST candidates /595targets remain unadmitted and only two turns long. Recent three-turn discovery yielded no suitable correction-retention/delayed-memory additions. Pause that low-yield search; do not lower full-path quality. After fit GO, build a small, explicitly state-tracked generated correction/memory set alongside reviewed organic examples, with provenance, split-by-scenario, independent test cases and full per-turn review. No volume target, no4K expansion, no maths/CBSE yet.

## Immediate deliverables completed

Compute/process inventory checked; capacity state disabled with explicit STOPPED_BY_USER marker; trace comparison recorded in trace-analysis.json; handoff and next steps updated. No model, corpus, objective or acceptance threshold changed. Existing release sets remain unused. This plan makes no claim that Own will reach usable English; that remains the experiment's unanswered question.

## Local optimizer follow-up, 17 November

The reduced-shape BF16-compute CPU harness in reports/optimizer-isolation-v1/probe.py passes exact fresh-process continuation in both eager and compiled modes, including fused argument/output and serialized-state comparisons. A deliberate perturbation is detected. This does not reproduce the A100 failure or qualify CUDA. See ASSESSMENT.md there for limitations and the actual-input capture/replay specification. No production optimizer, weights, corpus or release criterion changed.

## Actual-input harness follow-up

Implemented and locally checked; see reports/optimizer-capture-v1/READINESS.md. Both CPU replay modes are internally repeatable; compiled replay matches captured output while eager differs reproducibly. No CUDA root cause or English improvement is claimed. Actual failing GPU tensors still require a new approved capture run. New runtime and evidence are local only; no cloud allocation or cap extension.
