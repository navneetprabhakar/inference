# SNLI CPU feasibility diagnostic

**The premise helps on held-out SNLI captions, but these results do not justify using SNLI to repair the student’s paraphrase gap.** On 532 independently unanimous validation pairs, lexical premise–hypothesis matching raised class-balanced accuracy from 80.42% to 87.24%. The paired, source-family bootstrap interval for that gain is +2.68 to +12.76 percentage points. Reassigning premises reduced the same classifier to 73.33%, demonstrating real dependence on the provided premise. The admission procedure itself selects for lexical alignment, so this result does not establish broader semantic transfer.

| Primary training, 8,919 unanimous pairs | All 532 unanimous validation pairs | 516 unanimous pairs without explicit negation |
|---|---:|---:|
| Hypothesis only | 80.42% | 63.51% |
| Independent word bags from both sentences | 81.34% | 72.86% |
| Hypothesis words plus coarse overlap, lengths and negation | 83.86% | 66.99% |
| Pair matching with shared and introduced words/phrases | 87.24% | 79.01% |
| Pair matching, validation premises reassigned | 73.33% | 56.15% |

All percentages are macro recall over the three labels. Independent word bags let the classifier use premise words without representing which words match. The coarse-overlap condition was added after observing the primary comparison, with the optimizer and data unchanged. Reassignment was within annotation tier and approximate premise length; its original labels serve only as a sensitivity check.

## Errors and denominators

| Validation label | Total | Hypothesis correct | Pair correct | No-negation total | Hypothesis correct | Pair correct |
|---|---:|---:|---:|---:|---:|---:|
| Entailment | 319 | 267 | 279 | 317 | 267 | 278 |
| Neutral | 199 | 143 | 162 | 196 | 143 | 162 |
| Contradiction | 14 | 12 | 13 | 3 | 1 | 2 |
| **Total** | **532** | **422** | **454** | **516** | **411** | **442** |

The pair model corrected 57 hypothesis-only errors but introduced 25 errors, for a net gain of 32. Its 78 errors include 39 entailments called neutral, 34 neutrals called entailment, one entailment and three neutrals called contradiction, and one contradiction called entailment. Only three non-negated contradictions exist. One additional correct contradiction changes that slice’s macro score by 11.11 points. Among the better-populated non-negated entailment and neutral classes, mean recall increased from 78.59% to 85.18%; coarse overlap alone reached 83.82%. Thus most of the improvement on these two classes is attainable without learning which added or shared words matter. There are no internal-validation groups with an identical normalized hypothesis assigned different original labels under distinct premises.

## Source scope

The independent custodian excluded 10,407 source pairs. This diagnostic verified the original train/validation digests, denylist digest, authorized count, and disjoint source-image/premise groups before fitting. The primary training distribution was 5,173 entailment, 3,491 neutral and 255 contradiction. Adding the eligible singleton tier yielded 41,008 training rows with 35,877 entailment, 3,798 neutral and 1,333 contradiction. It raised the pair model’s unanimous-validation score by 0.04 points, from 87.24% to 87.28%. On all 2,754 validation rows (2,437 entailment, 216 neutral, 101 contradiction), the unanimous-trained model scored 84.49% hypothesis-only versus 91.77% conditioned; the all-cleared model scored 83.34% versus 93.40%. Those broader figures also measure the stronger rule-based screens applied to singleton records.

This was a one-core NumPy linear-classification experiment; neither GPU nor student weights were used. The surface-overlap control and absence of same-hypothesis label reversals limit the case for a semantic intervention. No A, B or confirmation material was accessed. results.json records per-class confusion matrices, raw denominators, changed-decision counts, family-bootstrap intervals, and example error IDs. To reproduce:

    OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 15 .venv/bin/python reports/snli-semantic-diagnostic/diagnose.py
