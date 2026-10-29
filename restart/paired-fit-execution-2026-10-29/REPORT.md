# Paired versus shuffled fit — completed, no qualifying candidate

**Neither arm passed the predeclared fit gate. Pair adjacency is not supported as the fix.** Both arms completed256 updates from identical fresh foundation parameters, optimizer and RNG; no promotion or final-test use.

| Measure | Paired | Shuffled |
|---|---:|---:|
| Complete pair presentations |191/512 (37.3%)|208/512 (40.6%)|
| Fit turns correct |880/1,408 (62.5%)|931/1,408 (66.1%)|
| Development turns correct |89/176 (50.6%)|85/176 (48.3%)|
| Task/view cells meeting29/32-pair gate |0/16|0/16|
| Native narrative NLL |1.9625|1.9648|
| NLL relative to source |1.4613×|1.4629×|

Source scored0 on both structured packets, with narrative NLL1.3430354334. This floor remains unsuitable for certifying behavioral preservation. Both endpoints satisfy the permissive1.65× research NLL guard, but approximately46% NLL degradation is not a preservation pass.

Across512 pair presentations, paired wins48 and loses65 against shuffled: net−17, or−3.3 percentage points. These are256 underlying semantic pairs shown twice, not512 independent observations. Paired has4 more correct development turns. One seed and small development strata do not establish a reliable ordering advantage. The intervention combines adjacency and before→after orientation; replay remains fixed by update, while assistant-batch order changes.

## Where fitting failed

Training-turn correctness across both presentation views:

| Task | Paired | Shuffled |
|---|---:|---:|
| Full name |15/128|30/128|
| Exact meeting time |0/128|1/128|
| Location |73/128|63/128|
| Color with distractor |106/128|114/128|
| Missing information |73/128|76/128|
| Clarification |192/256|192/256|
| State tracking |336/384|347/384|
| Requested output format |85/128|108/128|

Names and arbitrary exact times are the clearest remaining acquisition failures **on the fit data itself**, not merely unseen transfer. Examples include Damon Adler→Mabel Orton (paired), Damon Adler→cabinet (shuffled), and00:03→07:37/08:55. Both arms score0/16 on development names and0/16 on development times, including0/8 familiar full names and0/8 new-component names.

Teacher-forced loss improves substantially while complete copying remains poor: name loss11.290→1.609/1.205; time7.028→0.945/1.029. State loss falls11.123→0.205/0.183, but complete paired trajectories remain36/64 and41/64. Initial-state fit turns reach105/128 and111/128; this is meaningful within-run acquisition, not a comparable improvement over the different earlier screen.

Paired has no termination failures across fit/development. Shuffled has39, including36 fit-location turns and3 development turns. Thus termination contributes to shuffled location weakness, but does not explain either arm's name/time failures. See [failure-audit.json](failure-audit.json) for output examples and [assessment.json](assessment.json) for task/view pair counts, changed-answer errors, state turns and development strata.

## Accounting and integrity

- Exactly512 new optimizer updates,24,808 assistant/EOS targets,1,048,576 narrative targets.
- 7,557,173 new input positions;408.9503 active seconds (**6.82 new active minutes**) against20M positions/60 minutes. Early EOS made evaluation much cheaper than the conservative32-token projection. Active time excludes orchestration overhead and is not elapsed wall time.
- Carry-forward imported once: prior4,612 updates included all612 calibration updates, plus the separate inference-diagnosis usage. Final successor totals:5,124 updates,22,593,515 positions and1,592.3618 seconds (**26.54 active minutes**). Earlier campaigns/engineering remain separately recorded, not erased.
- Source plus two endpoints each received1,408 fit turns,176 development turns, all1,024 teacher-forced fit presentations, and512 native validation blocks. Checkpoints saved only at endpoints.
- [Audit](audit.json) verifies identical initialization including optimizer/RNG, frozen inputs, complete step sequences, checkpoint hashes, unchanged historical ledgers, one carry-forward import, and all caps. Artifacts approximately368MB, below2GiB.
- The512-update allowance is exhausted. Unused time/positions do not authorize more updates. No retries, LR search, extra seeds or final tests occurred.

## Reassessment and next decision

**Do not expand this into another full curriculum run or prefer paired ordering on this evidence.** Equal exposure controlled the schedule comparison; the results do not support adjacency as sufficient. They also do not prove a capacity limit or that the broader curriculum is ineffective: this used only a subset,256 updates/arm, a fixed LR and replay0.5, with all eight tasks trained together.

The next useful experiment would isolate exact copying from multi-task competition. Before requesting more compute, prepare a tiny balanced name/time fit packet with verified arbitrary values, counterfactual pairs and simple versus distractor contexts. Define training-fit and unseen-value measurements separately. Use a small predeclared training-only LR/exposure check, with explicit replay/retention tradeoff, rather than changing data, schedule, replay and optimizer together. Compare against these saved failures, but do not reuse exposed development cases as final evidence.

A diagnostic should establish whether a tiny copying subset can be fitted at all. If it cannot, inspect token-level teacher-forced errors and gradients before increasing data or model size. If it fits but unseen values fail, the next target is copying generalization. If it fits alone but fails when tasks are combined, investigate task interference/loss allocation. This is a proposed branch of investigation, not authorization to execute it.

Current status: completed bounded experiment; no acceptable conversational model; no further training launched.
