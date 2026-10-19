# Compact exact-shingle storage

Creator: Navneet Prabhakar

## Change and invariants

The stager now interns each complete SHA256 shingle hash once. Full-text/prompt postings and prefix indexes store integer feature IDs; separate full-text and prompt document-frequency counters preserve the original frequency order. A bounded per-record temporary table batches interning and membership joins. Explicit join order keeps small-record lookups before large dictionary/posting expansion.

- No digest truncation, approximate pair sampling, threshold change, record truncation or skipped candidate checks. The same normalization, exact identities, full/prompt signatures and integer-verified 0.85 Jaccard condition remain.
- Family/prompt/exact unions, exact representative priority, group digests, seeded splits, source provenance and frozen-heldout constraints remain unchanged. Existing budget failures still abort complete publication.
- Main SQLite allocation remains subject to the same page ceiling. New metrics expose the separate peak record-scratch database allocation, unique hashes and signature memberships. Journals, sort spill and output files are not included; these counters are not a hard total-disk/RSS guarantee.
- The exported shard schema stays unchanged. Implementation/report hashes change, so new artifact manifests differ. The original complete-source artifacts and 287-row pending review bundle are not modified or automatically rebound.

## Storage equivalence

For a signature kind `k`, hash `h` and record `i`, old membership `(k, h, i)` corresponds to new membership `(k, id(h), i)` through a unique dictionary entry. Each signature remains a set. The separate counter for `k` counts exactly those record memberships, and prefix ranking still uses `(count_for_k, h)`, never insertion-dependent feature IDs. Thus interning changes representation rather than feature equality, type-specific frequency, prefix selection or full intersection cardinality, under the same SHA256 collision-resistance assumption as before.

## Verification design

The existing independent reference-curator comparison and brute-force random/boundary Jaccard oracle remain in place. A new storage test verifies that every hash remains 32 bytes, dictionary memberships match independently computed full/prompt shingle sets, shared hashes are stored once, and kind-specific frequencies remain correct even when the two counts differ.

The actual natural-data comparison uses the exact milestone-thirty-five inputs, frozen 901-row parent, seed and all limits. Reference code is loaded from Git commit `59f35b91df4ce1f5b6e28d1f8c7209560eba3c0b`; its source hash must match the retained baseline artifact. The current and reference variants run in separate sequential processes on the same local machine. Every JSONL shard, heldout-family map, source registry and evidence index must be byte-identical to the retained baseline; semantic report fields must also match. This is one workload/run per variant, not a sustained throughput or p95 estimate.

| Same natural-data workload | Reference | Interned storage |
| --- | ---: | ---: |
| Wall time | 141.84 s | 105.06 s |
| Process CPU time | 135.56 s | 99.75 s |
| Peak main DB allocation | 809.94 MiB | 390.71 MiB |
| Main DB / input bytes | 52.48× | 25.32× |
| Parent peak RSS | 71.13 MiB | 70.22 MiB |
| Explicit per-record scratch DB | Not present | 0.46 MiB |
| Verified candidate comparisons | 2,964 | 2,964 |
| Near pairs grouped | 1,526 | 1,526 |
| Retained records | 15,692 | 15,692 |

Peak main DB falls **51.76%** and observed wall time **25.93%**. All **28 non-report payload files** match byte-for-byte, including record shards, heldout families, source registry and source evidence. New storage holds 2,370,188 unique shingle hashes and 3,905,056 typed signature memberships. Frequency counters are not token frequencies or training exposure.

Reference ran first. Filesystem caches and thermal state were not controlled, and a single pair is not a latency distribution. The small RSS difference is not evidence of a general memory reduction. Scratch allocation measures the explicit SQLite temporary database; sorter spill, journals and output remain outside this accounting. The remaining 25.32× main-file expansion still does not establish economical billion-token intake.

Final local suite: **689 passed / 15 hardware-dependent skips**. Focused staging tests: **21 passed**. The retained original twenty-test result precedes the added interning/frequency invariant. No test tolerance, boundary-set oracle or comparison budget was relaxed. There was no new NVIDIA validation.

Measurements and source/artifact hashes are recorded in `reports/milestone-thirty-six-summary.json` and the separate reference/interned reports.

## Scope and remaining work

The corpus remains 15,692 unapproved sample-only records. Existing source/sample export requests and the portability A/B decision remain pending. No model numerical code, teacher transport, corpus-admission authority, tokenizer selection or training gate changes. No new teacher generation, Platform teacher API call, cloud job, source download or neural training action occurs in the storage benchmark.

Teacher reservations remain 17/20; conservative CUDA allowances USD 7/10, settled cost unknown. Production-scale preprocessing, accepted data/policy, production tokenizer, real language pilots and useful student capability remain open. The full project goal remains active/incomplete.
