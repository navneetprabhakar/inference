# Paired supervised curriculum candidate — 29 October 2026

**Prepared and CPU-validated; never trained.** This is paired supervised fine-tuning data under the existing cross-entropy objective, not a new contrastive loss.

## Inventory and intended use

- 4,096 semantic training conversations: 512 each for name, time, location, distractor/color, state, missing information, clarification and output format.
- 2,048 before/after pairs. The pair changes only the requested fact; state reverses initial/corrected colors, missingness toggles availability, and clarification changes the supplied answer on its second turn. Clarification's first answer deliberately stays unchanged.
- Two presentation views of the same records: 8,192 exposures, not independent conversations. The proposed schedule has 1,024 batches of eight, one case per family. Paired members occur on consecutive batches; each record occurs once per view. This replaces the old schedule and is not plugged into an authorized runner.
- Views vary query, sentence/KV facts, single/full context and order. Clarification facts and follow-up templates remain fixed even when presentation metadata changes; its views are not a full factual-format intervention.
- 512 unscored development candidates, 64 per family, use separate object entities and one new query template per family. They are prospective synthetic development examples, not a sealed final test or conversation acceptance benchmark.

## Coverage and caveats

Eight training entities each receive all eight colors and all eight object locations with exactly eight occurrences per value in each relevant 512-record task family. Changed color/location pairs and reversed state pairs prevent a fixed entity→value answer from satisfying both sides. Both missingness states occur for each paired world. Sixteen first names × sixteen surnames yield all 256 full-name combinations in the name task; component assignment rotates across entities. This is not exhaustive entity×full-name coverage.

Development names split into 32 familiar full names on new entities and 32 names with new components. The first group is **not** unseen combinations of familiar components. Development meeting times are 18:00–19:03; clarification venues are separate from training venues. Colors/object locations are familiar values attached to new entities. Randomized distractors can occasionally share the correct value; not every example is an adversarial distractor. Presentation frequencies and new-name/color strata are not perfectly orthogonal. No broad distributional-independence claim is made.

Clarification uses plausible separate meeting venues, not object surfaces. Pre-freeze checking caught old prompt overlap and nonsensical venue reuse; see [revision-notes.json](revision-notes.json). Final exact user-sequence overlap is zero with old matrix/counterfactual packets and old canonical training; two sequences overlap old diverse **training** data. Old evaluation sets remain development/regression evidence because they already informed this revision.

## Validation

[checks.json](checks.json): 70,162 assertions passed. Recomputed IDs/masks and assistant/EOS targets, checked an independently expressed structured oracle, exact pair changes, family counts, per-entity color/location balance, schedule multiplicity, and train/development user-sequence separation. Maximum conservative generated-history context is 228 tokens for either training view and 224 for development, including 32-token allowance per generated response within the 256-token context. References fit the 32-token EOS-inclusive response cap.

Each view has 24,752 assistant/EOS targets; the proposed schedule exposes 49,504. Padded assistant input positions total 864,368 under batch-max padding with shifted input length. This excludes replay, evaluation and startup; it is **not** a full budget or elapsed-time estimate. Equal conversations per family do not mean equal target tokens; preserve explicit per-family loss aggregation and replay weighting in any future adapter.

Primary author inspected rendered training/development cases across all eight families. These checks are not independent semantic review. [REVIEW_PACKET.md](REVIEW_PACKET.md) contains 32 selected rendered conversations for review; no review completion is claimed.

## Evaluation contract for the next proposal

Report per-family and per-stratum results, never just a pooled total. On paired training fit examples report both-members-correct and unchanged-answer errors; score state initial/correction/distractor turns separately and as whole trajectories. On development separate familiar names/new components, single/full facts and sentence/KV format. Use generated history and normal EOS, not teacher-forced history or reference-length truncation. New development is single-record coverage; a separate prospective paired generalization set is still needed before claiming counterfactual transfer.

The [diagnosis reassessment](../binding-diagnosis-2026-10-29/REPORT.md) specifies the next gate: semantic review, matched pairing-order control, small predeclared fit experiment and fresh budget approval. No optimizer work, promotion, or final acceptance is authorized by this candidate.
