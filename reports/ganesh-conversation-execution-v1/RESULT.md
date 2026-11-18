# Controlled conversation attempt — HOLD

18 November 2026. Approved incremental cap: $25. **English pilot did not run. No model improvement or release acceptance is claimed.** Cloud retirement and estimated compute charges are recorded in `cloud-closeout.json`.

## What happened

1. The reviewed corpus and controlled block replay passed local admission and CPU tests. Frozen corpus/fit/release artifacts remain unchanged.
2. Initial A100 allocation in us-central1-c failed capacity. Inventory was reconciled to zero before the provider-suggested us-central1-f attempt. One A100 ran, under the original absolute stop deadline.
3. Qualification v1 failed before optimizer updates: the worker omitted the mandatory `/checkpoints` namespace. Tests mocked the trainer entry point and therefore did not exercise the journal validator. Original evidence was retained; one isolated repair added fail-fast CLI validation and a real namespace check.
4. Qualification v2 completed the continuous two-update branch and the first one-update split branch. The split checkpoint upload then timed out: the 120-second checkpoint reserve left 72.0058 seconds for payload copy. The qualification worker failed after 705.935 seconds. It did not reach restore/continuation, signal recovery, upload-fault drills, decoding measurement, or either English pilot arm.
5. After the second failure, execution entered HOLD. No additional VM retry or pilot was launched. All four checkpoint bundles were backed up and independently read back with SHA verification. The interrupted split checkpoint was recovered into a separate namespace without rewriting its failed journal. Compact evidence was also downloaded and hash-verified locally before shutdown.

## Root cause and responsibility

The immediate failures were orchestration defects: an invalid namespace and an inadequately measured checkpoint deadline. The local tests proved packing/control-flow invariants but did not establish operational timing readiness. The planned fifteen-minute qualification allowance did not adequately account for cold loading, repeated validation, checkpoint publication and readback. These planning and test-coverage errors consumed GPU time without producing the intended English experiment; they are not evidence of a bad GPU or of the new corpus failing to teach conversation.

The current model limitation remains poor generalization from the earlier narrow fit curriculum. This attempt adds no conversational evidence to that diagnosis. Three disposable qualification optimizer updates are not a completed English pilot.

## Remediation completed locally

- Backup-prefix validation occurs before model loading; worker commands are checked against the real journal namespace validator.
- The recovery uploader now rejects non-finite/non-positive timeouts before side effects and uses one absolute deadline across local validation, upload and independent readback. Expired validation cannot initiate a cloud upload. COMMITTED remains last.
- 222 local tests pass: 212 regression and 10 controlled-path tests. Frozen packet validation and whitespace checks pass.
- **The timeout remediation is local only, not GPU-qualified or part of deployed runtime v2.** No historical receipt has been relabeled as qualification of the changed implementation.

## Before another launch

Package the changed runtime; exercise real subprocess timeout/recovery behavior; budget all measured cold starts, hashing, transfer/readback and evaluation costs. A future qualification must prove exact CUDA 2-versus-1+restore+1 continuation, signal rollback, and upload-failure behavior before either pilot. A normal early shutdown does not establish scheduled-provider-STOP fault behavior.

Do not extend training or increase the cap to compensate for these failures. Establish a credible bounded timing forecast first. Both forty-update arms and all prescribed parent/best/midpoint/last behavior reviews remain outstanding. Policy-mode exposure differs slightly between arms, so even a completed experiment compares curriculum mixtures rather than proving a pure diversity effect.

## Retention

`recovery-backups.json` identifies all four verified GCS checkpoint bundles. `local-evidence-readback.json` binds the locally retained evidence archive to its verified GCS SHA. Existing Fit30 and serving-default weights remain local; HTTP and serving defaults are unchanged. Qualification checkpoints are diagnostic recovery artifacts, not promoted models. Historical runtime v1/v2 archives and failed journals preserve reproducibility.

No commit or push was performed in this execution turn.
