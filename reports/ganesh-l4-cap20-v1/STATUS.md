# Ganesh-base: $20 L4 campaign closeout

18 November 2026 IST. **Qualification HOLD; zero VMs/disks remain. English pilot did not start.**

## Allocation and execution

Original us-central1-a failed capacity. User then explicitly authorized other zones under the same cumulative $20 cap. New requests in us-central1-b/c and us-east1-b/c/d failed capacity and were individually reconciled. One L4 succeeded in us-west1-a: ganesh-l4-1117-185840. Zone checks stopped immediately. One earlier local preflight failed because a composite GCS runtime has CRC32C instead of MD5; the reuse check was corrected before allocation, preserving the prior SHA256 readback.

Actual uninterrupted two updates and separate one-update + GCS restore + one-update branches completed. Supplemental full-state comparison passed exactly: 159 tensors, 1,409,489,630 elements, zero tensor/metadata mismatches, zero nonfinite elements, equal quality-loop state. The selected Muon capture inputs, outputs and context also match exactly. This is a scoped L4 result, not resolution of the historical A100 mismatch or conversation acceptance.

Fresh eager replay failed its environment guard before kernel execution. The CLI did not restore the captured CUBLAS_WORKSPACE_CONFIG=:4096:8 setting from the SFT child. The English pilot remained blocked. Signal recovery, upload rejection, provider-STOP drill and decode-throughput qualification did not run. Normal shutdown was observed; it is not the provider-STOP fault drill.

## Correction and limits

The local CLI now restores or unsets the captured CUBLAS workspace setting before CUDA runtime use. A real subprocess regression covers missing/conflicting inherited values. **203 targeted tests pass.** A new runtime was built and independently extracted/source-verified; see fixed-runtime-readback.json. It was not deployed or GPU-qualified. Original runtime and captures remain immutable. Old captures require the original hash-bound source and a matching launch environment, not rewritten manifests.

All 52 frozen data files remain unchanged. No English fit/curriculum pilot, release review, serving-default change or HTTP start occurred. Existing local model weights remain available. Full RCA: REPLAY_ENV_RCA.md.

## Backups and retirement

Three distinct checkpoint states were uploaded and fully read back on the VM. The 2.5GiB-class evidence archive includes both raw GPU captures, traces, logs and the supplemental comparison; its SHA256 and both capture payload sets were independently verified again after download locally. Archive: runs/ganesh-l4-cap20-v1/qualification-evidence.tar.gz. GCS prefix: gs://forge-ownbase-a100-20261110/ganesh-l4-cap20-v1/ganesh-l4-1117-185840/.

Closeout recorded verified GCS backups at19:36:01UTC. Provider stop timestamp19:37:28UTC. After local verification, the stopped VM,200GiB disposable disk and temporary IAP-only SSH rule were removed. Fresh inventories at19:45:24UTC confirm zero VMs/disks. No GCS data or selected local weights were deleted. Receipts: attempts/us-west1-a-185831/retention-receipt.json and retirement-receipt.json.

## Spend and next gate

Observed VM runtime2263.227seconds: estimated VM compute **$0.53665**. Disposable-disk estimate is recorded separately in spend-ledger.json. GCS storage/transfer charges remain unsettled; these estimates are not the final invoice. No active compute/disk reservation or retry job remains. The $20 cumulative cap was not increased.

Next work is CUDA validation of the replay correction and remaining recovery/fault/throughput checks, with a fresh immutable request and complete budget reconciliation. The failed request cannot be replayed or relabeled passed. Any continuation must respect the approved campaign deadline and cumulative ceiling; no automatic qualification retry or English-pilot dispatch follows this partial result.
