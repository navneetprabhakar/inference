# Proposed finite L4 envelope

17 November 2026. User approved hands-off execution in principle, conditional on satisfactory review. A numerical dollar ceiling has not yet been supplied for this new campaign; old approvals remain closed. This document is a proposal, not an authorization receipt.

## Recommendation

**$20 incremental campaign cap**, one on-demand `g2-standard-8` (one L4, 32 GiB RAM) in us-central1, maximum 12-hour absolute compute lease. This is a minimum prudent bounded-attempt recommendation, not a measured minimum cost to finish or a guarantee of model improvement. Qualification-only can be attempted with **$5**, maximum two hours; it may stop without qualifying.

Google's public list rate checked today is $0.853624312/hour for the VM (GPU included). Balanced disk is $0.000136986/GiB-hour. Assume 200 GiB total provisioned disk, subject to actual retained-checkpoint peak-space verification before allocation. No premium OS, Spot, second VM, automatic upgrade or retries.

| Component | Twelve-hour envelope |
|---|---:|
| L4 VM | $10.2435 |
| 200 GiB balanced disk | $0.3288 |
| 25% margin on VM + disk | $2.6431 |
| Separate storage/egress/recovery reserve | $6.00 |
| Total planning envelope | **$19.2154**, rounded to **$20** |

Qualification-only: two hours of VM+disk with 25% margin = $2.2026; $2.79 reserve rounds to $5. The two-hour qualification limit is included within the full campaign lease, not additional. No claim that every diagnostic will finish in two hours. If qualification cannot finish, stop and retain evidence rather than silently extend.

The $6 full-campaign reserve must cover actual incremental GCS storage/operations, selected-weight download and recovery-disk retention. Before launch, estimate retained bundle bytes and network route against it. Preserve existing local base weights; download selected new model payloads rather than every optimizer checkpoint. If the reserve cannot cover measured requirements, HOLD/reprice before allocation. Existing bucket storage, unrelated resources, taxes and exchange-rate conversion are outside this incremental USD estimate; it is not a cap on the entire GCP invoice. Persistent disk/GCS charges continue after compute STOP. Delete recovery disk only after required restore-verifiable backups; never trade sole-copy safety for a billing claim.

Sources (region and billing-account currency must be reconfirmed at launch):
- https://cloud.google.com/products/compute/pricing/accelerator-optimized
- https://cloud.google.com/compute/disks-image-pricing

## Adverse budget check

The controller permits at most two hours per command task and 30 minutes per individual probe. Frozen fit/dev allows 228,096 generated tokens: 31.68 tokens/second would use the ENTIRE two-hour probe stage with no loading or prefill allowance. Require conservative measured worst-shape timing, including checkpoint loading, prompt prefill and output writes, to fit within **90 minutes**, leaving 30 minutes margin. Merely measuring 42.24 generated tokens/second is insufficient if overhead is omitted. Curriculum+protected permits 90,432 tokens and must independently fit its stage and per-probe limits. No frozen evaluation budgets may be reduced to force this pass.

Total worst-case task time is eight hours (four command tasks), plus two hours qualification and one hour final backup reserve, leaving at most one hour for launch/setup/review overhead in the proposed lease. Before dispatch, compare measured remaining work plus backup reserve to the fixed deadline; otherwise STOP/HOLD. Agent semantic review may continue locally after shutdown, but the subsequent curriculum command must still fit the original lease. A larger dollar cap alone does not fix a task timeout. Do not quietly enlarge timeout, lease, epochs or learning rate.

## Required sequence and stop conditions

1. Bind explicit finite cap and actual immutable request; one VM, absolute provider STOP, non-auto-delete recovery disk, no restart/retry. Fresh input backup readbacks, inventory, price, image, quota and space checks precede allocation.
2. Spend at most two hours on setup/qualification. Prove CUDA memory and full-shape decode timing, exact restart, actual optimizer capture/replay, signal recovery, GCS restore, rejected-upload handling and provider STOP. Any failure stops progression; no diagnostic waiver.
3. Run frozen fit only if all proofs and remaining-time forecasts pass. Maximum 64 updates/64 epochs, unchanged recipe. Complete all raw milestone/best/last reviews. No semantic pass means no curriculum.
4. Run the frozen seven-update English curriculum pilot only after fit acceptance; review baseline/best/last English and protected tools. No release or serving-default promotion is authorized by this campaign.
5. Stop on numerical errors, memory failure, regression stop, changed hashes, incomplete review, timeout, backup failure or two failed pilots. No automatic retry or budget increase. Join writers and verify required GCS backups before normal shutdown. Fixed provider STOP still applies on backup failure; preserve recovery disk and report it.

**Remaining blockers:** numerical cap confirmation; approval-bound deployment specification; fresh backup/price/space evidence; unresolved exact CUDA restart; live recovery/provider checks; measured decode feasibility. Local tests pass, but training is not currently authorized or qualified. A failed qualification is a valid outcome of the bounded attempt.
