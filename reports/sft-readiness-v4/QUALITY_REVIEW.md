# V4 objective filtering and fresh review

The targeted filters remove concrete teacher-label failures, but the fresh review still exposes unsupported service claims and instruction failures. **No source is admitted by this result.** Frozen rules were not amended after viewing the new sample; no sample was rerolled.

Thirteen CPU synthetic positive/negative checks passed before the full scan. The scan took about2.4seconds at nice10, one CPU thread, with no tokenization/model/GPU. All inputs, policy/code/test identities and resulting exclusion/sample hashes are recorded in ignored `receipt.json`. Existing v3 corpus, custody, split and review artifacts are unchanged.

| Source | Train docs after objective filters | Assistant targets | Fresh retain/review/hold (8 each) |
|---|---:|---:|---|
| everyday | 774 | 96,343 | 4/2/2 |
| constraints | 134 | 14,677 | 6/1/1 |
| magpie | 13,692 | 3,140,090 | 5/3/0 |
| summarize20k | 3,473 | 126,051 | 8/0/0 |
| summarize5k | 289 | 39,257 | 6/1/1 |
| rewrite | 5,693 | 746,739 | 8/0/0 |

Summary20k loses2,128 train documents:2,055 trigger banned-pronoun,484 trigger sentence-limit,71 trigger unsupported-digit rules (overlapping counts). Rewrite loses41 on numeric preservation; constraints17 on unresolved meta-placeholders; magpie11 and summarize5k5 on identity/external-claim patterns. Validation retains: constraints7docs/759targets; magpie247/55,965; summary20k59/2,026; summary5k13/1,373; rewrite103/12,834; everyday remains0. No protection was relaxed or quota replenished.

All48 new, disjoint, frozen selected histories were read in full. Clear residual failures include invented carpool availability and local yoga studios without location/lookup evidence, promised future social-media scheduling with no execution capability, and an exactly150word request answered in128 whitespace-separated words. Other review flags include unsupported article summary, revenue/profit conflation, dubious acceleration interpretation and a promise to outline factors followed only by referral. The eight new summary20k and eight rewrite samples appear task-aligned; that does not certify their populations or prove improvement statistically.

Defer all11 newly flagged sample IDs in addition to the objective exclusions: **24,044 train histories and4,161,323 assistant targets remain** (see machine receipt for authoritative counts). These are candidate counts, not admitted training rows. Teacher system constraints remain intact; host-policy insertion and current-turn masking still require independent revalidation.

Limitations: sentence boundaries and pronoun detection are operational lexical heuristics. Numeric-literal preservation can overreject legitimate calculations, and misses spelled-out quantities and nonnumeric fact drift. Meta-placeholder filtering does not validate every word-count/bullet/keyword instruction. The external-claim regex misses “found” and future-action promises; it can also misclassify first-person statements inside source-preserving rewrites or quotations. Fiction detection is a narrow marker set, not semantic role-play understanding. Do not claim that a filter hit proves an unverified fact false. General factual correctness, temporal drift, source-meaning preservation and ability claims remain incompletely checked.

The next correction should separately specify expanded external-claim checks scoped to actual assistant commitments (excluding quoted/rewrite speaker text), plus explicit numeric word-count constraints; freeze another version before use. The current receipt and sample must remain intact. No NoRobots intake, generation, packing or training occurred.
