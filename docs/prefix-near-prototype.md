# Exact prefix-index prototype

Creator: Navneet Prabhakar

Date: 20 October 2026

## Decision

The bounded replacement prototype passes its selected-population audit. It is suitable for a larger measured preflight, not yet full-corpus grouping, source admission or training. Student capability remains 0/100 on the last actual conversation assessment. No student gradients, teacher requests or cloud resources were used for this milestone.

## Algorithm and completeness

The former full-feature SQL dictionary required extensive random writes. The new prototype keeps complete punctuation-aware five-token shingle sets in an append-only binary stream, while indexing only prefixes. For Jaccard threshold 17/20, a set of n features needs a prefix of n - ceil(17n/20) + 1 features under one consistent global order. Any qualifying pair must share a prefix feature. Symmetric length filtering removes impossible matches; complete hash-set overlap filters candidates, and full raw-string shingle Jaccard verifies every accepted pair.

The fixed order uses counts from 512 deterministically selected source records, then SHA-256 as a tie breaker. Unseen features have count zero. Sampling chooses the global ordering only; it does not sample or truncate the matching features or candidate verification. The prefix property holds for an arbitrary consistent order; frequency ordering affects efficiency. See the prefix-filter lemma in [Efficient Similarity Joins for Near Duplicate Detection](https://wwwconference.org/wp-content/uploads/2025/06/p131-xiaoA.pdf). Cryptographic feature identities retain the ordinary hash-collision assumption; raw verification protects accepted edges.

Exact raw aliases retain all source/facet references. No source flag, inherited protected family or rejected record is admitted by this prototype. The original sources, runtime and prior interrupted indexes remain unchanged.

## Actual evidence

| Measurement | Actual result |
|---|---:|
| Selected source records | 4,096 of 235,779 |
| Source/facet references | 5,823 |
| Unique raw facets | 5,820 |
| Complete feature occurrences | 2,209,502 |
| Indexed prefix postings | 334,493 |
| Candidate pairs fully replayed | 7,368 |
| Qualifying near pairs | 0 |
| Full feature binary | 70,704,064 bytes |
| SQLite database | 30,175,232 bytes |
| Read-only audit duration | 5.79 seconds |
| Audit peak RSS | 576,847,872 bytes |

The audit reconstructs every selected source mapping, full feature stream, prefix and candidate comparison; original files hash identically before and after. An independent 128-facet all-pairs check agrees, but contains zero qualifying pairs. Positive-match recall is therefore demonstrated by synthetic tests, not this source sample. Nine focused tests cover arbitrary/sampled orders against brute force, positive mutations, exact-threshold and asymmetric sizes, aliases, punctuation and refusal at resource caps.

The original benchmark indexed the selected population, then was explicitly interrupted because its audit repeatedly scanned the full prefix index for each facet. Its terminal status remains incomplete (parent 130, child -9); all artifacts are retained. A separate 90-second bounded read-only audit used one sorted prefix stream and completed successfully. It neither rebuilt nor resumed the index. Exact build-phase throughput was not recorded. The 71.20-second observation bound includes setup and the interrupted audit; it is not an indexing-time measurement. Audit RSS does not establish peak build memory or full-corpus memory requirements.

## Reproduction and retained evidence

- Frozen benchmark: `configs/prefix-near-benchmark-v1.json`.
- Prototype: `src/slm/data/prefix_near.py`; tests: `tests/test_prefix_near.py` and `tests/test_facet_near.py`.
- Actual audit: `reports/prefix-near-benchmark-audit.json`; tests: `reports/prefix-near-prototype-tests.xml`.
- Private original attempt: `data/prefix-near-benchmark-v1`; separate audit: `data/prefix-near-readonly-audit-v1`.
- Commands and source copies are retained with each private attempt. Executed code/configurations are immutable. Do not rerun a creation command over an existing root or reinterpret an interrupted attempt as complete.

## Next acceptance boundary

Freeze a separate larger preflight with explicit wall, disk, feature, candidate-pair and memory bounds and measured build-phase timings. Include actual near-match witnesses and long/common-feature documents. Inspect candidate growth before extrapolating to all source records. Use the streaming auditor from the outset; the old benchmark script intentionally remains the executed historical version with its inefficient audit.

Only after a complete finite full-source join: audit every mapping and edge, propagate links over inherited exact/containment components, independently check protected/rejected labels, freeze family-disjoint splits, review finite source admission and count realized unique/exposure positions. Then freeze the learning/resource/useful-portability contract before substantial language continuation. No benchmark success changes the USD50/100M-position training ceiling or authorizes another tiny SFT run.
