# FineWeb salvage — limited recovery, 21 October 2026

**Recovered 51 individually reviewed FineWeb documents / 22,245 content tokens. The revised automatic filters did not pass fresh validation, so no unreviewed FineWeb volume is admitted. This is a small recovery, not a successful bulk cleanup. No training or weight initialization occurred.**

## Current usable counts

| Split | Documents | Content tokens | With one EOS per document |
|---|---:|---:|---:|
| Training | 72,116 | 15,317,518 | 15,389,634 |
| Development | 3,999 | 848,330 | 852,329 |
| Test | 3,923 | 831,587 | 835,510 |
| **Total** | **80,038** | **16,997,435** | **17,077,473** |

TinyStories remains 79,987 documents / 16,975,190 content tokens. FineWeb adds 51 / 22,245, all in their original training split. FineWeb development and test remain excluded. Cosmopedia remains ancestry-quarantined. The remaining mechanically eligible FineWeb quarantine is 37,572 documents / 34,604,705 content tokens; this is not a claim that every quarantined document is bad.

Counts use the unchanged 16,384-total-vocabulary tokenizer, SHA256 `0044125dd66d4414a4f7dabf9cdfe356dfdcbd7b91a09393fa28fe6bfac30a64`. They are exact sums of admitted original texts, independently re-tokenized. FineWeb admission is document-by-document; TinyStories admission still rests on the earlier sample, not a full semantic census. Neither is a factual certification.

## Filtering and fresh validation

The new deterministic screen is in `../fineweb-salvage-v1/filter.py`. It rejects:

- Links, markup, encoding damage, list layouts and short heading fragments.
- Incomplete paragraph endings, too few sentences and unsuitable paragraph structure.
- Commercial/signup/refund boilerplate, missing-media references and exercise templates.
- Medical-advice/claim keywords, where earlier findings exposed unreliable prose.

For this recovery attempt, the scope was deliberately restricted to **120–480 tokens and 2–12 paragraphs**, with at least eight words per paragraph. This is a conservative short-prose slice, not a claim that longer articles are unsuitable. Rejected text was not rewritten, truncated or repaired by inventing missing headings. All nine earlier semantic failures are rejected by content rules without document-ID exceptions; a previously good text survives. Three regression tests pass.

From the 37,623 mechanically accepted FineWeb documents, the screen retained **1,700 documents / 512,728 tokens**, including 1,520 training documents. This excluded all families belonging to the earlier 200-record review selection, so old examples could not become fresh validation evidence.

Before reading the new texts, I froze the filter code, seed, candidate manifest and **200-record pseudorandom training sample**. Selection did not prefer short records within the retained slice. I read **55 complete documents / 15,560 tokens** from that sample:

| Judgment | Count |
|---|---:|
| Pass, no material issue noted | 15 |
| Readable but minor issue | 26 |
| Fail | 10 |
| Major failure | 4 |

There are **14 failures**, already more than the ten allowed in a 200-record sample. Even if all remaining records passed, usability would be at most 186/200 = 93%, below the required 95%. Review stopped after the current batch; **145 selected records remain unread**. No sample pass rate was extrapolated into an exact usable population. The rules were not tuned on this sample and then passed off as independently validated.

Specific surviving failures demonstrate why the screen cannot support bulk admission:

- `161670`: dictionary text with a missing headword and an unrelated CV-writing sentence.
- `162906`: museum history concatenated with an unrelated European-art survey.
- `169540`: missing crack-category headings leave repeated “this crack” references unresolved.
- `147581`: a 1914–1918 framing mixed with 1940–1944 events and a confused trench-foot description.
- `174167`: disconnected programming/career fragments without the needed topic and section context.

Some clinical and health-promotion material also evaded the keyword rules. Broadening a blacklist would not prove that remaining fluent claims were sound.

## Recovery that is defensible

After that failed gate, I reviewed **all 59 remaining training records** in the short-prose slice hosted on `.edu`, `.gov`, `.ac.uk` or `.gov.uk`, excluding every family in the fresh 200-record sample. This was a complete review of a narrow retrieval set, not another representative population sample. Institutional hosting was used to find candidates, **not to automatically admit them**.

Those 59 full texts / 17,350 tokens produced 26 passes, 27 minor issues, three failures and three major failures. They included research abstracts, historical accounts, educational essays and public-agency explanations. Institutional pages also contained resource navigation, merged lessons, OCR damage and missing context.

The final admission rule is conservative: **a recorded full-text pass with no noted material issue, and no reviewed failed family**. Minor records stay quarantined rather than being silently repaired. Previously reviewed clean documents can be recovered as training material even though the source-wide gate failed; they are not reused as independent validation evidence.

| Review evidence | Passes considered |
|---|---:|
| Earlier FineWeb review, 31 full texts | 11 |
| Fresh filtered sample, 55 full texts | 15 |
| New institutional-slice census, 59 full texts | 26 |
| **Total individual passes** | **52** |
| Excluded because another reviewed record in the family failed | **1** |
| **Recovered** | **51** |

Record `144127`, a readable wetland-restoration abstract, was excluded because its family contains a reviewed failure. Family grouping remains conservative; this is not a finding that the abstract itself is bad.

This turn added **114 complete-text reviews / 32,910 content tokens**. Across both turns, 145 FineWeb texts / 60,481 content tokens have been directly read. Per-record rationales and original references are preserved. These are assistant judgments, not independent human labels or expert fact-checking.

## Sufficiency and limits

The recovery adds about **0.15%** to the prior training-token count. It does not materially change the sufficiency decision: enough for a narrow short-story feasibility experiment, still inadequate evidence to approve a general English foundation, conversation capability, or the prior 17.3M model proposal. The admitted training set remains overwhelmingly TinyStories. There is no admitted FineWeb heldout set with which to claim expository generalization.

The automatic filter has improved its handling of the known mechanical failures but has **not solved semantic admission at scale**. The working admission filter therefore requires an explicit reviewed-document allowlist. Wider recovery would require reliable article-boundary/extraction repair and semantic checking, followed by a genuinely new validation set. Unreviewed rejected long articles remain possible recovery candidates; their quality has not been measured here.

## Evidence and verification

- `results.json`: exact revised counts and review outcomes.
- `recovered-fineweb-manifest.csv`: 51 recovered original records and provenance.
- `accepted-manifest.csv`: current combined corpus; supersedes the semantic-review-v1 manifest.
- `excluded-manifest.csv`: complete reconciliation against the original mechanical pool.
- `judgments.jsonl`: the new 59-record census; fresh sample judgments are in `../fineweb-salvage-v1/judgments.jsonl`.
- `../fineweb-salvage-v1/policy.json`, `sample.json`, `filter-summary.json`, `validation-result.json`: frozen filter experiment and failed fresh validation.
- `verification.json`: full retained-corpus re-tokenization, hashes, roundtrips, duplicate and split checks, and direct-pass/family assertions for recovered FineWeb.
- `boundary-verification.json`: initialization, loading, training and resume remain blocked before model/data access.
- `receipt.json`: hashes of the final artifacts and referenced filter/review inputs.

Every recovered text is an unchanged subset of the original mechanically screened manifest. Its prior near-duplicate and known evaluation-overlap exclusions are preserved; no resplitting or evaluation-text review occurred. The earlier audit does not establish zero semantic-paraphrase leakage. No model, tokenizer or classifier was trained; no new source data was downloaded.
