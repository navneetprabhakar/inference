# Official source partitions and held-out repair

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

Official OASST partition mapping identified **23 examples incorrectly present in the previous local train-candidate pool**. They are now held out. The rebuilt sample contains **799 train / 70 validation / 32 test** examples, with all **79 previously frozen held-out IDs, message contents and partition assignments** preserved. **No public-data training or tokenizer fitting had run**, so this discovery did not contaminate a trained checkpoint.

The result remains a sample-only audit. Source/content approvals, calibrated English/privacy/quality gates and production data releases remain incomplete.

## Official identity projection

The pinned [OASST2 release](https://huggingface.co/datasets/OpenAssistant/oasst2/tree/179dd21fc55192153d94adb0e0ce8f69e222bf75) publishes Parquet train/validation partitions separately from its complete nested ready-tree export. The new registry pins each file path, size, published LFS SHA-256 and row count. The source record/card/license pins remain unchanged.

- Projected only `message_id`, `parent_id` and `message_tree_id` using [PyArrow Parquet column selection](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html), with the exact runtime pinned to 26.0.0.
- Checked **135,174 official message identities / 13,854 complete trees**: 13,162 train trees and 692 validation trees. Duplicate IDs, cross-partition trees, missing parents and cycles are refused.
- Joined all nodes and parent links for each of the 200 sampled complete trees. **191 are official train; 9 are official validation**. This is an exact membership join, not a split inferred from row order, a random seed or an English-only branch.
- All **303 retained English paths** now carry official mapping evidence: 280 upstream train and 23 upstream validation. Official train may still be subdivided locally; upstream validation cannot enter train.
- The successful acquisition consumed **8,844,478 bytes of range payloads**, plus 670 bytes of repository-file metadata. The range budget is capped at 16 MiB. These figures are not total session bandwidth: an earlier full projection reached the join and failed before publication, and a separate 8-byte footer probe was made.
- The first join exposed nullable per-message tree IDs in the nested export: all 1,873 sampled nodes have null values there, while their enclosing tree supplies the root ID. The reader now inherits that outer identity, rejects conflicting non-null IDs, and still requires exact membership against the official projection. It does not discard a failed membership check to force a match.

Range responses must be exact HTTP 206 spans with matching total file size and no content encoding. Full responses are refused. Metadata footers and selected compressed column spans are acquired explicitly; subsequent Parquet reads have no network fallback and cannot request unacquired column data. Only identity columns are decoded. Parquet footers can contain other columns' statistics, so cached bytes remain unreviewed and must not become model input.

The published full-file LFS hashes are pinned but **not verified against complete Parquet bytes**, because the full files were not downloaded. The evidence is a pinned HTTPS partial projection with per-range checksums and validated identities, not a claim of whole-file content-hash verification, text equality or source clearance.

## Pipeline and review changes

- Import specs can bind an OASST mapping bundle using its explicit manifest SHA-256. Source/revision, input-row hash, complete tree membership and canonical split must match before adaptation. A global split cannot override a per-tree map.
- Existing frozen examples remain in duplicate/group checks. The rebuild preserved all old held-out IDs, content and held-out status; the 23 additional held-outs are all OASST examples. All upstream validation examples are absent from train.
- Cached source audits now verify source identity, upstream configuration and actual split as well as revision, count and bytes. For example, a `test_sft` acquisition cannot be loaded under a `train_sft` registry entry. Known upstream split names map explicitly to canonical partitions. Generic custom imports still require their own upstream evidence.
- Review publication refuses OASST approvals without verified mapping evidence, and refuses manual partition overrides. Legacy unmapped snapshots remain available as historical sample audits, but cannot release approved OASST records through the current reader.
- The current pending review packet is **`data/official-split-audit-v1/pending-review.json`**: 40 examples, four source reviews, zero approvals, no human attestation. Seven OASST entries have machine-prefilled partition evidence only. English/privacy/quality/content decisions remain pending. The original `data/reviews/bootstrap-review.json` is preserved; no human decisions were copied or inferred.

## Evidence

- Full local suite: **148 passed, 5 CUDA checks skipped**. Nine new partition tests cover sparse-read bounds, HTTP refusal, corrupted caches, complete-tree identity, partition conflicts, actual local Parquet projection, offline replay, held-out build behavior, review guards and cached config/split mismatches.
- The official projection reproduced from its cached ranges with **zero new range payload bytes** and an identical bundle manifest. Its SHA-256 is `aee61ce28678916ac2df98e7c7dade148bf67e0aa93d463083be55037044b1fd`.
- Independent mapped curation rebuilds have identical manifests and shard hashes. The current dataset manifest SHA-256 is `7501cc5f6251c483abd8349fae5f65c95e78a7776dd9ba57bf1434a730177f7a`.
- The reviewed-training reader refuses the new sample-only snapshot. Public source/example approvals remain zero. No model training, live teacher request or cloud job occurred.
- Compact evidence: `reports/milestone-ten-official-partitions.json` and `reports/milestone-ten-tests.xml`. Raw records, identity/range caches and review packets remain outside Git.

## Reproduce using existing artifacts

The mapping collector supports a pinned cached replay or a new bounded public acquisition. Use a fresh destination and `.[dev,mlx,tokenizer,teacher,data]` on the laptop:

```sh
.venv/bin/python -m slm.data.partitions --source-record data/audit-v1/oasst2/source/source.json --ready-sample data/audit-v1/oasst2/sample --cache data/oasst-partition-map-v2 --output data/new-oasst-map
.venv/bin/python scripts/audit-official-partitions.py --cached-input data/audit-v1 --mapping data/oasst-partition-map-v2 --mapping-sha256 aee61ce28678916ac2df98e7c7dade148bf67e0aa93d463083be55037044b1fd --frozen-dataset data/audit-offline-final/curated --output data/new-mapped-audit
```

Omit `--cache` from the first command only when another bounded acquisition is intended. Do not overwrite existing frozen snapshots or review packets. Production-scale streaming/deduplication, representative quality calibration, actual human review, tokenizer selection and language-training pilots remain open. The pending portability decision and separate teacher budget/key/terms requirements are unchanged.
