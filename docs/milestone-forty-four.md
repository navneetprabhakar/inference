# Second-iteration dialogue candidates and grouped audit

Creator: Navneet Prabhakar

Date: 19 October 2026

## Candidate extraction

The complete pinned OASST2 snapshot now yields **20,713 metadata-eligible dialogue paths**: 19,662 upstream train and 1,051 upstream validation. There are 5,872 one-user-turn, 13,958 two-user-turn and 883 three-user-turn paths. These upstream partitions are not final training availability.

The retained paths contain 41,900 distinct raw message nodes and 30,974 repeated node occurrences; maximum shared-node occurrence is four. Repeated branch prefixes must not be counted as new semantic examples or distinct training tokens. Four-path selection omits another 7,955 eligible maximal paths. First-blocked branch counts include 8,468 non-English/missing language, 1,725 deleted/missing and 1,352 negative/missing reviews; descendants are not independently counted in those pruning counters.

Every raw tree's complete official membership is rechecked before filtering, including excluded branches. Node text remains exact in the extraction artifact. Rank affects deterministic branch selection only; it grants no correctness or content approval. Only 4,981 extracted paths have rank zero on every assistant turn, illustrating that positive moderation and rank are different signals. Neither is a substitute for actual reading.

Code and reproduction: [candidate contract](dialogue-candidates.md). Candidate evidence: [actual extraction](../reports/milestone-forty-four-dialogue-candidates.json). Raw source/candidates remain outside Git.

## Actual grouped population and audit

The preparation process exited successfully. Grouping took **256.691 seconds**, with a peak main staging database of **887,005,184 bytes**. This excludes journal/sort/output space and is not a whole-machine resource benchmark. It performed 32,895 qualifying near-pair groupings; the combined source/reference population retains **22,826 rows / 7,140 groups**.

The output preserves all **2,237 original frozen heldout rows** with unchanged text and no weaker partition. New candidate-marked rows are **20,589: 17,463 train / 2,093 validation / 1,033 test**. A further 25 input candidate IDs retain their older frozen-reference metadata. Exact ID reconciliation shows 1,071 upstream-train candidates moved to validation and 1,033 to test; none of the upstream validation candidates move to train. Ninety-nine candidate IDs are not retained after cleaner rejection and exact deduplication. The cleaner reports 73 credential-like, five control-character and nine repeated-line rejections; twelve exact duplicates are removed. Combined staging exposure can reach eight because frozen historical paths are retained; new train candidate shared-node occurrence remains at most four.

The quality audit covers **80,973 complete-message windows** and selects **129 paths / 60 whole groups**. Across the combined population it records 596 paths with a non-English top-scoring window, 50 with privacy candidates, 71 with unscored windows and 24 with incomplete top-k output. Flags overlap and are not verified error counts. Technical examples and short messages can trigger attention; absence of a flag does not establish quality or privacy clearance.

The checked training reader refuses this sample-only population. Actual receipts: [preparation](../reports/milestone-forty-four-dialogue-preparation.json) and [partition reconciliation](../reports/milestone-forty-four-partition-reconciliation.json). No normalized exact match to a first-iteration development prompt was found; semantic scenario isolation is still not proved.

## Train-only sizing

The existing 16K prose-pilot tokenizer was loaded without fitting or changing it. On the 17,463 new train candidates:

| Measurement | Result |
| --- | ---: |
| Distinct raw message nodes | 35,249 |
| Content tokens counted once per raw node | 6,282,874 |
| Content-token occurrences across all paths | 8,834,497 |
| Repeated content occurrences from shared nodes | 2,551,623 |
| Full serialized processed positions | 8,974,604 |
| Assistant-supervised positions | 7,797,345 |
| Full paths exceeding 1,024 positions | 1,646 |
| Full paths exceeding 2,048 positions | 170 |

These are candidate sizing observations, not approved tokens or globally unique language. Text shared between different node IDs can still repeat. The positions include message boundaries; full sequences were not truncated. Later admission and context limits reduce available volume. This establishes enough candidate volume to investigate a 10M local experiment, not that a 10M training contract is ready. [Measurement receipt](../reports/milestone-forty-four-candidate-token-measurement.json).

## Review boundary

The [review protocol](../configs/iteration-two-dialogue-review-v1.json) records delegated expert authority with human attestation false, whole-path reading, separate failure classes, and no blanket approval from metadata or sampling. It preserves slang and separates mature-content categories from general quality. Fact-sensitive unresolved claims are not silently certified as true or marked false.

Actual full-text review covers **all 20 sampled new-train paths in six complete groups**, with shared messages read once through their exact DAG lineages. Results: **six suitable for bounded SFW research consideration, nine excluded and five unresolved**. The other **109 sampled rows remain ungraded**. All decisions bind the frozen audit/sample hashes and individual record hashes. Suitable-for-consideration is not training approval.

Observed failures include explicit formatting violations earlier in an otherwise useful conversation, role-label artifacts, answering with an operating system when asked for a laptop model, copied navigation with missing context, and broken list indexing in a code example. The latter was checked against the [historical primary loader implementation](https://raw.githubusercontent.com/langchain-ai/langchain/v0.0.107/langchain/document_loaders/unstructured.py) and a minimal Python list-index probe; the real PDF dependency pipeline was not installed or executed. Travel and historical market-share claims remain unresolved rather than being declared false without checking.

The six groups span length strata with markedly unequal inclusion probabilities. Twenty related paths are not twenty independent source-wide trials. No corpus success percentage, calibrated error estimate or production bound is inferred. [Bound review decisions](../reports/milestone-forty-four-delegated-review.json). `scripts/review-iteration-two-dialogue-sample.py` replays only these frozen judgments and refuses changed input hashes; it is not an automatic classifier.

The next admission decision must identify the exact reviewed population, rule/calibration evidence, source rights, holdout protection, residual risks and finite experiment limits. This artifact does not extend the earlier 1M prose authorization or approve the complete OASST2 source. Second-iteration neural training remains unstarted.

## Validation and next action

- **85 focused checks passed**, covering whole-path filtering, ancestor pruning, complete-prefix size limits, branch caps, corrupted bindings, atomic cleanup, prior staging, official partition verification and offline quality-audit mechanics. Initial extraction/partition subset: 39 passed before two later size-limit checks. Previous full-suite evidence remains historical; it was not rerun here.
- Actual extraction, staging, full-message audit, frozen-reference verification, exact partition reconciliation, train-only sizing and hash-bound review commands completed successfully. The initial broad review display was truncated; the complete untruncated unique-node/path display was subsequently read before recording judgments.
- Next: complete the remaining sampled dialogue review, define candidate eligibility with measured failure evidence, then publish a bounded private research admission decision. After admission, compare representative train-only tokenizers and freeze the next local training/SFT experiment. Do not turn six suitable sampled paths into an approval of unsampled rows or over-replay them as the whole conversation corpus.
- No new neural update, teacher generation, Platform API call or cloud job. Spending authorizations and accepted portability contract are unchanged. Full project goal remains active and incomplete.
