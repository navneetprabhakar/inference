# Next step: test a small conversation curriculum against matched grounding practice

Date: 2026-10-24. Status: **planning complete; execution not authorized**.

The user requested a deep dive and next-step plan. Work in this directory is CPU-only inspection and planning: no student forward/backward passes, optimizer updates, teacher requests, downloads or data admission. This proposal replaces the recommended next experiment in the earlier [proposed study](../deep-training-audit-v1/PROPOSED_STUDY.md), but does not alter historical approvals, checkpoints, scores or terminal stops. Approval must explicitly cover this revised experiment and its guard/budget changes.

## Decision

Keep the current 15.19M model as the diagnostic architecture. First establish complete name/time fitting under narrative preservation. Then run one matched comparison: **does allocating part of supervised training to reviewed teacher conversations improve fresh conversation performance more than spending the same model-input budget on additional grounded practice?**

This directly tests the missing teacher curriculum. Both arms use separate loss normalization; there is no simultaneous ramp or normalization ablation. The comparison measures a curriculum-allocation policy, not the isolated superiority of teacher authorship. Broad-English data admission remains a separate prerequisite for an accepted BASE release. A successful diagnostic does not complete BASE, CHAT or TOOL.

## 1. Findings that determine the plan

| Finding | Evidence and qualification | Consequence |
| --- | --- | --- |
| Learning is measurable, transfer is weak | Matched exact answers increased 25→56/152. Complete names/times stayed 0/16 each; novel-wording recall stayed 1/8. [Matched review](../matched-improvement-reassessment-v1/README.md) | Preserve B and measure gains/regressions separately. Do not infer general conversation readiness. |
| Multi-token tasks were not fitted | Seen training names 1/16; times 0/16. Only 538/2,592 new records visited. [Audit](../deep-training-audit-v1/README.md) | A small fit gate comes before the comparison. Failure does not establish a capacity limit. |
| Teacher data is absent from A/B | Their lineage contains factual drills; the earlier 62-conversation SFT branch is separate and failed behavior despite lower loss. [Earlier SFT](../sol-conversation-sft-diagnostic-v1/README.md) | Include an actual teacher-vs-grounding contrast and behavior evaluation, rather than comparing two teacher-fed recipes. |
| Gradient evidence depends on checkpoint | At A, equal old/new normalization left conflicting old-loss directions in 3/4 samples; at B, all four directions were preservation-compatible. [Raw summary](../deep-training-audit-v1/summary.json) | Do not treat the parent's 264–441× ratios as B's current condition. No ramp or gradient surgery in this study. Four sampled SGD directions do not predict the actual Adam trajectory. |
| Optimizer state is usable but the helper destroys it | CPU inspection found 56 finite, nonzero moment pairs in B, all at step 100, plus RNG state. The SFT `load()` explicitly resets steps/moments. | Add explicit fresh/resume paths and test continuation equivalence. Saved optimizer step 100 differs from B's cumulative 500 SFT updates. |
| Saved LR metadata is stale | B stores 5e-5; its runner explicitly passed 2e-5 after warmup. The checkpoint helper calls an injected constant 5e-5 schedule when writing metadata. | Persist the actual applied LR and schedule position. This is a reproducibility defect, not evidence that historical updates used the wrong LR. |
| Decoder length matters | Of 757 train records fitting serialization, 248 contain an answer requiring more than 32 decode steps including EOS; 37 exceed 48. At cap 80, 15 fail gold-history headroom and 317 fail conservative generated-history headroom. [New evidence](evidence.json) | Use a reviewed two-turn subset compatible with cap 48. Do not silently shorten references or increase context. These are structural limits, not observed model failures. |
| “Exact” scoring is too permissive for syntax | The existing word-token normalizer equates `09:10` and `09 10`. It does not accept arbitrary wrong digits. | Use literal clock syntax plus value correctness in fresh tests. Preserve historical scores under their original rubric. |
| Broad data remains blocked | D0 failed composition and semantic admission; R1/R2 did not start. [Report](../foundation-recovery-v2-corrected/REPORT.md) | Keep a separate broad-data readiness deliverable; do not use this study to waive foundation gates. |

All three source checkpoint hashes were reverified. New evidence is reproducible with `restart/mac-native-benchmark-v1/venv/bin/python restart/next-step-plan-v1/inspect_evidence.py`. That script reads only teacher training payloads and hash-verified local checkpoints; it does not initialize or execute a model.

## 2. Preparation and engineering prerequisites

Implement in a new run directory after execution approval, using versioned support code rather than modifying historical experiment sources. Preserve raw payloads, generated holdouts and weights outside Git. The plan itself does not start an execution clock.

1. **Explicit state handling.** `fresh` resets moments, RNG according to a frozen seed, and optimizer counters; `resume` restores parameters, both optimizer groups, steps, moments and RNG. Store parent hash, cumulative lineage counters, local update count, effective LR, schedule position, data cursors and ledger cursor independently. Do not temporarily zero the base step when saving a resumed run. Validate tensor-name mapping and tied embeddings.
2. **Resume preflight, charged to this study.** Compare two uninterrupted updates against one update + save/load + one update on identical inputs (four optimizer invocations). Require exact saved/reloaded tensors, steps, moments, RNG and cursors; require exact same-backend continuation results. Two additional disposable fresh-mode updates verify reset and step bookkeeping. If equality fails, stop and diagnose; do not relax tolerances after seeing outputs. Disposable children never seed the fit gate or main arms.
3. **Loss and masking checks.** Freeze the existing independent FP32 tolerances: NLL difference ≤0.02, gradient relative L2 ≤0.08, cosine ≥0.995; masked-label and padding perturbation difference ≤1e-6. Check each new group loss and the weighted combined loss. Empty groups and zero target denominators are errors. Log per-group targets, mean loss, coefficient and gradient norm; compute logged norms from gradients already required by the update.
4. **Scorer fixtures.** Include correct full values, omitted name components, wrong digits, missing colon, stale facts, negated answers, unsupported additions, valid short/full-sentence formats, premature EOS, BOS and length/context overflow. Freeze content and instruction scores independently. A keyword match cannot certify clarification or factual truth.
5. **Schedule and context checks.** Materialize every batch before training; count all examples, target tokens, input positions and coverage. Check training-prefix equality and generated-history worst-case bounds. No truncation, post-output cap extension, best-of decoding or silent format repair.
6. **Approval/run receipts.** Record the exact approved plan hash, source hashes, input manifests, rubric version, selection rule, fresh tests and aggregate budget. Fail closed on changed artifacts. No runtime invocation until all preparation artifacts pass.

The six preflight updates are proposed future work, not tests already executed. Preparation produces a ready/not-ready receipt; uncertainty about admission or budget feasibility stops launch rather than expanding the run.

## 3. Data design

### Grounding and preservation

- **800 corrected grounding records:** 100 each for names, times, locations, distractor selection, state updates, answerability, clarification and requested sentence format. Each full serialized record has at most 24 assistant/EOS targets. Use deterministic fact oracles; reject an impossible oracle/format combination before training.
- **400 rehearsal records:** fresh training paraphrases of established skills, paired short/full-sentence requests and corrections; at most 12 assistant/EOS targets per record. Do not copy exposed evaluation prompts into rehearsal.
- Independently balance values, entity identities, order, missingness, transitions and answer format. Within each relevant training stratum, present and absent variants must share attribute values, each initial location must have multiple successors, and target position must vary independently of target value. Assert these properties in the generated bank.
- Use at least 100 complete name strings and 100 clock strings across the corresponding 100-record families; preserve exact component/combination exposure inventories. Fresh tests separate new combinations of familiar components from entirely new strings. Do not attribute length effects to tokenization without a separate intervention.
- Group related scenarios and paraphrases before splitting. Training, development and final tests have disjoint scenario groups and templates. Run exact, near-text and generator-family overlap checks against known exposed banks; report their limits. No claim of independent sealed custody.

### Small teacher bridge

Restrict the first bridge to six already represented training families: grounded extraction, reading comprehension, clarification, correction, instructions and simple explanation. Use two-turn conversations only, each answer plus EOS ≤48 tokens, total assistant/EOS targets ≤96, and enough context for worst-case capped generated history.

CPU inspection found **254 structurally eligible records** across those families: 48, 50, 27, 34, 46 and 49 respectively. They are still unadmitted candidates. Review all 254 against supplied facts, completeness, coherence, ambiguity, unsupported claims, constraints and overlap. Prior same-teacher screening is supporting evidence, not an admission verdict.

After review, select a balanced **6 × k** bank, where `k = min(24, the smallest admitted family count)`. Require `k ≥16`; otherwise stop preparation. Thus the study uses **96–144 reviewed conversations**, not an assumed 757-record release. Selection uses frozen seeded order among passing records, never student outputs. Preserve exclusions and source IDs; no rewriting to fill quotas. Report actual targets and token-length distributions. No new teacher calls are proposed.

Keep original teacher dev/test splits untouched. They reserve whole skill families and cannot supply a clean same-skill transfer comparison for these six families. Fresh evaluation scenarios are authored separately, grounded in explicit facts/reference material, and kept out of training. Existing held-out-task transfer is a later evaluation question, not pooled into this study's score.

## 4. Stage I — bounded fit gate

- Start an isolated child from B's weights with explicitly fresh Adam state. Use the existing 16-name/16-time seen-training fit set, verified ≤16 targets per record. This is deliberately a training-fit diagnostic, not fresh evaluation.
- Batch eight fit records with deterministic equal coverage; narrative batch eight ×256 targets. Objective: `0.5 narrative CE + 0.5 fit CE`. Maximum 200 updates, LR `2e-5 × min(1, local_update/5)`, clip norm 1.
- Evaluate fit and original narrative validation at updates 50, 100, 150 and 200. Greedy cap 16, including room for EOS. Pass only with ≥15/16 complete names and ≥15/16 exact clock strings, each ending in EOS, within hard numerical/narrative/resource limits. Stop at first passing scheduled checkpoint.
- The child is discarded as a training source. Legacy retention is not an advancement criterion for this sacrificial child; its purpose is fitting under narrative preservation, not proving whole-model preservation. Main-arm retention remains mandatory.
- If the fit gate fails, end the study. Report per-position fit losses/accuracy from budgeted evaluation and distinguish failure to fit from a preservation/resource stop. No automatic LR search, teacher generation, larger architecture or extended memorization run.

## 5. Stage II — paired curriculum comparison

Both arms start from identical copies of **B's original weights and saved step-100 optimizer/RNG state**, not the fit child. Use a fixed 2e-5 learning rate, existing AdamW betas/epsilon/decay, clip norm 1, FP32 parameters/moments and BF16 compute. No new warmup or ramp. One frozen seed pair, no hidden reruns.

Each arm has at most **400 updates**. Every update contains two rehearsal records, four shared grounding records, two comparison records and eight narrative sequences. All model inputs are padded to 256 positions. Shared examples and narrative sequence order are identical between arms.

| Independently normalized loss | Control | Teacher arm |
| --- | ---: | ---: |
| Narrative | 0.50 | 0.50 |
| Rehearsal: two records | 0.25 | 0.25 |
| Shared grounding: four records | 0.10 | 0.10 |
| Comparison: two additional grounding records / two teacher conversations | 0.15 | 0.15 |

The comparison changes only the records in the final group. Different assistant-token counts and response lengths are intrinsic to this allocation policy and must be reported; equal padded input work is not equal target exposure or semantic difficulty. This study does not isolate normalization, teacher authorship or longer-answer exposure.

Complete coverage of the 800 shared grounding and 400 rehearsal records is guaranteed by update 200. Cover the entire teacher subset at least once before then, cycling deterministically and balancing families. The control's extra grounding slots cycle through the same 800-record bank. Log distinct coverage and repeated exposures separately.

Run alternating 50-update blocks, checking hard guards after each arm's block. Full development/eligibility checks occur at updates 200 and 400 only. Checkpoints before complete coverage cannot be selected. If either arm hits a hard guard, stop new updates in both arms; compare the last common completed update descriptively and mark the study stopped. This prevents spending the remaining budget as an unplanned single-arm rescue.

## 6. Evaluation and selection

**Decoding:** full-vocabulary greedy; no EOS suppression. Fit/legacy use caps 16; new grounding/conversation tests use cap 48. Generated previous replies remain in conversation history. BOS, missing EOS, unsupported additions or context overflow fail the relevant turn; an overflow also fails the whole conversation. Do not replace generated replies with gold history. Teacher-forced NLL is secondary evidence.

**Fresh scoring:** strip outer whitespace only for clock strings, require `HH:MM` syntax and equality to the supplied value; names must contain every component in order, with only case and whitespace normalization. Report factual content separately when requested answer format fails. Conversation-correct means factual/task correctness, all explicit instructions satisfied, EOS and no unsupported additions. Clarifications must ask for the required missing field without assuming its value. Freeze allowed variants and examples before any model output; ambiguous judgments remain failures/holds under the fixed rubric. Historical retention/secondary scores keep their historical normalization and separate EOS checks.

**Fresh development:** 16 names +16 times +8 three-turn state conversations =56 replies; six families ×4 two-turn conversations =48 replies. Total **104 replies** per checkpoint. Freeze separate fresh final banks before any training.

**Fresh final:** 32 names +32 times +32 three-turn state conversations =160 replies; six families ×8 two-turn conversations =96 replies. Total **256 replies** per model. Evaluate B and at most one development-selected checkpoint per arm once, after selection. Final outcomes cannot select a different checkpoint. Report all cells, full-conversation success, EOS, unsupported claims and paired gains/losses.

**Eligibility at development checkpoints:**

- Original narrative NLL ≤`1.3430354408919811 ×1.05`.
- Legacy strict ≥73/80 and content ≥72/80; preserve exposed exact location/sentence/missing-fact counts ≥9/16, ≥8/16, ≥8/8 under their historical scorer.
- Full training-bank coverage as specified above; no hard-stop violation.

Select each arm's eligible checkpoint by highest development conversation-correct turns, then most fully correct state conversations, then total exact names/times, then earliest update. If no checkpoint qualifies, that arm has no selected model; do not substitute a failing checkpoint for an advancement claim.

**Proposed final progression thresholds:** names and times ≥16/32 each; state conversations ≥16/32 wholly correct. Teacher-arm conversation performance must reach ≥48/96 correct turns, ≥6/16 in each family, and improve by ≥12/96 turns over B. To favor teacher allocation over extra grounding, additionally require ≥8 net correct turns over the selected control without failing preservation or grounding thresholds. If control has no eligible selection, a clean eligible-arm superiority claim is unavailable; report that qualification explicitly.

These are chosen pilot decision margins, not statistical confidence guarantees or release gates. Blind checkpoint labels during manual scoring and review all fresh final answers against frozen rubrics. The same agent can perform that review, but it is not independent human evaluation. Publish paired counts by scenario; turns in a conversation are correlated. If the contrast is small, mixed, or one arm is ineligible, return an inconclusive recipe comparison rather than a ranking.

## 7. Guard policy and aggregate budget

The original broad run stays closed. For this new recovery study only:

- **Strict 69/80 becomes eligibility rather than a hard stop**; final development eligibility is the stronger 73/80. B itself starts at 64/80 strict, so recovery must be allowed to run below eligibility.
- **Main-arm content hard floor is 72/80**, B's recorded baseline. This explicitly rejects the earlier proposed 64/80 content floor. Calibrate a general scorer against historical reviewed responses before launch; do not hardcode accepted IDs. If it cannot reproduce 72/80 correctly, stop preparation and resolve the rubric before seeking execution approval. A strict no-content-regression rule may stop a potentially recoverable trajectory; that conservative tradeoff is deliberate.
- Hard stops: nonfinite model/loss/gradient/moments; pre-clipping combined gradient norm >100; original narrative NLL above +5%; main-arm content below 72/80 at scheduled checks; any approved work/resource cap. Numerical/resource checks occur per operation/update; retention/narrative checks occur at the stated cadence, so transient regressions between checks are not observed.
- Global cap stops forbid further model work. Reserve evaluation capacity before updates. Scientific stops can use only a previously reserved read-only report allocation; no extra updates, fallback branches or budget resets.

| Aggregate cap | Proposed maximum |
| --- | ---: |
| Optimizer invocations, including disposable preflight | **1,006**: 6 +200 +400 +400 |
| Model-input positions | **40,000,000** including preflight, fitting, training, validation and all decoding |
| Assistant/EOS training-target exposures | **250,000** |
| Narrative training-target exposures | **3,000,000** |
| Model-work wall time | **45 minutes**, includes model loading/compilation/preflight/training/evaluation; paused only during documented CPU preparation/manual review with model process idle |
| Added study artifacts | **5 GiB** |
| Process RSS / MLX active-or-driver peak | **12 GiB each**, recorded separately |
| Free disk floor | **60 GiB** |
| New teacher requests / downloads | **0 / 0** |

**Budget changes are explicit:** fewer updates than the older 1,400 proposal, but a larger position cap than its 12M. The latter funds pessimistic full-length decoding for a real paired conversation evaluation; it is not inherited unused allowance. Count each submitted padded forward or value-and-gradient input position once; backward work is not multiplied into this unit. Extra diagnostic forwards are additional positions. Historical audits sometimes used gradient multipliers, so do not compare totals without their accounting conventions.

The nominal training upper bounds are 4,120,576 input positions (`1,006 ×4,096`) and 2,060,288 narrative targets. The per-record bounds above give ≤219,472 SFT targets even allowing six preflight updates at the larger arm's maximum. A conservative planned envelope for specified guards/dev/final generation is below 40M, but the executable schedule must compute and reserve its exact worst case before launch. There is no promise that all caps can be consumed simultaneously or that the model will pass within 45 minutes. If preflight/final reservations do not fit, stop preparation; do not silently remove evaluation coverage.

| Position reservation, assuming all checkpoints and maximum reply lengths | Positions |
| --- | ---: |
| All 1,006 update invocations | 4,120,576 |
| Four fit checks: 32 replies at cap 16 plus narrative validation | 1,048,576 |
| Sixteen main guard checks: 80 replies at cap 16 plus narrative validation | 7,340,032 |
| Baseline plus four development checks: 104 replies at cap 48 | 6,389,760 |
| Baseline plus four exposed secondary checks: 40 replies at cap 48 | 2,457,600 |
| Initial main-arm narrative/80-turn guard baseline | 458,752 |
| Final tests: B plus two selected children, 256 replies each at cap 48 | 9,437,184 |
| **Subtotal** | **31,252,480** |
| Remaining allowance for numerical preflight, fit failure analysis and explicitly reserved extra forwards | **8,747,520** |

Each generated token pessimistically charges 256 input positions here; actual prompt lengths may be shorter. The narrative validation set is 512×256 positions. CPU grading charges wall/review time but no model positions. Additional student loss diagnostics consume the remaining allowance, not a separate budget. At least the full final-test allocation remains reserved until selection or explicit terminal cancellation.

Preparation/manual review is separately limited to **six active hours after execution approval**. Record elapsed work and unfinished items; no model run if the freeze cannot be completed within that budget. This is a proposed stopping allowance, not a forecast of completion. All model work, including failed preflight, remains charged.

## 8. Outcome and route beyond this diagnostic

| Outcome | Next decision |
| --- | --- |
| State/scorer/data/schedule preflight fails | Repair the identified implementation or admission problem; no student launch. |
| Fit gate fails without numerical/preservation stop | Multi-token learning under this recipe remains unresolved. Review consumed fit data and position errors before proposing any new experiment. |
| Fit passes; both main arms fail preservation | Report interference under this data/objective. Do not interpret fit as conversational progress or add more teacher volume. |
| Grounding improves; conversation does not | Keep measured gains as research evidence; investigate foundation/curriculum suitability. No automatic follow-on drill cycle. |
| Both arms improve similarly | Additional diverse practice may explain gains; teacher-specific benefit remains unestablished. |
| Teacher arm clears all gates and the comparison margin | Recommend a separately scoped expanded conversation study; preserve full lineage and exact admitted data. No automatic promotion. |

Produce `approval.json`, `data-admission.json`, `freeze.json`, `schedule.json`, `preflight.json`, a durable aggregate ledger, per-checkpoint histories, private raw responses, final paired report and terminal decision. Record actual rather than planned coverage and target counts. A final report must include failed gates and unsupported claims, not only loss curves.

**Broad-data work is the next project dependency regardless of the diagnostic's outcome.** Prepare a separate readiness packet from existing local supply: source/version and rights evidence, extraction boundaries, native-token counts, semantic quality failures, genre/family diversity, source caps and feasible train/dev/test allocation. The prior 13.66M candidate frame is quarantined. Repairing it requires a new version and fresh admission; do not reuse the failed sample as fresh or assume the 39,796-token arithmetic shortfall is the acquisition requirement. Stop before downloads or broad training. Final architecture/context/throughput selection follows admitted supply, not this conversation pilot.

Tool integration remains later: the old BPE tool serializer is incompatible with the active SentencePiece path, and learned tool choice/arguments are unproven. Address that contract after grounded conversation is demonstrated. No tool/MCP implementation work is included in this next experiment.

## 9. What is ready now

The diagnosis, proposed comparison, acceptance rules and aggregate limits are documented. CPU evidence and checkpoint hashes are verified. The new runner, admission reviews, frozen data/schedules, scorer and resume tests are **specified but not implemented/executed**. The next authorization can cover preparation and the gated experiment above; it must include the changed strict guard, 72/80 content floor and 40M position allowance. There is no authorization to execute merely because this plan exists.
