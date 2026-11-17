# GCP resource and cost audit

17 November 2026 IST. Read-only inventory across all five projects visible to the current account and the one visible billing account. No resource deletion, VM start, API enablement, billing link change or secret-value access. Small read-only BigQuery aggregate queries were capped at100MB scanned each; they can consume query quota.

## Key finding

Current billed-project storage footprint implies approximately **₹6,521.68/month**, even with no running VM. This is a steady-footprint estimate using observed INR account rates, not a final invoice or guaranteed future charge. Soft-deleted data expires and the Own bucket has a deletion lifecycle; credits, taxes, requests and transfer are not forecast.

## Charges already in the export

November invoice-month net exported charges: **₹9,732.88**. Latest export: 2026-11-16 14:51:45UTC. Latest usage end represented: 2026-11-16 10:00:00UTC; individual services, especially storage, lag further. The most recent A100 allocation starting18:02UTC16Nov is not included. This is not the final invoiced/payable total. All positive November costs are in executespecv1.

| Service | November exported net INR |
|---|---:|
| Compute Engine | 9,116.20 |
| Cloud Storage | 596.55 |
| Secret Manager | 20.13 |
| Cloud Logging | 0.00 |
| Networking | 0.00 |
| BigQuery | 0.00 |
| Deep Learning VM | 0.00 |

The separate billing-summary query groups usage dates in IST, producing a different total (₹9,745.07) because usage period and invoice month are different groupings. Do not add the two totals. Standard and detailed exports are also not added together. This report uses the detailed export and invoice-month total above. Only regular cost lines are present in the November aggregation; no tax/payment reconciliation was performed.

## What continues to cost money

| Resource | Current footprint | Monthly INR estimate |
|---|---:|---:|
| Balanced persistent disks | 500GiB | 4,761.50 |
| Nine GCS buckets in executespecv1 | 818.51GiB | 1,651.61 |
| Secret Manager | 14secrets /19enabled versions | 108.56 |

Rates from recent detailed billing rows: balanced disk₹9.523/GiB-month; Standard Storage₹1.9046/GiB-month in us-central1/us-east1 and₹2.19029in us-east4/asia-south1; secret-version replica₹5.7138/month. All14secrets use automatic replication. The19-version estimate is consistent with the recent daily storage charge; additional accesses or free allowances can change the actual bill.

### Persistent disks

| Disk | Size | Region | Monthly INR |
|---|---:|---|---:|
| forge-ownbase-budget50-v1 | 200GiB | us-central1 | 1,904.60 |
| forge-ownbase-v2-retained-01 | 200GiB | us-central1 | 1,904.60 |
| forge-english-retry-1116-180221 | 100GiB | us-central1 | 952.30 |

Four VM records exist but only three persistent disks. Do not multiply VM count by disk size. Stopped instances incur no VM usage charges, but retained disks remain billed: [Google Compute Engine documentation](https://docs.cloud.google.com/compute/docs/reference/rest/v1/instances/stop).

### Storage buckets in the billed project

| Bucket | Live GiB | Soft-deleted GiB | Noncurrent GiB | Monthly INR |
|---|---:|---:|---:|---:|
| forge-ownbase-a100-20261110 | 284.946 | 0.000 | 0.000 | 542.71 |
| ganesh-gate0-model-transfer-1061994342941 | 121.684 | 87.449 | 0.000 | 398.31 |
| executespecv1-laxmi-features | 151.200 | 0.000 | 0.000 | 331.17 |
| laxmi-corpus-executespecv1-20260714 | 147.119 | 0.000 | 0.000 | 322.23 |
| ganesh-benchmarks-1061994342941 | 23.103 | 2.982 | 0.000 | 57.13 |
| executespec-dev-deploy | 0.020 | 0.000 | 0.000 | 0.04 |
| executespec-tfstate | 0.000 | 0.000 | 0.003 | 0.01 |
| laxmi-corpus-pilot-executespecv1-20260713 | 0.002 | 0.000 | 0.000 | 0.00 |
| executespec-swebench-lite-20260718-results | 0.000 | 0.000 | 0.000 | 0.00 |

Monitoring snapshots are around18:45UTC16Nov; all pages were followed. Values are monitoring evidence, not an object-by-object storage audit. Older zero-valued series are included as zero. About90.43GiB is soft-deleted, predominantly the model-transfer bucket. Soft-deleted objects remain billed during their retention period: [Cloud Storage pricing](https://cloud.google.com/storage/pricing). This temporary footprint should not be extrapolated as a fixed recurring bill indefinitely.

**Retention issue:** forge-ownbase-a100-20261110 has a Delete lifecycle at age30days and soft delete disabled. Objects become eligible for automatic permanent deletion after30days. It is not an indefinite archive. Change/archive the required future-use objects before relying on it for long-term retention; this audit did not alter the policy.

## Project inventory

| Project | Billing enabled | Main findings |
|---|---|---|
| executespecv1 | Yes | 4stopped VMs;3disks;9buckets;14secrets/19enabled versions;empty instance group;1instance template;1VPC/42subnets/43routes;1firewall;2log buckets;empty billing dataset; IAM/configuration assets |
| gen-lang-client-0455394131 | Yes | Billing dataset with2export tables;2log buckets;API/IAM/configuration assets; no positive November exported charges |
| ppl-ai-488614 | No | 3buckets (~0.597GiB);19secret resources/3indexed versions;2log buckets;IAM/configuration assets. Some direct service listing is blocked while billing is disabled. Not charged to the visible billing account in this audit. |
| google-mpf-enzl3bmo5kvq | No | Management project/lien, logging and enabled-service assets; no compute workload found |
| project-a90cbc0b-0cbc-40b0-a1a | No | Logging/project/service configuration; no workload found |

Full indexed resource types/counts: asset-type-counts.json; raw resource metadata is in the accompanying JSON files. Secret contents and API-key values were not fetched. Enabled APIs are not proof of provisioned or billable workloads.

## Empty workload/resource classes verified

In executespecv1: no running VM, disk snapshot, custom image, reserved address, forwarding rule, backend service, Cloud Router/NAT router, VPN tunnel, reservation, commitment, GKE cluster, Cloud SQL instance, Cloud Run service/job, Artifact Registry repository, Pub/Sub topic/subscription or managed DNS zone. Redis instance listing returned zero across43locations. BackupDR returned no resources across supported regional reads;6multi-region management-server/backup-plan requests returned400, with no BackupDR assets in Cloud Asset inventory. Instance group size is zero; its template/configuration does not mean an active worker.

## Coverage and access limits

Cloud Asset initially failed because the default consumer project had its API disabled. Reusing the existing enabled Cloud Asset API in the management project allowed complete paginated indexed inventory for all5visible projects without enabling a service. Cloud Asset may lag and covers supported asset types, so direct service reads were used for major billable workloads. This is account-visible scope, not a guarantee of unseen projects/accounts.

Budget API listing was unavailable because its API is disabled; budget alerts were not verified. No billing account payment balance, credits remaining, tax invoice or future usage guarantee is claimed. API/billing-disabled direct-list failures are retained as evidence rather than represented as zero resources.

## Cleanup priority — no deletions performed

1. Largest potential recurring saving: the500GiB disks (~₹4,762/month). Verify every required unique file/checkpoint against local/GCS backups before deleting any disk; the audit did not inspect disk contents or certify all disks disposable.
2. Review old bucket contents (~₹1,652/month at current snapshot), especially model-transfer and corpus/features buckets. Names alone do not establish obsolescence.
3. Resolve the Own bucket30day lifecycle for required long-term backups before project pause.
4. Review unused enabled secret versions (~₹109/month) without exposing values.
5. Keep compute/retries off. Empty groups/templates/network configuration are lower priority than actual billed storage.
