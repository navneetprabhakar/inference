# Full automated foundation-data audit — 21 October 2026

**No model sizing or training is approved.** These are exact counts under the documented operational quality, provenance and leakage policy. The previous ~104M-token estimate is superseded.

**Usable pool: 117,620 documents, 51,604,297 content tokens.** This includes the new development and test reservations. The training-only total is below.

## Exact final split

| Partition | Documents | Content tokens | Tokens including one EOS/document | Families |
|---|---:|---:|---:|---:|
| train | 105,789 | 46,451,603 | 46,557,392 | 94,644 |
| development | 5,780 | 2,495,946 | 2,501,726 | 5,279 |
| test | 6,051 | 2,656,748 | 2,662,799 | 5,133 |

Tokens are exact encodings of **every original record**, with UTF-8 roundtrip assertions, using the retained 16,384-total-vocabulary byte BPE. Tokenizer SHA-256: `0044125dd66d4414a4f7dabf9cdfe356dfdcbd7b91a09393fa28fe6bfac30a64`. Content totals exclude structural markers and padding. Counts including one EOS per document are reported separately. A future 8k tokenizer changes these counts; no tokenizer was fitted here.

## Exclusive document/token waterfall

| Source / step | Documents | Content tokens |
|---|---:|---:|
| **TinyStories: raw** | 131,323 | 28,077,733 |
| Official heldout | 49,620 | 10,775,619 |
| Unresolved ancestry quarantine | 0 | 0 |
| Quality rejected | 1,341 | 222,381 |
| Evaluation/connected-family excluded | 365 | 102,386 |
| Duplicate removed | 0 | 0 |
| **TinyStories: usable** | **79,997** | **16,977,347** |
| **FineWeb: raw** | 49,000 | 55,821,298 |
| Official heldout | 18 | 15,665 |
| Unresolved ancestry quarantine | 0 | 0 |
| Quality rejected | 7,041 | 17,546,640 |
| Evaluation/connected-family excluded | 4,310 | 3,626,879 |
| Duplicate removed | 8 | 5,164 |
| **FineWeb: usable** | **37,623** | **34,626,950** |
| **Cosmopedia: raw** | 49,064 | 39,380,839 |
| Official heldout | 0 | 0 |
| Unresolved ancestry quarantine | 49,064 | 39,380,839 |
| Quality rejected | 0 | 0 |
| Evaluation/connected-family excluded | 0 | 0 |
| Duplicate removed | 0 | 0 |
| **Cosmopedia: usable** | **0** | **0** |

Each raw record appears in exactly one exclusion category or the usable pool; both document and token totals reconcile. The exclusion order is official holdout → unresolved ancestry → quality → evaluation family → deduplication. Overlapping quality reasons are separately available in `results.json`.

## What was completed

- **Full content audit:** 229,387 original foundation-candidate records; 432,499 records/facets including protection material. No sample extrapolation in the counts.
- **English checks:** 828,327 whole-document/window classifications; every 1,024-character window with at least 40 alphabetic characters checked, threshold English probability >=.8. Literal `</s>` markers initially split classifier lines; the input-only projection was fixed, the entire classifier pass rerun, and exact prediction-to-record alignment verified. Original text/tokenization was unchanged.
- **Quality:** length, encoding/control characters, literal escapes, prose-character ratio, repeated lines/words/five-grams, markup/boilerplate, contact/secret signals, table/caption density, promotional calls to action and embedded model markers. Rules and the small direct-review exclusion are recorded before final tallying.
- **Duplicates:** complete prefix-filtered all-pairs search at five-word-shingle Jaccard >=.8, without sampling or truncation. 59,893 exact representative links and 3,276 verified near links across the full input/protection pool. These are graph links, not counts of independently removed training documents. All proposed near links were rechecked with exact string shingles; hash false-positive edges: 0.
- **Leakage:** official TinyStories validations; historical heldout/blocked source records; every SQuAD paragraph; full upstream conversation-test message facets; all retained evaluation-exclusion versions and complete contexts; applicable evaluation configs; upstream TinyStories evaluation prompts; current public English-gate examples. Full protected-text and contained-span checks propagate exclusions to connected families.
- **Families:** original source IDs, source URL/host families and exact/near components. Host grouping uses the final two DNS labels conservatively, so e.g. `co.uk` may overgroup; it does not split known subdomain families. All known connected family members stay together.
- **Partition verification:** no known family crosses train/development/test; no normalized exact duplicate survives; only one representative per verified near component; no protected-family member survives. Full document/token accounting passes. Matching kernels were checked against brute-force/synthetic controls without loading a project model.

## Why Cosmopedia contributes zero usable tokens

All 49,064 locally inspected Cosmopedia records are quarantined. Seed excerpts and labels do not reliably establish the underlying source-document identity; excluding only exact seed excerpts would leave unknown document-family leakage. This is a conservative admission decision, not a claim that the text is inherently useless. Recoverable provenance could justify a separate future audit. Its tokens must not be counted in the current usable foundation budget.

## Scope and remaining limits

- “Usable” means **passes this full operational audit**, not human-certified factual accuracy or a guarantee of coherent English. Direct review was a small spot-check; the earlier proposed 200-document/source human review has **not** been completed. That proposed semantic-quality sign-off remains distinct from these now-exact technical counts.
- Five-word Jaccard is lexical similarity, not semantic equivalence. Unknown paraphrases or upstream ancestry cannot be exhaustively excluded. Near candidate retrieval uses 64-bit shingle hashes and exact-string confirmation; theoretical hash-collision false-negative risk is not zero. Containment searches full protected strings >=12 words plus 32-word protected blocks at stride 16; any shared contiguous 47-word span contains a checked block. Short labels only exclude whole-document equality.
- This is the frozen foundation pool from the previously inventoried original TinyStories/FineWeb/Cosmopedia snapshots. Explicit conversation/instruction datasets remain reserved for later stages. Wikipedia/SQuAD and other unresolved or uncounted small legacy samples are not silently added. This is not a maximum possible count across every historical transformation.
- Ordinary adult prose and real dialogue remain weak relative to simple synthetic narrative. An exact token count does not repair that coverage gap. The 17.3M model and 8k tokenizer remain unapproved design hypotheses.
- Existing protected evaluation data is not a fresh sealed acceptance set. New development/test corpus reservations prevent known overlap but do not create the independently held capability acceptance suite.

## Reproducible artifacts

- `accepted-manifest.csv`: original reference, original/normalized hashes, exact tokens, split and family ID for every usable document.
- `dispositions.jsonl`: a final disposition and reasons for every original candidate record.
- `results.json`: complete counts, exclusions and verification assertions.
- `audit.sqlite`: read-only source copies and pinned input identities for reproducible inspection; an audit database, not a training release.
- `policy.json`, `quality-addendum.json`, matching/scanning programs and their checks: executable definition of the count.
- Training/init/resume guards remain active. No weights were initialized, no training ran, and no cloud or new training-data acquisition was used.

## Measured duplicate rates in the original snapshot pool

| Source | Normalized exact redundant records | Exact redundancy | Records in nonexact near components | Near-component participation |
|---|---:|---:|---:|---:|
| TinyStories | 422 | 0.3213% | 0 | 0.0000% |
| FineWeb | 5 | 0.0102% | 8 | 0.0163% |
| Cosmopedia | 22 | 0.0448% | 4 | 0.0082% |

Denominators include official heldouts and precede filtering. These rates overlap and cannot be added. Near participation requires multiple distinct normalized candidate texts in a connected component; it is not a semantic/plot-duplication rate. Most near links in the expanded audit pool connect protection facets rather than distinct original candidate documents.

## Independent verification

Every one of the 117,620 accepted original texts was independently re-encoded from the reference manifest. All original-text hashes, token counts and UTF-8 roundtrips matched; split totals reconciled exactly. The independent check also confirmed unique normalized content and disjoint family sets. See `independent-verification.json`.
