# V3 result: current web pool cannot support the proposed pilot

Do not admit the existing web pool or lower the quality threshold to manufacture a 30M quota. A floating publisher score of at least 4 plus the prospective whole-document filters retains only 809,031 train tokens. The 30M web target is short by 29,190,969 tokens before the new manual deferrals. Raising the score further leaves almost nothing. These counts preserve original splits, root custody and all v2 proposed exclusions.

| Floating score | Train tokens before filters | Train tokens after filters | Train documents after | Validation tokens after | Validation short/long documents |
|---|---:|---:|---:|---:|---:|
| >=4 | 891,386 | 809,031 | 919 | 20,725 | 1 / 27 |
| >=4.5 | 25,300 | 23,460 | 34 | 0 | 0 / 0 |
| >=5 | 0 | 0 | 0 | 0 | 0 / 0 |

Short means 32–127 usable targets; long means >=128; usable targets are stored GPT2+EOT count minus one. Counts are not the publisher's token_count. Validation at >=4 has only 28 documents, so it also misses the earlier 128-document source minimum.

The raw parquet contains floating `score` and integer `int_score`. Among 47,814 custody/v2-eligible web documents (both splits), integer scores are 3:41,375; 4:6,409; 5:30. Integer and floating thresholds are different: the observed integer5 rows still have floating scores below5. Do not silently interpret int_score>=4 as score>=4. All source-row IDs matched the raw rows, and the 2.15GB source hash matched the existing receipt.

The frozen filters defer whole documents with repeated FAQ questions, repeated lines, large trailing runs of short navigation-like lines, or five distinct boilerplate phrases. At score>=4, 30 documents trigger FAQ and26 trigger trailing-short-lines, with overlap; neither the duplicate-line nor multi-marker rule triggers there. These heuristics are deliberately simple and may remove legitimate FAQs/lists. They do not repair missing equations, unsupported claims or semantic inconsistencies.

The 16 new deterministic quartile samples were frozen before reading, never rerolled, and all read in full: **5 retain / 6 review / 5 hold**. Strong defects include a course-promotion list, lesson text whose promised definitions and diagrams are absent, repeated climate-report paragraphs, an astronomy article with contradictory convection prose and implausible assertions, and an electronics tutorial missing essential formulas. Lesser concerns include detached glossary fragments, unqualified learning-style claims, diagram-dependent geometry and suspect technical simplifications. No external fact-checking occurred; these are review flags, not verified factual-error statistics. No model-role leakage was found. This small subjective sample cannot certify the population or prove improvement over v2.

Defer all eleven flagged samples provisionally: that leaves 796,609 train tokens within the >=4 filtered set. This is not a viable 30M web tranche. The story pool is unchanged, but replacing missing web tokens with stories or repeats would change the experiment and is not authorized by this review.

Next useful option is a separately bounded **fresh high-score raw intake**, with score distribution/yield checked before a large download, existing lineage/custody rules retained, and a fresh deterministic content audit. Higher score alone is insufficient: extraction completeness and factual/structural quality need attention. A smaller mixed pilot is an alternative only under an explicitly revised budget and adequate heldout-source coverage; the current <0.8M strict web supply is too small to preserve the proposed 30M/30M design. No new acquisition, packing or training was performed.

Artifacts: `profile.py` reproduces the metadata join and counts; `record_review.py` records fixed judgments. Raw samples and all receipts remain in ignored `data/language-mixture-v3/`. CPU profile took34.97 seconds using one thread; artifact storage is below100MiB. v1 and v2 artifacts are untouched.
