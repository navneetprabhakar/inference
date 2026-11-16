# $15 Own English campaign — qualification before learning

User authorization: 16 November 2026, new $15 total incremental campaign cap; L4 or A100 allowed. Prior closed leases remain closed. This authorization supersedes L4-only/no-cap notes; it does not override quality gates or authorize model release.

## Decision and second-pass review

Use one standard A100 40GB (`a2-highgpu-1g`, us-central1-f) qualification attempt. Rationale: reproduce the unresolved A100 CUDA signal-resume discrepancy on the same GPU class, using the newly instrumented runtime. This minimizes hardware changes during diagnosis; it is not a claim A100 is the cheapest training GPU. L4 remains eligible for a separately qualified later phase. No automatic fallback, retries or concurrent GPU allocation.

Official pricing checked on this turn: https://cloud.google.com/products/compute/pricing/accelerator-optimized lists A2 standard a2-highgpu-1g at $3.673385/hour. Verify region/machine/image before creation. Reserve 25% compute margin. Standard provisioning avoids deliberately introducing Spot eviction during recovery diagnosis.

| Allocation | Maximum reserved cost |
|---|---:|
| Qualification, including 25% margin | $5 |
| Bounded learning, gated and not launched by qualification worker | $6 |
| Disk, GCS, transfer, backup/shutdown uncertainty | $4 |
| Total new campaign | $15 |

First qualification lease: at most60minutes from request preparation, computed reservation $4.59173125. Bootstrap, compilation, training diagnostics, traces, uploads and readbacks all consume that clock. No deadline resets. Training diagnostics stop well before provider expiry; reserve final15minutes for recovery/evidence. Create request only after input staging/readback succeeds. Explicit provider STOP, no boot-disk auto-delete; no delete-on-timeout. Unused slices stay unused. The reserve is not extra training money. Existing historical storage costs are not reset by this incremental campaign.

## Execution order

1. Commit/push existing source review (done:50defa5). Keep reviewed OASST data separate from frozen fit; no admission or corpus changes.
2. Read-only inventory, image/subnet checks, exact local checkpoint/runtime/frozen-file hashes, focused restart/trace/retention/lease tests. Two-pass review: inspect worker/config/lease before creation, then recheck exact hashes, finite deadlines, cumulative reservations and cloud inventory at launch.
3. Stage the exact runtime/packet to a new immutable GCS prefix; download and hash-verify both. Existing base must remain locally intact and the GPU must independently read/validate its full GCS bundle before use.
4. Qualification only: traced fresh0->1 versus GCS-restored0->1, exact2vs1+1 with cadence1, real mid-accumulation SIGTERM and rollback/resume. Bind tracing and packing-buffer1 to model identity. Compare complete model/optimizer/RNG/data/quality state without tolerances. Stop qualification on first failure; preserve traces and all surviving bundles. Do not try to repair a failed run in place.
5. Only if exactness passes: actual GCS upload rejection/recovery and independent provider STOP fault drill, under the same remaining qualification slice or HOLD if insufficient. Normal shutdown alone does not qualify provider STOP. A separate bounded action is required; qualification worker cannot launch a fit pilot.
6. Only after every qualification gate passes, measure remaining budget and stage a new hash-bound fit lease within the $6 learning slice: frozen24-session fit, native2K, <=64updates/64epochs, LR multiplier<=.25, packing1, development regression stops; preserve0/16/32/64when reached plus best/last. No silent budget, epoch or LR extensions.
7. Review all72fit turns and complete sessions using actual generated histories; blocked turns remain failures. Fit GO requires >=23/24complete sessions and zero invalid/forbidden actions. Then exposed development/local MPS review; no release or serving promotion. Two failed learning pilots force diagnosis/HOLD. Qualification failure blocks learning immediately.
8. Before normal shutdown, join writers and independently download/hash-validate required GCS checkpoints and evidence. Backup failure still triggers finite compute STOP while retaining the disk and local sole copies. Retrieve final useful weights/evidence to local and verify bundles before any cleanup. Do not delete retained historical copies.

## Guardrails and honest limits

- Financial control is reservation plus absolute provider termination, not a delayed billing alert. Record actual lifetime and reserved cost; service latency, taxes/exchange rates and ongoing storage mean no promise of an exact final invoice or zero failure.
- One writer, private VM/no public HTTP, offline package/dependencies, immutable source identity. No broad IAM change or destructive recovery test.
- Fail closed on checksum, runtime, context, schedule, exactness, disk-space, upload, ledger or deadline mismatch. No model-quality claim from loss or job exit.
- Updates roughly30minutes during paid execution, immediately on failure/budget risk/completion. Local source review may continue while compute is off; no weak examples added to satisfy volume.
- All old evidence/receipts stay immutable. Current handoff supersedes old authorization/authentication status. Auth now works and all three retained VMs were observed TERMINATED in this turn.
