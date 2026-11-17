# GCP storage cleanup — 17 November 2026

**Completed within authorized scope; no VM was started.** Required Own local models remain available; HTTP remains off.

## Removed

- Four stopped VM records and all three persistent disks (500 GiB). Fresh project inventories confirm zero instances and zero disks. Estimated disk cost removed: ₹4,761.50/month.
- Own: 85 obsolete/redundant weight objects, 258.042 GiB. Fresh listing confirms 62.797 GiB retained, with exactly 11 checkpoint payloads.
- Ganesh: all 8,527 live/versioned objects across both dedicated buckets; both empty buckets deleted and absence confirmed.
- Laxmi: 1,288 exact duplicate objects (0.411 GiB), verified by matching nonzero size, MD5 and CRC32C. A generation-pinned canonical copy was freshly checked before each deletion.
- Secret Manager: five superseded version1 credentials destroyed; 14 latest versions remain enabled.

Total GCS payload removed: **403.238 GiB**. Remaining live GCS footprint: **approximately 360.728 GiB**. Own is freshly relisted; Laxmi totals use complete before-inventory minus successful generation-bound deletions plus restore-map uploads. Small unchanged buckets use the audit snapshot.

## Ongoing cost

- After soft-delete expiry: approximately **₹852/month**, using observed account rates, before tax, requests, egress, future credits and data growth.
- Including previously soft-deleted Ganesh data and newly soft-deleted Laxmi duplicates: snapshot equivalent about **₹1,026/month**. This is temporary, not a forecast.
- Existing ~90.431 GiB of soft-deleted Ganesh data cannot be claimed purged. Its prior retention expiry still applies. Ganesh soft deletion was disabled before the new removals to avoid extending retention of newly removed data. Laxmi retained its existing seven-day safety policy.
- Billing export and Monitoring lag. These figures are inventory-based estimates, not final billed savings or invoice totals.

## Own retained and verified

- Seven local-test/reference model bundles: base10B, development step50, SFT194, SFT605, selected diagnostic2, and the prior restart reference/mismatch pair. Local payload SHA256 matched manifests and fresh GCS MD5/size.
- Four latest restart-failure bundles retained. Fresh manifest hashes match the earlier independent readback receipts; all referenced members and COMMITTED markers remain present.
- All 11 retained bundles passed post-deletion manifest/member/commit-marker checks. All 224 corpus shard receipt MD5/size identities matched fresh inventory.
- Latest restart evidence matches its locally verified SHA256 and GCS MD5. Reviewed conversations, frozen corpus, tokenizer, runtime and compact provenance/evaluation evidence remain.
- All 41 frozen input hashes are unchanged. No model promotion, training, HTTP start or runtime-default change.
- Removed the blanket 30-day Own lifecycle deletion rule. Required backups now persist until deliberately retired.
- `own-plan.json` and `own-post-delete-verification.json` are current checkpoint retention authority. Historical manifests and journals can name deliberately retired weights; they are provenance, not a promise every historical checkpoint remains restorable.
- Disk retirement preserved the required future-use artifact set. No claim of a full offline block-level inspection of all three disks is made. Disposable environments/caches and obsolete experiments were intentionally retired.

## Laxmi: what remains and why

- 105.837 GiB compressed raw-disk archive: generation and size match the prior verified retirement receipt; the original disk is already gone. Its internal files were not extracted in this task. It cannot safely be called redundant from object metadata.
- Approximately 74.447 GiB repository snapshots and 65.641 GiB archived Git clones. Different formats/history may overlap, but equal content has not been established.
- Other sizable archives include pretrained weights, runtime and all-training-checkpoints packages. Their internal redundancy or safe reconstruction was not established here.
- The complete metadata scan covered 179,004 Laxmi objects across three buckets. Exact nonempty object-level duplicates total only0.411 GiB. This does not rule out internal duplication inside differently packaged archives.
- Durable restore maps were uploaded to `_retention/20261117/dedupe-restore-map-<SHA256>.json` in all three Laxmi buckets and SHA256-readback verified before deletion. To restore an original deleted path, copy its mapped canonical `keep.bucket/name#generation`, verify size/MD5/CRC32C, then recreate the original path with a no-overwrite precondition and its recorded metadata. Consumers requiring original layouts must apply this map.
- Local source of mapping: `laxmi-dedupe-plan.json`; GCS identities are in `*-restore-map.json`. Unique data and opaque archives were preserved; remaining large-archive overlap needs an explicit content-level extraction/reconstruction review, not a filename guess.

## Secret Manager limits

- The five superseded versions were replaced by version2 on the same day. No aliases pointed to version1; examined local deployment references did not pin those old versions. Latest versions were retained.
- An application service account still has Secret Accessor and an instance template uses that account. No current VM/Run/GKE consumer was found, but external or future consumers cannot be excluded.
- Recent access-log query returned zero; project Data Access audit logging is not configured, so this is not evidence of non-use. The remaining14latest application credentials were not destroyed.
- Billing-disabled project secrets were left unchanged; their lifecycle/dependencies were not established. No secret payload values were accessed.

## Execution evidence and limits

- 1427 Ganesh deletion requests were rejected with401 after the process token expired. A fresh token and paginated inventory reconciled exactly those remaining generations; all were removed successfully. No unresolved deletion error remains.
- Every object deletion used an exact generation precondition. All mutation results, metadata inventories, backup checks and post-checks are retained beside this report.
- No new cloud compute, disks, snapshots or model downloads were provisioned. API operations and small receipt uploads may incur normal request/storage charges.
- Raw audit files can contain resource metadata; they are not intended for public GitHub publication. No commit or push performed.
