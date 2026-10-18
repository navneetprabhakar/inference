# Disk-backed sample corpus staging

Creator: Navneet Prabhakar

## Delivered

`slm.data.staging` provides local JSONL staging beyond the old 32 MiB / 10,000-row reference-builder limits. Records, similarity postings, components and exposure counts live in SQLite. Read the [command contract and limitations](disk-backed-corpus-staging.md) before use.

- Existing normalization, privacy patterns, provenance, official OASST mappings and teacher bridge checks remain in force. Family/prompt/exact/similarity grouping precedes partition assignment. Exact duplicate selection matches the reference; nonexact semantic variants remain records. Integer-verified 0.85 shingle Jaccard uses lossless frequency-ordered prefix candidates, with hard comparison limits instead of skipped comparisons.
- Frozen heldouts preserve their records and family constraints. Stronger test assignments cannot be overwritten by older validation constraints. New occurrences cannot silently mutate or drop frozen content. Repeated input identities fail even if cleaning rejects them.
- Explicit input/row/feature/comparison/database and metadata limits fail the whole publication. Per-split writer handles remain bounded. Input/evidence and staging/cleaner source changes are checked; checked shards/evidence/manifest publish through a final directory rename. The main-database page ceiling excludes journal/sort/output space and is not a total disk or memory guarantee. Ingestion is not resumable after interruption.
- Every output remains sample-only and is rejected by the reviewed-training reader. No actual source approvals, representative quality clearance, tokenizer selection, language training or model acceptance result from staging.

## Verification

Focused tests independently compare retained records, exact representatives, splits and group digests against the original curator; compare prefix-filter results with brute-force Jaccard over random and boundary set systems; and cover adapter identities, frozen content, mutation, checksum/evidence failures, budget exhaustion, cleanup and training refusal. No numerical model code or acceptance threshold changes.

The larger local probe uses deterministic random word sequences and exercises both former input limits. Its distribution intentionally produces very few candidate pairs; it does not demonstrate dense-duplicate or natural-corpus performance. Source-frozen measurements are recorded in `reports/milestone-thirty-two-scale.json`.

| Source-frozen synthetic probe | Measurement |
| --- | --- |
| Input / retained rows | 11,000 / 11,000 |
| Input JSONL | 42,624,780 bytes (40.65 MiB) |
| Staging wall time | 82.07 seconds |
| Process peak RSS on macOS | 85,327,872 bytes (81.38 MiB) |
| Peak main database allocation | 649,936,896 bytes (619.83 MiB), about 15.25× input |
| Similarity candidate checks | 0 on this random-word distribution |
| Final local regression | 628 passed / 15 hardware-dependent skips |
| Focused staging tests | 20 passed |

These measurements include local contention from other verification processes. Database allocation excludes sort spill/journals/output; RSS is a process high-water mark, not a guarantee. The zero-candidate distribution is especially weak evidence for dense natural-corpus throughput. The separate real sample exercises 624 candidate checks and groups 598 near pairs, but remains only 901 retained rows.

The existing 901 retained canonical public rows are separately restaged with the original frozen heldouts. This checks source-specific canonical provenance and official proof preservation, not replay of raw upstream source files or new bulk acquisition. Messages, family identities and official labels remain unchanged; prior heldouts never become training rows. The original review packet remains byte-identical and the new output is refused for training. See `reports/milestone-thirty-two-real.json`.

Preliminary runs started before final metadata/code guards were frozen. Two incomplete scale probes were deliberately interrupted after query-plan inspection found SQLite scanning the full prefix index before selecting the current record. Their observations are retained in the incomplete-probe report; both working directories were removed and no output was published. Explicit cross-join order now starts from the selective record index, and commits are batched in groups of 256 rather than per record. Exact pair verification and limits are unchanged. Earlier successful small-sample runs are retained separately and are not final implementation proof. The initial full suite passed 624 / skipped 15; final source/test-frozen results appear in the summary and final XML.

## Remaining requirements

Production admission and representative quality/human policy remain missing. English/privacy checks are incomplete, semantic contamination remains unresolved, and bootstrap review/tokenizer readers still materialize records. SQLite staging is a foundation, not evidence that a billion-token corpus can be processed within the intended training budget. Real 1M/10M language pilots still require approved data and a production tokenizer. Numerical trajectory acceptance remains open.

No new teacher launch, API call, cloud job, source/teacher approval or real training occurred. CLI-only teacher policy remains active. Teacher reservations stay 17/20; conservative CUDA allowances stay USD 7/10, settled cost unknown. The full project goal remains incomplete.
