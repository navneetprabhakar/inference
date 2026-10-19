# Main English learning pilot: budget proposal

Creator: Navneet Prabhakar

Date: 19 October 2026

Status: **Budget requested; no main-training spend authorized or VM created.** Machine-readable limits: `configs/main-learning-budget-proposal-v1.json`.

## Decision needed

Choose a separate main-learning budget: **up to USD 50**, **up to USD 25**, or **laptop only**. The existing USD 10 authorization is CUDA-validation-only; conservative historical allowances are USD 7, with settled cost unknown. It will not fund this main-learning pilot.

This funds the next measured learning experiment, not a promise of a completed assistant. The present model solves zero of eight conversation tasks. The recent small control fits some references while its validation loss regresses; more tiny memorization is not a substitute for broader language learning.

## Concrete resource and workload

Use one on-demand **g2-standard-4 / NVIDIA L4** VM in `executespecv1`, `us-central1`, with 4 vCPUs, 16 GiB host RAM and 24 GB GPU memory. The publicly listed Iowa VM rate observed today is **USD 0.706832276/hour**, before separate storage/network/account-specific charges. [Official accelerator-optimized pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized?hl=en), [official GPU machine specifications](https://docs.cloud.google.com/compute/docs/gpus).

Retain the 80,765,440-parameter architecture, frozen 16K tokenizer and FP32 reference implementations; training context starts at 1,024. Use the project's own random-origin foundation checkpoint as the proposed starting point. Declare any new-corpus optimizer-phase transition explicitly; never reset state during a backend transfer or call a fresh optimizer an ordinary resume. Source, exact realized corpus/exposure, recipe and evaluation contracts must be ready before launch.

| Choice | New total spend ceiling | New training-position ceiling | Total VM lifetime ceiling | Conservative allowance |
| --- | ---: | ---: | ---: | --- |
| Preferred pilot | USD 50 | 100M | 45 hours | USD 36 compute at rate cap 0.80/hour +4 storage/network +10 contingency |
| Smaller pilot | USD 25 | 50M | 20 hours | USD 16 compute at rate cap 0.80/hour +4 storage/network +5 contingency |
| Laptop only | USD 0 cloud | Separately frozen local run | No cloud VM | Local data preparation; no paid resource |

Spend, time and data ceilings apply together; stop at the first boundary. They do not guarantee the token target will finish. All-in charges must be bounded within the selected ceiling before launch; if account-specific charges prevent that bound, stop before resource creation. Do not rely on billing alerts as a compute stop mechanism.

## What the timing numbers mean

Prior actual 81M laptop foundation updates process approximately **1,014 positions/second** over 9.96M measured update positions. At that update-only rate, 100M positions take about **27.4 hours**, excluding new data preparation, evaluation, transfers/checkpoints and changes in sustained conditions. It is a projection, not a promised laptop completion time.

Actual earlier T4 synthetic probes measured roughly 1,100–1,352 positions/second, but used a different epsilon/embedding-era recipe and very short timing samples. They are not a forecast for this L4 run or the current dense-onehot workload. No actual L4 throughput has been measured.

For scale only, the 100M target would require:

| Hypothetical sustained rate | Update-only hours | VM cost at the observed listed rate |
| --- | ---: | ---: |
| 500 positions/second | 55.6 | USD 39.27; exceeds the 45-hour lifetime |
| 1,000 positions/second | 27.8 | USD 19.63 |
| 2,000 positions/second | 13.9 | USD 9.82 |

These scenarios are arithmetic, not performance estimates. Measure the actual frozen workload before committing the remaining run. If too slow, retain the achieved checkpoint and stop within the approved envelope; do not silently extend lifetime, change hardware or purchase capacity.

## Data and quality conditions

The new phase should materially expand English prose rather than repeat the twelve-example control. FineWeb-Edu is a planned source, not automatically admitted training data. The old 200-document cached prefix is entirely from one 2013 crawl. The new bounded audit spans four distant clusters and still finds boilerplate, mixed-language captures, topic/scope issues and secondary claims. Six reviewed documents are quality considerations, not a 100M-token release.

Before gradients, prepare a finite pinned population; retain source/URL/crawl/license lineage, apply language/privacy/boilerplate/exact-near-duplicate checks, preserve all ancestral heldouts and define new groups before tokenization. Remove observed nonapprovals or explicitly resolve their narrower scope under a new documented admission decision. Keep unread-row and underlying-rights uncertainty explicit; do not label the entire web corpus verified. FineWeb-Edu's database license and Common Crawl's conditions do not certify every underlying document's rights or factual accuracy. [Pinned source card](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu/blob/87f09149ef4734204d70ed1d046ddc9ca3f2b8f9/README.md), [Common Crawl terms](https://commoncrawl.org/terms-of-use).

Freeze held-out prose/reference diagnostics and protected request tasks, learning/retention guards, seeds/exposure/uncertainty before comparative continuations. The accepted Option-A portability gate requires useful held-out learning; the current failed overfitting control cannot close it. Perform state/inference checks and a predeclared matched learning comparison before deciding whether to extend the paid pilot. Failed comparisons remain failed. Prose-loss improvement alone never establishes conversational/tool capability.

At each completed training iteration, retain the terminal state and conduct the actual eight-turn raw-history conversation/direct score before advancing. Teacher-based conversation/style/tool training and later ESCI remain necessary; this foundation pilot does not replace them. No new teacher usage is part of this funding request.

## Lifecycle and authorization boundary

Before creation, verify current prices, the exact image/dependencies, global/regional quota and stock, dataset admission, remaining allowances, resource sizing and bounded cleanup. Regional quota currently reports L4 limit16/usage0 and T4 limit8/usage0; this does not guarantee stock or global eligibility.

Use one task-labelled private VM with no public service, no credential copying and only the necessary access path. Set provider-enforced finite deletion duration and auto-delete boot disk, and independently stop on job time/tokens/quality/integrity failures. Retrieve and checksum results, delete owned resources, then verify their absence. Implement and verify those controls before launch; the proposal itself does not claim they already exist for the new run. Touch no unrelated resources.

The selected budget becomes the preparation constraint; paid launch remains conditional on the gates above. Approval does not authorize a cluster, parallel runs, credits/resets, teacher/API spending, public deployment, numerical-tolerance waiver or another silent budget reset. Local source/pipeline work can continue while a funding decision is pending.
