# Ganesh-base English campaign — closed on quality hold

The A100 run trained Own/Ganesh-base weights and failed conversation acceptance.
The VM and its boot disk have been removed after verified backups. No training,
retry or allocation is pending. The approved cumulative cap was $40.

- Fit stopped at update30 on persistent development regression guards. No curriculum
  training ran. The original failed controller state remains intact.
- Last30:64/72exposed-fit turns,21/24complete sessions; unseen development2/36turns,
  0/12complete sessions. Best-loss20:0passing conversations. All396English records
  and24protected-tool records were reviewed; this was not independent release.
- Actual learning issue: answer words fit before termination learns. At20the end
  token is never top1at reference endings; at30it is top1for65/72fit and26/36dev.
  Packed and isolated diagnostics agree on fit end-token counts. Generalization
  remains poor after termination improves. See ENGLISH_RESULT.md for the RCA.
- Actual eager Muon restart/capture/replay/signal/GCS rejection checks passed;
  209local tests passed. All52frozen hashes remained unchanged. The deployed runtime
  SHA is3413ab059fe05ebb301f3021737ad1f960a5e625bc34e6be385013775702b55b.
- Best20andlast30are hash-verified locally in runs/ganesh-a100-cap40-v1/local-fit/.
  Last30completed a3turn exposed appointment-state conversation on MPS. This only
  establishes local runtime availability. No default change; HTTPoff.
- All4retainedfit bundles and raw/model-diagnostic/review evidence passed GCS
  readback before normal shutdown. See assessment/closeout/, local-fit-weights.json,
  review-backup.json and retirement-receipt.json.
- Normal GCP STOP observed2026-11-17T23:15:10.675UTC. GCP rejected shortening the
  running VM's terminationTime, so scheduled-provider STOP is UNPROVEN. Do not
  relabel the normal stop as a scheduled-stop fault-test pass. VM/disk were then
  removed under existing cleanup authority; project inventory0VMs/0disks.
- Estimated cumulative compute/disk$10.61including priorL4, excluding unsettled
  GCS/network charges. Conservative margin+reserves$20.59under$40. Unused budget
  does not bypass the failed fit gate.

Next: a versioned termination-learning treatment and reviewed English curriculum,
with generated-behavior selection and predeclared stops. No blind extra epochs or
loss-only model selection. The closed request must not be reused.
