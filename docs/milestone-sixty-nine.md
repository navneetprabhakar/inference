# Prose screening, evaluation isolation and duplicate grouping

Creator: Navneet Prabhakar

Date: 19 October 2026

## Result and decision

Local screening of **1,048 distinct acquired documents** yields **865 candidates /882,610 student-BPE content tokens**. Existing sample-only duplicate grouping assigns **796 train /34 validation /35 test candidates**. All **5,728 ancestral heldout rows preserve their exact text and partition**; no selected candidate text changes during cleaning.

**Do not train from this staging artifact yet.** All ten prior direct-review exclusions/deferrals would pass the automatic signals alone. Their explicit whole-group quarantine prevents admission despite those signals. This is concrete evidence that the language/privacy heuristics do not establish content quality. The next step is broader content review and an explicit finite research policy, not relabeling candidates as verified examples.

No student gradients, teacher calls, dataset downloads, paid resource creation or spending occur. The main cloud-training budget question remains pending. Current control score remains 10/100, zero of eight tasks; the full model goal and useful MLX/CUDA learning gate remain incomplete.

## Non-mutating screening

New `slm.data.prose_screen` examines original source text and emits metadata only. It retains the raw-record hash, original heldout partition and prior review decision. Every result keeps training, factual and privacy verification false and content category unreviewed.

The frozen first screening rule uses source English label/score, all fixed 1,024-character windows with at least 40 letters, a minimum top English detector score of 0.8, a 50-word minimum, a 200,000-character scope limit, encoding/control checks, duplicate-line/single-word repetition signals and existing privacy/credential patterns. Scores are detector signals, not calibrated probabilities. Short fragments below the letter threshold are not independently language-scored; mixed-language passages can still pass. Privacy patterns can also flag public contact information and miss identifying text. No factual, genre or rights classifier is implied.

The existing pinned offline fastText binary/model is reused for **5,392 windows**. Hashes, descriptor, source license metadata and predictions remain retained. This dependency does not initialize student weights or replace the conversation teacher. Complete prediction coverage is required; no prefix-only language check or silent truncation.

Actual first-pass reasons, with overlap:

| Signal | Documents |
| --- | ---: |
| Window English signal | 112 |
| Privacy/credential pattern | 44 |
| Source English signal | 23 |
| Ancestral heldout | 18 |
| Prior direct exclusion | 4 |
| Prior direct deferral | 6 |
| Single-word repetition | 1 |
| Encoding/control characters | 1 |

The 865 candidates remain heavily concentrated in the 2013 crawl: 829 from 2013, 13 from 2018, 11 from 2019 and 12 from 2023. This reflects acquisition coverage and cannot be presented as a representative English mixture or an estimated population acceptance rate.

## Evaluation isolation

The prior role-context guard does not detect a protected request quoted inside an article. A separate `RequestGuard` now checks complete user-request word sequences embedded anywhere in prose, after Unicode compatibility/case/punctuation/whitespace normalization. Word boundaries prevent a matching suffix from becoming a false whole-request match. Reserved evaluation IDs also trigger quarantine.

The actual protected set has **190 distinct normalized requests**, derived from existing 500 conversation candidates, seven tool scenarios and all four completed actual conversation transcripts. The set fingerprint and exact source/transcript hashes are frozen before screening. This extends surface isolation without changing historical guards or evaluation bytes. It does not detect arbitrary paraphrases or unseen variants of a task family, and the actual source sample having no matches does not prove universal decontamination.

## Existing duplicate staging and exact lineage audit

`scripts/stage-prose-candidates.py` reuses the existing SQLite staging implementation. It imports every ancestral validation/test record, copies exactly matching source evidence, and adds only the 865 selected canonical prose candidates. Original acquired rows remain separately available by hash. No source review status or training-reader rule changes.

Existing exact identities and 5-token hash-shingle Jaccard grouping at 0.85 operate before split assignment. This checks incoming candidates against each other and imported heldout records; it is not an audit against every historical training row or a semantic duplicate guarantee. Full staging reports 6,876 candidate comparisons and 6,418 near pairs across the entire combined population, much of which is inherited dialogue material. Those counts are not new prose-duplicate counts. No exact duplicate is removed in this execution.

The staged artifact contains **6,593 records: 5,728 ancestral heldouts plus 865 new candidates**. It remains `sample_only`, `training_eligible:false`, `source_rights_approved:false`. Existing cleaners can normalize/redact text generally, so the actual checker compares text rather than assuming it stayed unchanged: all 865 current candidate texts remain exact. No candidate ID disappears and no ancestral heldout partition changes.

| New candidate partition | Documents | Student-BPE content tokens |
| --- | ---: | ---: |
| Train | 796 | 814,048 |
| Validation | 34 | 37,084 |
| Test | 35 | 31,478 |

These are content-token counts, not a prepared batch stream or gradient-position exposure. This corpus is also far smaller than the proposed 50M/100M learning envelopes; repeatedly replaying it is not a substitute for sufficient diverse data.

Actual staging stays inside explicit 12,000-record, 500,000-comparison and 768 MiB database ceilings; peak allocated database bytes are 289,865,728. This is a bounded local execution, not a throughput or memory forecast for a larger corpus.

## Verification and next action

**23 focused checks pass**, including the 13 range-reader checks and ten new screening checks. New cases exercise embedded punctuation/case variants, word boundaries and acknowledged paraphrase misses, foreign-language tails, missing predictions, heldout protection, preserved prior nonapprovals, non-mutating output, privacy candidates and repetition/source signals.

`scripts/check-prose-intake.py` reconstructs every actual screen decision from retained predictions and pinned inputs, recomputes BPE counts, checks selected raw-to-canonical lineage, verifies the staged manifest, and compares every ancestral heldout's text/partition. The actual check passes. It does not independently rerun the detector or approve subjective content. Frozen acquisition/screen/stage code and plans retain their original hashes; historical numerical/training implementations remain unchanged.

Evidence: `reports/milestone-sixty-nine-{prose-screen,prose-staging,intake-check}.json` and tests XML. Private raw/prediction/staged artifacts are under `data/fineweb-prose-screen-v1` and `data/fineweb-prose-candidate-staging-v1`; raw source content is not committed.

Next: directly inspect a deterministic crawl-balanced train-candidate packet, record remaining defects/content boundaries and formulate a finite source/research admission without inventing individual clearance for unread rows. Then scale bounded diverse acquisition and durable overall accounting, preserve these heldouts/nonapprovals, prepare an admitted token stream and freeze learning/retention/portability/conversation contracts. No new training starts merely because this technical staging passes. Actual terminal conversation and direct scoring remain mandatory before advancing after any completed training iteration.
