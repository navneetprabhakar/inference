# English training result — failed acceptance, real fit learning

Ganesh-base by Navneet Prabhakar is not yet a usable English conversation model.
The approved A100 run trained actual weights; qualification alone was not its goal.
The fit stopped at update 30 because seven development regression guards fired.
No automatic continuation or curriculum run is authorized by this result.

## Execution efficiency and accountability

The30logged training-update intervals sum to23.899seconds. That excludes data
collection, development evaluation, checkpointing, uploads, setup, qualification
and assessment. The fit job occupied roughly18minutes, and the VM was allocated
much longer. This was a diagnostic/qualification campaign with very little learning
compute, not a substantial English training campaign. Infrastructure work dominated
the run. Repeating it unchanged would be a poor use of the approved budget. Reuse
valid evidence bound to the unchanged runtime, and spend future GPU time on a
predeclared learning treatment plus behavioral checks; requalify only affected
boundaries when code or numerical behavior changes.

## Complete raw conversation assessment

All 396 English turn records were read, including malformed outputs and blocked
follow-ups. This is a same-agent diagnostic review, not an independent release.
Greedy decoding, original prompt policies and reply budgets were unchanged.

| Checkpoint | Exposed fit turns | Fully passing fit sessions | Unseen development turns | Fully passing development sessions |
|---|---:|---:|---:|---:|
| 0 | 0/72 | 0/24 | 0/36 | 0/12 |
| 16 | 0/72 | 0/24 | Not scheduled | Not scheduled |
| 20, minimum development loss | 0/72 | 0/24 | 0/36 | 0/12 |
| 30, stopped last | 64/72 | 21/24 | 2/36 | 0/12 |

The frozen fit gate requires at least 23/24 semantically passing sessions, complete
valid actions across all turns, full review, and no forbidden tool actions. It fails.
The two passing development turns do not imply any passing conversation. Minor
wording judgments cannot change the decision: most development failures are missing
termination, irrelevant answers, invented facts, or blocked follow-ups.

Evidence: `assessment/scores.json`, exact raw files and hash-bound per-turn reviews
under `assessment/raw/` and `assessment/reviews/`. Checkpoint 30 is diagnostic only.
No serving default changed, and no HTTP endpoint was enabled.

## What this establishes

- Learning is occurring. At update 30 many exact training conversations produce
  correct natural answers, corrections, state changes and clean assistant endings.
  This is exposed-fit evidence, not generalization.
- Minimum development cross-entropy selected a worse generator: checkpoint 20 has
  CE 3.20395 but no valid completed fit conversations. Last CE is 4.07371 and last
  training loss is 0.56719. Loss alone cannot select a conversation model.
- The tiny diagnostic has 24 training sessions and 656 unique supervised token
  positions. The 13,120 target exposures repeat that material; they are not 13,120
  new examples. It is not an adequate broad English curriculum by itself.
- Checkpoint 30 still fails novel preference recall, correction-following, object
  ownership and missing-input clarification. Training-example recall is ahead of
  transferable instruction following and state tracking.
- Repeated advertisement, video, rating and website boilerplate occurs in raw
  continuations. That is evidence of undesirable learned continuation behavior;
  identifying its precise source in pretraining data remains unproven.
- Actual optimizer recovery is now exact with the explicitly selected eager Muon
  path. The earlier compiled mismatch is real, but it does not establish the cause
  of these conversation failures. Fixing replay alone did not fix English.

## Checks against premature conclusions

The assistant-end token is explicitly supervised by the serializer and shifted
training labels. A missing `autocast` wrapper is not by itself a serving defect:
the pinned model performs compute-dtype casts internally in both train and serve.
Teacher-forced endpoint probabilities were measured separately; they do not
replace free-running conversation scores. Baseline assistant-end probability is
roughly 5e-13 on fit reference endings, median rank32721/32768. At20 none of72fit
or36development reference endings rank the end token first. At30,65/72fit and
26/36development endings rank it first. Therefore the best-loss checkpoint had
not learned to stop even on correct reference answers. Last30has materially better
termination but still fails free-running unseen conversation. End-token supervision
is present; learned end-token likelihood is the problem, not a proven missing mask. No outputs are trimmed or rewritten to
manufacture a pass. The failed controller and persistent guard states remain intact.

## Termination diagnosis: a concrete training-design problem

First-epoch seed103 packed evaluation covers all24sessions/656targets, including
72assistant-end positions. It agrees with isolated conversations on end-token
argmax counts:0/72at0and20,65/72at30. Packing is not the explanation for the
observed failure to stop, although this does not prove packing has no other effect.

| Step | Content-token CE | End-token CE | Median raw end logit | Median softcap derivative |
|---|---:|---:|---:|---:|
| 0 | 2.3325 | 28.6148 | -42.0 | 0.0147 |
| 20 | 0.1954 | 10.5406 | -40.5 | 0.0179 |
| 30 | 0.0041 | 3.9751 | -8.4063 | 0.7416 |

These are teacher-forced packed diagnostic values, not reported training losses.
The head uses15*tanh(logit/15). The initially negative end logit sits in a strongly
attenuated-gradient region. This is direct evidence of suppressed conversational
termination and a plausible reason it adapts later than answer words. It is not
proof that changing this alone will solve generalization. At30content is nearly
memorized while stopping remains less confident and novel conversations still fail.

Protected development tools: all0/8turns at0,20and30; no actual tool calls. Last30
acknowledges Mysuru then reverts to stale Nashik. The diagnostic excluded positive
tool training, so these results do not establish that tool ability regressed from
a capable base; all three candidates fail. Raw outputs and reviews are retained.

## Next remediation boundary

Do not spend the remainder of the cap on blind repetition of this stopped fit.
The development-loss stop is a conservative predeclared rule, not proof that
generated conversation degraded: last30generates better than best-loss20on the
observed suites. Changing the rule after seeing this result requires a new
versioned experiment, not silently clearing the guard.

A revised experiment should address termination learning before broad conversation:

1. Predeclare a bounded conversational-control adaptation treatment against the
   untouched base. Consider supervised control-token warmup or explicit loss
   balancing; neither should be selected without comparing content degradation,
   premature stops and end-token rank on independent scenarios. A static decoder
   that truncates or rewrites answers is not a weight improvement.
2. Keep the existing24fit sessions immutable. Distinguish the limited memorization
   feasibility gate from generalization acceptance; do not demand an overfit toy
   task simultaneously prove broad English, and do not treat it as release.
3. Use the reviewed English curriculum with short answers, varied paraphrases,
   natural closings, correction chains and delayed recall. Split scenario families
   before variants, audit every answer, and count unique targets separately from
   repetitions. Preserve tools-enabled/no-call and tools-disabled/no-call coverage.
4. Select candidates with generated development conversations plus content/end
   losses, not aggregate CE alone. Predeclare guard thresholds and maximum updates;
   compare both best and last. Preserve the original failed run and guard history.
5. Stop if the treatment only memorizes prompts, produces premature endings, or
   worsens independent content/state tracking. No automatic epoch/LR/budget increase.
6. Only after development readiness: fresh independent release conversations,
   protected tool checks and local MPS qualification. Neither a small pilot nor
   unused budget guarantees a general English model.

Evidence: `assessment/closeout/packing-diagnosis/`,
`assessment/termination-summary.json`, and the hash-bound raw conversation reviews.
GPU qualification is finished; the remaining blocker is model learning and
curriculum/selection design. Best20andlast30are now fully hash-verified locally under
`runs/ganesh-a100-cap40-v1/local-fit/`. Last30successfully ran the3turn exposed
appointment-state conversation on local MPS with correct answers and termination.
This confirms runtime availability only; default/HTTPremain unchanged. All four retained fit checkpoints, complete remote raw evidence and final review
archive have passed fresh GCS readback. GCP rejected shortening terminationTime on
a running VM. Normal APIstop was requested after joined writers and backups; this
is explicitly not a successful scheduled-stop fault test. That release prerequisite
remains unproven. No additional training is running or queued.


Closeout confirmed: normal STOP at2026-11-17T23:15:10.675UTC, then the dedicated VM
and200GiBboot disk were removed under existing cleanup authority. Fresh project
inventory shows0VMs/0disks. Required backups were verified before shutdown/deletion.
Estimated cumulative compute/disk including priorL4is$10.61, excluding unsettled
storage/network; conservative margin plus reserves is$20.59under the$40cap.
Scheduled-provider STOP remains unproven; normal stop is not relabeled as that test.

## Thorough next-step reassessment — 18 November 2026

Assessment only: no new training, VM, dataset admission or changed gate authorized.
This refines the earlier termination-first recommendation. Improving termination
alone is insufficient and additional EOS pressure is not automatically desirable.

### A material correction to the interpretation

Reweighting the saved isolated teacher-forced diagnostics by actual content-token
count gives the following development results; all three use the same520content
and36end-token reference positions:

| Checkpoint | Unseen content CE | Unseen end-token CE |
|---|---:|---:|
| Base0 | 2.789902 | 28.829655 |
| Best-loss20 | 2.639400 | 11.580472 |
| Last30 | 3.939904 | 5.788230 |

Content CE worsened about49% from20to30 while end-token CE improved. This is real
reference-content deterioration, not just an unfortunate checkpoint-selection rule.
The guard was useful. Last30is a better free-running generator than20because it can
finish some answers, but a worse predictor of unseen reference content. Both facts
can hold. We should retain the stop and improve the objective/data/selection design.
Source-bound calculation: assessment/content-end-reassessment.json.

The existing fit confirms substantial memorization and partial chat-protocol learning.
It does not establish broad English improvement. The12development sessions are
small, repeatedly inspected, and not pristine release data. Blocked follow-ups count
as failures, but do not independently measure what the model would do given a valid
history. Report end-to-end and isolated diagnostic measures separately.

### Evidence-ranked explanations

1. **Established:** the exposed fit is tiny:24sessions/72assistant messages and656
   supervised token positions. The next prepared curriculum is also a seed pilot:
   31sessions/95assistant messages, including only6sessions each for ordinary
   conversation, instructions, corrections and memory. Neither warrants a broad
   English recovery forecast.
2. **Established:** answer termination is severely suppressed initially. However,
   endings already account for roughly60%of initial packed fit loss. Blindly
   increasing their weight can further distort content learning or cause empty
   answers. Suppressed logits and attenuated gradients are measured; causal repair
   by a particular warmup/reinitialization has NOT been demonstrated.
3. **Established:** optimization changes weights and can memorize short sequences.
   The exact eager restart fix does not supply missing conversational competence.
4. **Confirmed implementation, untested hypothesis:** SFT loads the base optimizer
   state and retains moments while changing learning rates. That is not inherently
   a bug, but it is not equivalent to a fresh task-specific SFT optimizer. Separate
   new-task warm-start policy from exact restart of an existing SFT run. A fresh
   optimizer arm must retain the identical own model weights, tokenizer and data.
5. **Unresolved:** base-language/compositional ability, pretraining source quality,
   boilerplate prevalence, policy-prefix influence, and generalization under changed
   names/order/phrasing. More training cannot be assumed to fix all of these.

### Initial proposed sequence — revised by the second review below

**1. Define the first product milestone and prepare evidence locally.** Basic
screen-free English chat, clarification, instruction following and3–6turn stateful
conversation inside native2Kcontext. No broad factual expertise,4Kclaim, maths or
CBSE milestone yet. Keep Ganesh-base/Navneet Prabhakar identity in a small reviewed
training share, then test it without giving the answer in the system prompt.

Build a compact source-disjoint development panel spanning everyday replies,
clarification, rewriting, grounding, preference retention, state corrections,
ownership/negation and clean closings. Compare Own base10B, last30and retained SFT194
on the same panel; use chat output plus plain-prefix/teacher-forced diagnostics.
Do not assume the latest checkpoint is the strongest parent. Do not use another
pretrained model as the serving solution. Diagnostic prompts become exposed;
create and protect a separate release panel.

**2. Replace the seed curriculum with a real, reviewed pilot curriculum.** A practical
initial design range is300–500distinct conversations, usually2–6turns; this is a
planning range, not a proven sufficiency threshold or a quota that overrides quality.
Cover different intents, answer lengths and conversational wording. For corrections,
use explicit state oracles, counterfactual swaps and late recalls; split whole
scenario/template/source groups before variants. Hold out some entity/order/wording
combinations. Avoid multiplying one template to satisfy the count.

Use reviewed Smol-SmolTalk training rows for natural phrasing, selected OASST training
paths where complete provenance and every turn pass review, and labelled Codex
examples for controlled correction/memory gaps. Smol-SmolTalk is synthetic, not an
organic human corpus. Existing source review found only a small shortlist; its
acceptance rate is not a population estimate and it does not justify bulk admission.
Source IDs, revisions, licensing, split ownership, near-duplicate checks and raw
versus edited lineage remain required. Codex-generated answers require semantic
review and state-oracle checks; syntax validation alone is insufficient.

Preserve required tool/no-call modes in a production-intent contract, with positive
tool material small and replay-verified. Tools are regression protection, not the
English milestone. Report family assistant-target mass, not just session percentages.

**3. Test one controlled optimization difference on that broader curriculum.** After
new local readiness and explicit new experiment approval, propose at most two bounded
arms from the same selected Own parent: current inherited optimizer moments versus
fresh optimizer moments. Everything else stays fixed: data/order, LR schedule,
objective, tokenizer, context, update and replay limits. Predeclare budget allocation
and exact limits after tokenizing/counting the reviewed corpus; no invented runtime
estimate from the24second tiny-fit measurement. Both arms start from identical
weights. This evaluates an optimization hypothesis while performing actual English
training. It does not assume optimizer reset will win.

This proposal requires a new versioned controller contract. The current frozen-fit
failure remains a failure. Do not silently waive its>=23/24gate or let the old
controller dispatch curriculum. In the proposed contract, learnability diagnostics,
generalization-pilot admission and release acceptance have distinct roles. If the
new design is not approved, training remains blocked.

Keep content/end losses separate; measure valid ending, premature/empty ending,
actual semantic correctness and complete-session success at fixed checkpoints.
Record matched baseline, best and last on real generated histories. Preserve all
blocked turns in the end-to-end denominator. Evaluate diverse reference prefixes
as diagnostics only, never substitutes for generated conversation success.

**4. Predeclare decisions and stop conditions.** Proposed pilot progress threshold:
at least70%valid completed turns and50%fully correct conversations on a new grouped
60session development panel, with improvement spread across families and no material
content-loss regression. These are engineering milestones, not statistical proof or
release criteria; thresholds need prospective review before any learning run.
Retain hard numerical, integrity, budget and writer stops. Define content-regression
threshold/patience prospectively from the fixed baseline and measurement stability;
do not select it to accommodate this run's failure. Two failed pilots force HOLD.

For a first narrowly scoped release, propose a separately authored, protected set
with>=90%correct turns,>=80%complete conversations and>=80%turn correctness in each
critical family, plus identity/grounding and tool regression checks. A60session
release panel is still small: report denominators and uncertainty and do not claim
broad benchmark competence. Independent grading remains outstanding; a second pass
by the same author is not independent review. Local MPS must pass the selected
candidate's checks before default promotion.

If both arms improve endings but not unseen content, stop optimizer tinkering and
assess foundation/data coverage. If plain-language comprehension is weak even without
chat controls, a bounded clean-English continued-pretraining experiment may be needed
before further SFT. That is a different budget and objective, not an automatic next
stage. If language works but conversation fails, focus on SFT diversity/state tracking.
If revised data improves held-out learning curves, scale distinct reviewed scenarios
before scaling repetition. No claim that several hundred examples guarantee success.

**5. Reduce operational overhead without weakening data protection.** Reuse exact
runtime-bound optimizer/recovery evidence when applicable; test changed objective
and optimizer-initialization paths specifically. Use one VM/one writer, measured
stage timers and a fixed provider deadline set before launch. GCP does not permit
changing terminationTime on the running VM in this campaign; do not depend on that
for extensions or a last-minute scheduled-stop drill. Keep the unresolved scheduled
STOP evidence explicit. Checkpoint at planned durable boundaries and failures, avoid
unnecessary repeated multi-GB copies, and verify required backups before shutdown.
The GPU should spend its useful allocation on learning and behavior assessment.

### External context, not a sufficiency claim

The official Smol-SmolTalk card describes460,341training rows, shorter conversations,
less specialist material and no advanced maths for sub-1B models. This supports the
curriculum direction, not copying all rows or claiming Ganesh needs that exact count:
https://huggingface.co/datasets/HuggingFaceTB/smol-smoltalk/blob/main/README.md
The SmolLM2 paper's1.7B result used roughly11trillion pretraining tokens. That is not a
minimum requirement for basic conversation, but it makes direct expectations of
commercial small-model quality from Own's10Btokens and a few dozen SFT conversations
unjustified: https://arxiv.org/abs/2502.02737 .

**Decision:** proceed with local foundation assessment, a broader reviewed curriculum
and a versioned experiment contract. Do not launch a VM or resume step30. The next
paid work should answer whether transferable English improves under controlled SFT,
not merely whether more examples can be memorized.


## Second adverse review — 18 November 2026

**Decision: revise the experiment priority; no new training is ready for dispatch.**
This review adds read-only local checkpoint analysis and 72 counterfactual scoring
records. No optimizer step, weight edit, data admission, serving-default change or
cloud operation occurred. These are same-author exposed diagnostics, not independent
release tests. Scripts, inputs and raw results are in `assessment/deep-review/`.

### What changed after testing the recommendations

1. **Fresh optimizer state is no longer the recommended first experiment.** The
   assistant-end output-head second moment at base10B is 2.6882e-25, versus
   4.03747e-7 at fit20 and 3.23771e-4 at fit30. Its inherited contribution after
   decay is negligible relative to the observed SFT state. The first moment also
   grows from effectively zero. This weakens the specific stale-end-token-moments
   explanation; it does not rule out effects of shared/trunk state or Adam step
   counters. Suppressed ending weights and inherited optimizer moments are different
   mechanisms. Resetting moments remains a possible controlled ablation, not a fix
   supported by these measurements. Never reset state during an exact resume.

2. **Weak state tracking appears outside chat framing as well.** Six simple pairs
   reverse ownership, meeting day, borrower/owner, negation, switch state and item
   location. A pair passes only when both reversed contexts rank the correct answer
   above the alternative. Results below show passing pairs out of six; each cell
   reports mean-token / joint-log-probability scoring.

   | Own checkpoint | Plain continuation | Canonical chat |
   |---|---:|---:|
   | base10B | 2/6 / 2/6 | 1/6 / 1/6 |
   | fit30 | 2/6 / 2/6 | 1/6 / 2/6 |
   | SFT194 | 2/6 / 2/6 | 1/6 / 1/6 |

   Static answer preferences often survive fact reversal. This is evidence against
   assuming chat controls alone explain the failure. However, six hand-authored
   pairs, answer-length/tokenization sensitivity and supplied candidate answers
   cannot establish a general capability ceiling. This is likelihood ranking, not
   generated conversation. There is no defensible winning parent from this panel.

3. **More EOS pressure is not justified.** Endings already contribute about 60% of
   initial packed fit loss. Development content CE worsened from 2.6394 to 3.9399
   while endings improved. Preserve the regression stop; measure premature ending
   as well as missing ending. Head reinitialization, softcap removal and loss
   reweighting are untested hypotheses, not authorized remedies.

4. **The corpus-count and percentage recommendations were under-specified.**
   300–500 conversations is a planning batch, not a demonstrated sufficient dose.
   The prepared 31-session curriculum has only 1,052 supervised target positions;
   it is a seed, not a credible broad-English remedy. Likewise the earlier 70%/50%
   pilot and 90%/80% release suggestions are unvalidated planning thresholds, not
   launch gates. Illustratively, 48/60 passing sessions gives a Wilson 95% interval
   of roughly 68.2%–88.2%, even assuming independent sessions. Correlated scenarios
   make that assumption optimistic. This is a hypothetical calculation, not our
   model's result. No existing acceptance contract has been changed.

### Revised next steps and decision checks

1. **Finish a balanced local foundation comparison before choosing a parent.**
   Expand ownership, negation, correction and delayed recall across independently
   written scenarios, answer positions, entities and distractors. Pair reversals
   within a split; keep related variants out of other splits. Compare base10B,
   fit30 and SFT194 with the same prompts. Include bounded free generation and
   generated multi-turn histories alongside reference-prefix diagnostics. Report
   semantic correctness, valid endings, premature endings and complete sessions
   separately. Examine disagreements between scoring methods rather than selecting
   the favorable score. These prompts remain exposed development material.

2. **Audit the foundation's actual inputs and build coverage, not repetitions.**
   Reconcile source composition, filtering, duplication and unique exposure in the
   10,000,269,312 processed pretraining positions; that count does not prove ten
   billion unique useful English tokens. Record unavailable evidence explicitly.
   Review natural English and grounded conversational examples for grammar,
   instruction following, clarification, reference resolution and state changes.
   Require source lineage, full turn review, state oracles and scenario-level
   separation. Use reviewed Smol-SmolTalk/OASST for appropriate natural phrasing and
   labelled Codex material for missing controlled skills. Count unique targets and
   per-family target mass. Preserve the frozen fit and protected release material.

3. **Choose the learning objective from the failure pattern.** If broad plain
   comprehension is adequate but generated chat is weak, prioritize a broader SFT
   curriculum from the best measured Own parent. If plain comprehension remains
   weak across balanced probes and natural continuations, compare a bounded clean
   English adaptation hypothesis before committing to more SFT repetition. Neither
   route is authorized automatically, and there is no evidence for a required
   number of additional billions of tokens. Optimize one defensible hypothesis at
   a time; do not spend another campaign mainly qualifying the same GPU/runtime.

4. **Freeze a new experiment only after the evidence supports it.** Bind parent,
   tokenizer, corpus/review receipts, objective, optimizer initialization policy,
   target exposures, checkpoint schedule and budget. Define prospective improvement
   and regression rules with per-family/session denominators and uncertainty.
   Separate learnability, generalization and release decisions. Existing failed
   controller state remains failed; two failed pilots force diagnosis/hold. Check
   changed training paths specifically and reuse applicable exact-runtime evidence.
   One writer, finite provider STOP, backup verification and local MPS acceptance
   remain mandatory. Scheduled-provider STOP observation remains unresolved.

### Research cross-check and limits

[LIMA](https://arxiv.org/abs/2305.11206) used 1,000 curated examples on a pretrained
65B LLaMA. Its result does not establish that a few hundred examples can supply
missing foundational skills in this 537M model. [TinyStories](https://arxiv.org/abs/2305.07759)
shows that very small models can learn coherent stories from simplified synthetic
language. That supports investigating focused language data, but story coherence
is not evidence of reliable multi-turn assistant behavior. Neither paper establishes
Ganesh-base's minimum data, compute budget or a guaranteed recovery recipe.

### Reproducibility and remaining limits

`audit_optimizer.py` checks bundle integrity and reads saved optimizer tensors;
`optimizer-state.json` records measurements. `probe_counterfactuals.py` loads the
retained local Own checkpoints and writes exact inputs, manifest hashes, scores and
summaries. `recommendation-sanity.json` contains the illustrative uncertainty and
moment-decay calculations. No release set was consumed. These diagnostics do not
replace a wider natural-language generation assessment, a pretraining-input audit,
independent grading or actual learning curves on the proposed broader curriculum.
The new evidence narrows hypotheses; it does not claim conversation has improved.


## Executed generated comparison — 18 November 2026

The next local comparison is now complete:576 single-turn outputs and216 rollout
records, fully reviewed, with input/manifest/parser integrity verified. See
[the generated-comparison report](assessment/generated-comparison/RESULT.md) and
[summary](assessment/generated-comparison/summary.json).

Native clean short answers: base10B0/96, fit30 27/96, SFT1940/96. All three score
0/12 complete clean native three-turn sessions. Fit30 has better short-answer
framing and semantics, but a fully valid Sunday-to-Monday correction exchange still
ends with Sunday. Neither stopping alone nor the older SFT solves conversation.

The next hypothesis is broader reviewed contextual-conversation SFT, provisionally
starting from fit30 and comparing against an exposure-matched narrow replay control.
This is not a launch-ready recipe or parent promotion: short-answer gains do not
establish conversational superiority, and no new corpus/contract/cap is approved.
Keep existing failed guards/frozen data, retained weights, serving default and VM
state unchanged. The report records exact scores, limitations, stop conditions and
remaining readiness work; it supersedes the earlier pending local-comparison step.
