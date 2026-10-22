# Semantic admission review — 21 October 2026

**The remaining pool is sufficient for a narrow short-story feasibility experiment, but insufficient evidence for approving a general English SLM or the proposed 17.3M model. No training or model initialization occurred.**

## Exact admitted counts

These supersede the mechanically eligible 117,620 documents / 51,604,297 content tokens. Counts are exact for the admitted manifest, not an estimate obtained by multiplying corpus size by a sample pass rate.

| Split | Documents | Content tokens | With one EOS per document |
|---|---:|---:|---:|
| Training | 72,065 | 15,295,273 | 15,367,338 |
| Development | 3,999 | 848,330 | 852,329 |
| Test | 3,923 | 831,587 | 835,510 |
| **Total** | **79,987** | **16,975,190** | **17,055,177** |

All admitted records are TinyStories. Tokens use the retained 16,384-total-vocabulary BPE, SHA256 `0044125dd66d4414a4f7dabf9cdfe356dfdcbd7b91a09393fa28fe6bfac30a64`. Counts will change under a different tokenizer. No tokenizer was trained.

| Change from mechanical audit | Documents excluded | Content tokens excluded |
|---|---:|---:|
| Ten failed TinyStories families | 10 | 2,157 |
| FineWeb source quarantine after failed semantic gate | 37,623 | 34,626,950 |

Cosmopedia's 49,064 documents / 39,380,839 tokens remain excluded for unresolved seed ancestry, as in the mechanical audit. Quarantine means excluded from the new admission manifest; original text and evidence remain preserved. FineWeb's quarantine does **not** mean all its documents are poor quality. Good articles were observed, but the source cannot currently be counted as passing the corpus admission policy.

## What I actually reviewed

I directly read **231 complete texts**, totaling **69,592 content tokens**: 200 TinyStories and 31 FineWeb. This was an assistant review, not an independent human audit or full factual verification. Truncated tool outputs were reread before recording a judgment.

Before reading, I selected 200 training records per source by SHA256 rank with the fixed seed recorded in `policy.json`. This is a deterministic pseudorandom document sample with equal selection opportunity within each source, not a handpicked showcase. Length was not restricted: the FineWeb review included a 5,158-token audio engineering feature. Development and test texts were not inspected for this review. The findings target the training population; heldout semantic quality was not separately measured.

The proposed gate was at least 95% readable, complete English and at most 2% major corruption/off-topic boilerplate. I assessed narrative continuity, intelligible causal links, standalone completeness, grammatical corruption, extraction debris, and usefulness as English prose. Fantasy, unhappy endings, disagreement, product-specific explanations and unfamiliar topics were not automatic failures. Minor labels include awkward wording, weak lessons and factual caution; they count as usable for language experimentation, not as endorsed advice. Substantive coherence errors fail. Unsupported certainty was also flagged; medical, legal and historical statements were not independently verified.

Before opening any FineWeb sample, I added a rejection-only stopping rule: stop once the fixed 200-record sample contains more than four major failures, or more than ten total failures. This can establish failure without pretending unread documents passed. There is no early acceptance rule. This is an explicit conservative change from reading all 200 before a decision.

| Source | Fully read | Pass without noted issue | Usable with minor issue | Failed | Admission outcome |
|---|---:|---:|---:|---:|---|
| TinyStories | 200 | 137 | 53 | 10 | 190/200 usable: exactly 95%, borderline sample pass |
| FineWeb | 31 of 200 selected | 11 | 11 | 9, including 5 major | Reject: at least 5/200 = 2.5% major, even if all unread records pass |

**169 FineWeb records were selected but not read.** Do not report this as a 200-document completed FineWeb review or extrapolate 22/31 to a population usable-token count. The stopping rule establishes admission failure, not a precise population defect rate.

TinyStories' 95% sample pass is also not proof that 95% of its entire corpus is good. The descriptive 95% Wilson interval is approximately 91.0–97.3%. There is no safety margin at the proposed threshold. Excluding ten observed failures does not make unseen failures disappear. These are exact *policy-admitted* counts, not a census of individually semantically certified records.

## Findings from the texts

TinyStories has clear value for short narrative syntax, simple dialogue, pronouns, sequencing and everyday vocabulary. Longer stories in the sample sustained readable conversations and resolutions. However, the recurring children/pets/balls/parks, stock names and repeated friendship/sharing endings show limited thematic breadth. Exact and shingle deduplication do not remove this kind of template similarity.

Examples of failed TinyStories records:

- `110568`: the ending says the horse advised minding the barn; earlier it explicitly proposed leaving it unattended.
- `107851`: a wrapped novel becomes a cat without a substitution or magical explanation.
- `127509`: a “little zip” inexplicably resizes sunglasses; the central solution is not intelligible.
- `127244`: a mark is predicted to return tomorrow, returns immediately, and the narrator claims the prediction was fulfilled.

Minor records also contain poor practical/social lessons: consuming found food, praise for risky behavior, simplistic emotional advice and parental intimidation. The corpus is not a vetted children's education or safety dataset. These concerns matter if the intended product teaches facts, gives advice or targets children; they do not all make fictional sentences unusable for a narrowly defined language experiment.

FineWeb contains useful coherent journalism, history, policies and technical exposition. The audio-loudness interview (`172904`), Danish Easter-letter explanation (`148699`) and school honesty policy (`228744`) are examples. But the accepted mechanical pool still contains:

- `135377` and `135633`: pervasive word-spun prose and grammatical damage in health articles.
- `146369`: clipped article mixed with unrelated news links.
- `174354`: a link roundup dominated by activity titles and provider names, without the underlying experiment instructions.
- `169031`: booking/refund/FAQ boilerplate with contradictory group-size limits and repeated material.
- `148243`: related words repeatedly mislabeled as antonyms—particularly damaging for an English-learning objective.
- `144632`: omitted test headings attach explanations to the wrong preceding tests.

These are failures the language-ID and surface filters did not resolve. A simple keyword purge would not establish that the remaining FineWeb content is sound. Recovering FineWeb requires extraction/semantic repair followed by a fresh independent sample; no recovered volume is assumed here.

## Sufficiency decision

- **Narrow research feasibility: enough data to investigate short-story language learning**, if subsequently authorized. There are 15.30M unique training content tokens and separate family-disjoint development/test pools. This is a volume-and-coverage assessment, not measured model capability.
- **General English foundation, factual understanding or conversation: not sufficient to approve.** The admitted pool is entirely synthetic short fiction. It does not adequately cover adult expository prose, grounded explanations, broad registers or conversational pragmatics. The useful FineWeb examples cannot substitute for a passing source audit.
- **Model size remains unresolved.** The previous 17,308,032-parameter recommendation is withdrawn pending revised design. At the current tokenizer, one pass offers about 0.884 unique training tokens per proposed parameter; three exposures offer 45,885,819 content-token presentations but still only 15,295,273 unique content tokens. This arithmetic is not a scaling-law claim or proof of a suitable size. Repetition cannot supply missing genres.
- Corpus test loss alone would only measure this narrative distribution. The separate sealed English capability suite remains to be materialized; it is not supplied by the TinyStories test split.

## Reproducibility and checks

- `sample.json`: fixed ordered sample, IDs, original references, hashes and token counts, including unread FineWeb selections.
- `judgments.jsonl`: one direct-reading decision and text-specific rationale for each of the 231 reviewed records.
- `accepted-manifest.csv` / `excluded-manifest.csv`: exact retained/excluded records and exclusion reasons.
- `results.json`: machine-readable counts, sample results and limitations.
- `verification.json`: independent full re-tokenization, original-text hash and roundtrip checks for every retained record; exact duplicate and cross-split family checks.
- The admitted manifest is an unchanged subset of the pinned mechanical manifest, preserving its near-duplicate and known evaluation-overlap exclusions. No reshuffling or new data was introduced. Semantic paraphrase leakage was not exhaustively proven absent by the earlier shingle checks.
- `receipt.json`: hashes of review artifacts; `boundary-verification.json`: runtime guard result. No model weights were allocated or loaded.
