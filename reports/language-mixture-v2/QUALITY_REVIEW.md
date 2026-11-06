# Proposed 60M language pilot: quality review

Recommendation: a bounded 30M story + 30M web pilot is a more useful language-learning hypothesis than blindly adding another web-only tranche, but this review does not justify a quality-pass claim or launching training. The web quality is materially uneven. The existing custody-cleared pool is not synonymous with a clean or fact-checked corpus. Root must choose the budget and acceptance criteria separately.

The frozen deterministic sample contained 32 complete train documents per source, eight from each document-token-length quartile. All 64 were read. Raw samples remain only under ignored `data/language-mixture-v2/`; that directory also holds judgments, checksummed selection, proposed exclusions and the count receipt. Selection and recount took under 7 CPU seconds; no GPU, download, packing, or corpus mutation occurred. These document-stratified subjective judgments are not population defect estimates or statistical certification.

| Source | Retain | Review | Hold | Main observations |
|---|---:|---:|---:|---|
| TinyStories | 25 | 4 | 3 | Mostly complete short narratives. Three have abandoned plots or unsupported causal resolutions; four have awkward vocabulary/timeline/contrivance. Repeated character names, formulaic openings and morals narrow the style. |
| Retained web | 7 | 16 | 9 | Nine strong concerns: stitched essay fragments, dictionary/navigation mixture, repeated SEO FAQ, promotional link lists, questionable medical cure/treatment statements, sweeping solar claims, and an explicit Wikipedia derivative. Sixteen others have lesser boilerplate, broken extraction, repetition or factual concerns requiring review. |

No model-role or system-prompt leakage was observed in the 64. Ordinary instructional prose and quotations are not role leakage. No external factual verification was performed: suspect assertions are reasons to defer documents, not claims of verified falsehood. Fictional animals and fantasy were judged as fiction.

A material lineage limitation surfaced: a New World Encyclopedia document explicitly says it was rewritten from Wikipedia. Excluding `wikipedia.org` URLs alone cannot exclude mirrors/derivatives. The proposed narrow additional rule excludes `newworldencyclopedia.org` URLs or explicit derivative attribution phrases listed in `review.py`. It does not prove comprehensive semantic or mirror exclusion.

For a conservative count-only proposal, defer all 32 individually flagged samples (7 story, 25 web), plus that derivative rule applied read-only across the entire custody-eligible pool. This removes 7 story documents/1,361 tokens and 42 web documents/85,418 tokens, including overlaps. It does not repair unreviewed analogues of the sampled defects.

| Source | Remaining train documents | Remaining train tokens | Unchanged validation tokens |
|---|---:|---:|---:|
| Stories | 169,204 | 31,494,305 | 629,749 |
| Web | 46,816 | 41,602,743 | 821,413 |

Both 30M quotas are available without duplication. These are verified document token counts including EOT, not a final packed target count. The story surplus is only 1.49M: a broad quality screen removing more than about 4.7% of remaining story tokens would miss the quota. Preserve original family/domain validation assignment and custody exclusions; do not replace withheld content to reach quota.

The proposed mixture gives the model short, explicit narrative dependencies absent from much of the noisy web sample, while preserving broader prose. A 50% story share could also encourage childish/formulaic output. Any experiment should retain original web loss/context/raw-generation checks, add source-stratified heldout document loss, and inspect transfer beyond narrative continuation. Most stories are shorter than 512 tokens: heldout evaluation needs variable-length document masking, not silently discarding short stories or crossing heldout document boundaries. Story fluency cannot count as conversational competence or tool-result grounding. This pilot contains no adequate dialogue supply and no tool-call supervision; those remain separate unmet capabilities.

A mixture run alone cannot establish superiority over a matched web-only run. If only one extra run is budgeted, describe it as a targeted probe; never claim causal evidence that the mixture beats web-only. The current sample suggests an additional bounded web-quality screen is worthwhile before treating these retained tokens as a final recipe.
