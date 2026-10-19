# Complete small-source preparation and review bundle

Creator: Navneet Prabhakar

## Delivered

The complete pinned Dolly source now replaces its first-200-row limitation in a new sample-only population. This is actual instruction data preparation, not another synthetic language-training substitute. Training and source approval remain gated.

- Source: `databricks/databricks-dolly-15k`, revision `bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a`. The publisher's root-file metadata supplies a 13,085,339-byte size and LFS SHA256 `2df9083338b4abd6bceb5635764dab5d833b393b55759dffb0959b6fcbf794ec`; the complete download matches both within the existing 24 MiB audit ceiling.
- The [pinned source card](https://huggingface.co/datasets/databricks/databricks-dolly-15k/blob/bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a/README.md) describes employee-written instructions, Wikipedia context and CC BY-SA 3.0 distribution. Local card/license hashes and attribution are retained. This records publisher evidence, not a new source-rights determination.
- **15,011 raw rows → 15,003 distinct raw objects → 14,991 retained Dolly examples**. Eight exact raw duplicate occurrences are counted explicitly. The existing cleaner rejects one credential-pattern row and four replacement-character rows (reported as invalid text encoding by the cleaner); seven additional exact normalized conversation duplicates are removed. These are mechanical criteria, not adjudicated defect judgments; original raw data and rejected identities remain available for review.
- Combining the complete Dolly source with the other 701 existing source examples yields **15,692 records: 14,041 train candidates / 810 validation / 841 test**. All 901 previous retained identities survive with unchanged messages, source/family provenance and official labels. All 102 previous held-out records remain held out. One prior train candidate moves to held-out status after full-population grouping. The old pending packet is preserved but cannot be rebound to this different parent manifest.

## Categories and finite-population audit

| Upstream Dolly category | Raw occurrences | Retained examples | Sampled examples |
| --- | ---: | ---: | ---: |
| Brainstorming | 1,766 | 1,765 | 8 |
| Classification | 2,136 | 2,136 | 14 |
| Closed QA | 1,773 | 1,766 | 9 |
| Creative writing | 709 | 707 | 5 |
| General QA | 2,191 | 2,189 | 10 |
| Information extraction | 1,506 | 1,504 | 14 |
| Open QA | 3,742 | 3,737 | 16 |
| Summarization | 1,188 | 1,187 | 17 |

The new audit measures **34,240 windows across 14,977 groups** and selects **287 records in 194 complete groups**, including 93 Dolly examples. It observes all eight Dolly categories, but category-balanced sampling was not imposed and observed coverage is not a statistical quality guarantee. Dolly sampling is conditional on the complete post-cleaning/deduplication population; the other three sources remain first-N-derived. Rejections must be considered separately when assessing the original raw population.

The classifier marks 386 combined records with non-English top windows, six with privacy candidates, 100 with unscored windows and twenty with incomplete top-k results. None of these measurements approves or rejects a training row. Existing short/code/quotation limitations remain relevant.

## Reviewable artifacts

- Population and provenance: `data/complete-small-source-v1/`.
- New bounded pending review master and index: `data/complete-small-source-review-v1/pending-master.json` and `review-index.json`.
- Existing console workflow rendered as [part 1](/Users/navneetprabhakar/Documents/git/image/inference/data/complete-small-source-review-v1/part-01.html) (199 records) and [part 2](/Users/navneetprabhakar/Documents/git/image/inference/data/complete-small-source-review-v1/part-02.html) (88 records). Whole groups do not cross parts. Source evidence is embedded through the existing checked renderer; all source/row decisions remain pending. The original 40-row packet and console are historical artifacts, not replaced in place.

These exports can attest only reviewed rows. They cannot approve all 15,692 records or bypass the proposed corpus-admission policy. Browser rendering/download behavior remains unverified; no automated browser route was attempted after the earlier local-file policy rejection. Actual exported decisions are required before applying or publishing them.

The portability A/B decision and the new source-review export paths were requested through the app. Existing failed trajectory criteria remain unchanged while that decision is pending.

## Resource evidence and limits

Natural-data staging takes **151.00 seconds** for 2,964 verified candidate comparisons and 1,526 near pairs. Peak main DB allocation is **849,281,024 bytes (809.94 MiB)** against 16,183,589 staged input bytes—about **52.5×** input. Quality auditing takes **7.47 seconds**. Parent process peak RSS is **104,497,152 bytes (99.66 MiB)**; child-process peak and total journal/spill/output disk are not included.

This demonstrates a complete small natural source, not economical billion-token ingestion. The observed database expansion and preprocessing cost require improvement before production bulk use. Instruction data alone also does not satisfy broad English foundation pretraining.

Final local suite: **688 passed / 15 hardware-dependent skips**. Acquisition tests: **11 passed**, including published size/hash binding, unsafe names, metadata/budget failures, excluded sources, interrupted streams, evidence mutation and atomic cleanup. The actual preparation independently checks original Dolly identity coverage, frozen holdouts, source categories, lineage and sample-only training refusal.

No new teacher generation, Platform teacher API call, cloud job, credit action or neural update occurred in preparation. Public source metadata/file retrieval did occur. Teacher reservations remain 17/20; conservative CUDA allowances USD 7/10, settled charges unknown. Actual source/row approvals remain zero, no production tokenizer is frozen and no real language pilot has run. Full goal remains active/incomplete.
