# Campaign outcome: capacity HOLD before GPU execution

Prior follow-up review/handoff pushed to main as50defa5. New user approval is $15 total incremental spend with L4 or A100 permitted; the old L4-only/no-cap restriction is superseded.

## Plan and second review

PLAN.md reserves $5 for qualification, $6 for conditional fit and $4 for disk/GCS/transfer/recovery. A100 was selected to reproduce the historical A100 exact-resume discrepancy without a hardware change. Current official listed rate used: $3.673385/hour; one60minute lease reserves $4.59173125 with25%margin. No claim this is the cheapest learning GPU. Standard provisioning, private VM, fixed absolute provider STOP, retained disk, no automatic restart and no pilot in the qualification worker.

Checks passed:56focused tests;41frozen inputs unchanged;148runtime members read back and hash-checked;3local model bundles validated;5actual worker argument branches inspected. Existing local evidence includes160broader tests; they were not rerun here. Runtime/packet GCS copies were independently downloaded and hash-verified before the first create request. A local preflight initially rejected the macOS temporary-directory symlink; resolving the path corrected that local check without weakening the extractor. No GPU existed at that point.

The launch guard rechecked input/source hashes, active VM inventory, deadline and reservation immediately before the API call. The worker pins tracing, cadence1, seed103, packing1 and finite one/two-update branches; all remain untested on actual CUDA in this campaign. It would stop on any exactness mismatch and cannot launch the fit pilot. Fresh0->1 versus restored0->1 is exercised by the signal-restored branch after the normal2vs1+1 comparison; all required observations remain identity-bound.

## Provider results

- us-central1-f: create operation DONE with ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS. GCP suggested us-central1-a.
- After verifying no created VM/disk, ZONE_FALLBACK.md reviewed one same-machine/same-rate fallback using the original18:13:22UTC provider deadline, without extending runtime or borrowing the fit slice.
- us-central1-a: create operation also DONE with the same capacity error; no alternative zone reported.
- Final inventory: three historical VMs TERMINATED; zero new VM/disk. No worker ran, no training/checkpoint generated, no model quality change. Exact recovery, upload-fault and provider-STOP tests have not passed.

Async create returning0 means only request acceptance. Both operation error results were checked; neither is called a successful launch. The empty failed describe outputs were removed; operation records and final inventory remain.

New observed GPU compute cost: $0. Active compute reservation: $0 after reconciliation. GCS staging/readback/storage/operation costs are nonzero and not invoice-reconciled; the $4 reserve remains allocated for them. The full $15 is not falsely described as untouched. No budget alert is treated as a hard cap. Existing historical storage costs continue separately from this incremental attempt.

## Data, backup and next step

Eight more TRAIN conversations/24responses reviewed in reports/oasst-memory-remaining-v1; zero retained,48prefix checks passed. Prior four candidates/595targets remain unadmitted. Frozen fit and all other41frozen files unchanged. No sealed release or serving changes. Local weights remain intact, HTTP remains off.

Input backup proof is in input-backup-receipt.json. Final evidence archive/readback proof is in final-backup-receipt.json when completed. No shutdown or new-weight backup was necessary because no VM/worker existed. Do not infer new verification of every historical GCS object from this task.

Approval remains recorded; no additional cap is requested. This attempt is closed with no scheduled retry. A future attempt must reconcile storage/transfer spend and create a new reviewed finite request within the remaining approval; never reuse these closed requests. L4 remains allowed, but switching hardware needs actual qualification and a reviewed runtime/cost plan, not bypassing the unresolved recovery gate. A100 availability is not proof of readiness either. Keep fit blocked until all qualification gates pass.
