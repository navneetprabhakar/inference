# G0 training candidate, version 1 — not admitted

6,400 conversations /17,600 reference turns. No model inference, training, teacher CLI, final-custody read, or claim of independent semantic acceptance occurred during authoring. The author read the forty source-frame rules and function/structure expansion rules while composing them. That is author inspection, not full nonauthor semantic review.

## Provenance and diversity limits

-4,800 natural candidates:40 authored source frames ×6 functions ×4 dialogue structures ×5 assignments. Eight frames per domain: household chores/storage, neighborhood retail errands, school clubs, community sports, craft workshops.
-The forty frames cover storage/location, ordering, rejected alternatives, role allocation, material condition, availability, quantity uncertainty and stated reasons. These are not4,800 independent stories. There are240 function/frame semantic templates and960 function/frame/structure combinations; each gets five name/count/time substitutions. Most name substitutions do not affect an answer. Slot replication, uniform short missing-information replies, repeated exact-value instructions, and generic label interruptions materially limit linguistic richness. Reviewers may reject this as insufficiently rich; counts do not override that judgment.
-Each natural family has200 candidates in each structure. Direct follow-up and multi-constraint have2 turns, correction/repair3, interruption/return4. The clarification correction structure supplies previously missing information; it repairs incompleteness rather than contradicting a supplied fact. Most comprehension questions are negation/contrast checks. No external knowledge is intended.
-Name copying uses a40×20 component product:800 distinct names;760 outside a defined40-pair diagonal anchor inventory;476 have a long first/last component. Time copying has800 distinct strings,400 numeric and400 marked12-hour strings, with780 outside a20-pair hour/minute anchor inventory. Anchor novelty means recombination within the training pool, not unseen test values or chronological introduction. Both copy tasks vary actual native segmentation. Four instruction wrappers are reused per copy task. There is no claim of800 distinct semantic copying contexts.
-References are examples of valid answers unless an exact string is explicitly requested. Short noun phrases are valid in these questions. All supplied changes carry the updated factual answer; correction-family records also recover the explicitly requested original state.

## Files and review

`private/candidates.json` contains actual messages, per-turn references/constraints, native ids and target masks, provenance, and candidate status. `private/review-all-00.json` through `15.json` are compact400-row review shards. Each `pairs` entry is `[user_prompt, assistant_reference, exact_match_required]`; all turns must be read, including duplicates and substitutions. Shared contract: intelligible English, requested act and constraints, grounded facts, correct original/latest state, no unsupported material claim. No automated check establishes semantics.

`review-index.json` navigates960 natural representatives plus8 copy representatives. It is not sufficient admission review. `private/review-second-00.json` through `03.json` contain1,280 stratified second-review records (20% of each family/structure). Every candidate needs a nonauthor first review; the second review must use another reviewer. Collect all issues before the campaign's single permitted prelaunch revision batch. Do not patch after individual comments.

`build.py` uses the exact native serialization copied from phase-a build.py; it never loads model weights. `validation.json` gives native counts. Worst generated-history context including32 reserved response positions per turn is254/256; maximum reference reply13/32 includingEOS. No truncation or history repair occurs.

Each frozen seed schedule (291102,291103) has1,000 updates with one record per task: all800 once, then the same200-record subset in different shuffled order. Repeat selection is50 per structure/task. The two screen arms share seed291102; confirmation uses291103. No replay corpus/schedule is authored here.

`review-budget.json` reserves approximately1.71M input/output tokens and20 review requests for this training packet only, using bytes/3 estimates plus20% prompt reserve and48 output tokens/record. This is not actual API accounting, and full-context agent turns may cost more. Parent accounting must include all author/reviewer requests, failed calls, repeated history and other G0 artifacts under6M/80.

Rebuild only before review freeze, or as the single collected revision batch under parent control. Candidate manifest hashes identify the reviewed version; no admission file is created by this builder.
