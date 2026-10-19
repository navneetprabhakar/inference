# Verified seed containment and grouping input

Creator: Navneet Prabhakar

Date: 19 October 2026

- **One additional cross-component link is verified:** a captured Cosmopedia seed is the first 1,000 normalized bytes of an acquired FineWeb document. Its endpoints are `cosmopedia-v2/train-00039-of-00104.parquet`, group90/row593, and `sample/10BT/010_00000.parquet`, group453/row998.
- The new link is consumed into the next grouping input. Its 235,779 records now form **229,605 components**, compared with 229,606 after exact-only grouping. Original source text and individual heldout labels remain unchanged. The previously discovered rejected-family candidate remains withheld.
- Near-duplicate grouping, new splits, finite corpus admission and a realized exposure schedule remain incomplete. No student update, teacher call or paid resource occurred.

## Actual exhaustive scan

| Measurement | Result |
| --- | ---: |
| Captured seed fields | 38,278 |
| Distinct normalized complete seeds | 36,554 |
| Consolidated target records | 235,779 |
| Target text fields | 333,398 |
| Normalized target bytes | 650,719,438 |
| Prefix-index candidates | 116,084 |
| Verified complete-seed occurrences | 79,147 |
| Occurrences already within exact components | 79,146 |
| New cross-component occurrences | 1 |

Every content, prompt, seed and witness text field is included. Normalization is NFKC, case folding and whitespace collapse, applied only to a matching view; original source text remains in the immutable database. The index enumerates every possible byte offset using a vectorized 64-byte polynomial prefix hash. A hash hit is only a candidate: the entire normalized seed must match before an occurrence is accepted. Hash collisions cannot become accepted links. Identical normalized patterns share a representative in their existing exact component.

The reported offsets refer to normalized matching bytes, not original source byte positions. A contained quote demonstrates a text relationship; it does not establish a unique upstream document identity. Different excerpts from an unobserved common document remain unresolved.

## Verification

- Four tests pass: all-offset comparison against brute force, repeated prefixes, Unicode/whitespace/case handling, partial UTF-8 prefix boundaries, deliberately forced hash collisions and finite target/pattern bounds.
- The actual checker reconstructs all 36,554 pattern identities and verifies source record/field/byte coverage totals, the output database integrity/hash and every new full containment span.
- Independent brute-force comparisons cover 128 fixed-hash target fields plus the new-link target: 129 fields /30 complete occurrences, with exact agreement. Independent recall checking is sampled; the complete scan evidence is the pinned executed worker, full counters and tested all-offset algorithm.
- A separate next-input checker independently consumes every containment edge, reconciles every output root/component/identity/heldout and nonapproval flag, and verifies the original database/input hashes. All 235,779 roots and 229,605 components pass.

The worker has a 30-minute independent process-group deadline, 20M candidate-hit cap, 4 MiB normalized field cap, 512 MiB output-database cap and 30 GiB free-disk reserve. Out-of-scope fields or exhausted limits fail the whole scan; there is no truncation, sampling fallback or automatic replay. NumPy 2.5.4 was used locally. These controls are not a hard RSS sandbox.

## Next execution contract

`configs/global-grouping-input-v1.json` binds the immutable exact database, verified containment edges and checks. Its private root/component artifacts are hash-bound by `reports/global-grouping-input.json`. Future near grouping must consume these roots rather than return to the earlier exact-only components.

Apply the declared 17/20 Jaccard threshold to complete reference five-token, punctuation-aware shingle sets, preserving every protected/nonapproval component before new splits. Exact and containment outputs do not substitute for that step. The source-family uncertainty above remains an explicit limitation of corpus admission; no latent source identity is invented.

Evidence: `reports/global-seed-containment.json`, its actual checker, `reports/seed-containment-tests.xml`, `reports/global-grouping-input.json` and its checker. Raw seed patterns, databases and root maps remain ignored. Full project scope and all learning/portability/teacher/tool/ESCI gates remain active.
