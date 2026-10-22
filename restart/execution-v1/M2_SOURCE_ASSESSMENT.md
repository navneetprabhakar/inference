# M2 source supply assessment — initial evidence

Status: incomplete. Owner authorized 80 GB downloads and local laptop storage. Initial FineWeb-Edu pilot shard downloaded; no new training admission. See m2-intake/acquisition-status.json and disk-budget.json.

The prior full local census reports approximately 28.2M raw TinyStories tokens and 55.9M raw FineWeb tokens under its historical tokenizer. These are estimates before quality/leakage exclusions, not usable supply. Local Wikipedia contains only 64 raw documents. Cosmopedia remains excluded for unresolved ancestry. Conversation/QA corpora cannot silently replace the broad prose mixture. The existing local supply cannot support the roadmap's 0.5–2B distinct-token investigation range, even before losses from quality review.

Current authoritative admitted release remains fineweb-salvage-reviewed-v1, with 72,116 training documents. Under the fresh M1 8k tokenizer these contain 14,397,833 content tokens. Retokenization creates no additional content or rights clearance.

## Source candidates to investigate

- **Wikimedia Wikipedia**: reference/expository coverage. Pin a specific snapshot, page IDs, URLs, revision and attribution metadata. Review current dataset license and text licensing before intake; document transformations and share-alike obligations. Reserve whole pages/families and protect existing SQuAD and Wikipedia-derived evaluation ancestry. Do not equate page formatting cleanliness with factual correctness.
- **FineWeb/FineWeb-Edu**: broader human web prose and explanatory prose. Their collection license does not itself certify every underlying page's rights or factual quality. Edu scores are a source-selection aid, not a replacement for our 200+200 semantic checks. Group related extracts/URLs and cross-deduplicate against all existing FineWeb and protections. Count Edu and FineWeb as one source family for the 30% mixture ceiling when one is a subset of the other.
- **Long-form narrative/nonfiction with explicit provenance**: needed to avoid a story/web-only or encyclopedia-only mixture. Project Gutenberg is a candidate for per-work investigation, not blanket admission: its own guidance is jurisdiction-specific and does not establish unrestricted use in India. Record work/author/translation/edition-level status. Prefer sources with explicit reusable terms and established local applicability.
- **Instructional/explanatory material**: investigate openly licensed textbook or educational prose, preserving book/chapter ancestry and attribution. A source cannot be admitted just because it fills the >=10% genre quota.

Sources checked 2026-10-21:
- https://huggingface.co/datasets/HuggingFaceFW/fineweb
- https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu
- https://huggingface.co/datasets/wikimedia/wikipedia
- https://www.gutenberg.org/policy/permission.html
- https://www.gutenberg.org/policy/license.html

## Acquisition and repair protocol

Use the owner-approved 80 GB download cap and local disk-budget.json reservations; paid services/cloud budget remains zero. First download metadata and a small, reproducible, geographically/domain-diverse candidate sample within that cap, not an entire corpus. Freeze cohort definition and extraction before probability sampling. Preserve raw text and separate repaired text with parent hash and explicit transformation log. Reconstruct article boundaries from available source structure; do not invent missing continuations or ask a teacher to silently rewrite failed pages.

For every source x extraction cohort, review 200 randomly sampled full documents and an additional 200 token-weighted full documents. Label pass/minor/fail/major with reasons, primary disjoint genre and factual-risk flags. Review enough to decide the gate; early rejection is permitted when the maximum possible final pass rate already fails, but unread records never count as reviewed. Token-weighted selection needs actual token lengths and published selection probabilities. Report intervals and total distinct reviewed records across overlapping samples.

Only passing cohorts (or individually admitted pass records) advance to language checks, exact/family/near deduplication, protected ancestor exclusions and final tokenizer counts. Recompute overlap after every text transformation. Freeze train/dev/test before tokenizer fitting; raw source availability is not usable supply. M2 cannot pass until the complete mixture, factual-risk audit and all M4 evaluation-domain supplies exist.

## Pilot evidence update — 2026-10-21

The frozen FineWeb-Edu prose-v1 cohort failed the uniform quality gate after 48 full reviews: 11 fail/major labels make the best possible 200-document result 189/200. Its 1,824 candidate documents and 1,976,759 provisional tokens remain unadmitted. Preserve individual salvage opportunities; do not extend this result to the entire source. More shards with this same pipeline are not the next acquisition step.

A deterministic English Wikipedia pilot contains 156,288 raw documents. Eight discovery reads support structural extraction at article/end-matter boundaries and separate exclusion of stubs, lists and disambiguation. These are discovery findings only. Page IDs are clustered in the selected shard, so a future one-shard acceptance result cannot certify all English Wikipedia. Preserve page identity, original text, removed attribution material and transformation provenance. See m2-intake/wikipedia-license-investigation.json for the unresolved historical-card/current-terms discrepancy. No additional usable documents or tokens are claimed.

Wikipedia prose-v1 repair and integrity checks completed: 39,525 candidates / 40,738,120 provisional tokens, with exact retained-prefix/removed-suffix reconstruction and independent raw-source, token-count and sampling verification. The uniform acceptance review then failed at 30 full documents (9 fail, 2 major), so even 170 unread successes would total 189/200. Missing template expansions produce blank values and names inside sentences. This cannot be repaired by trimming end matter. Preserve the frozen failed cohort; a subsequent version must reject or reconstruct these gaps from verified source material and address language quality. All 30 reviewed page families must be excluded from a fresh acceptance sample; unchanged rows cannot be re-labelled to improve the gate. No new usable supply is admitted.
