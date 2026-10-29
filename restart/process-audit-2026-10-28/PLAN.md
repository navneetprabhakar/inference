# Revised plan — no training authorized by this document

Date:28 October 2026. Requested deliverable: audit and revised plan **before training again**. Historical checkpoints, failed gates and exhausted ledgers stay unchanged. This proposal defines a new study; it does not restart an old arm or reset its budget.

## Decision

First repair measurement and make the data support the intended skills. Then run one small factorial experiment that separates **instruction diversity** from **preservation pressure**. Only after that result choose whether to invest in broader foundation training or model capacity. Do not default to another LoRA run, larger model, longer TinyStories continuation or another teacher-generation batch.

## Phase A — prepare a decision-ready packet, zero optimizer updates

### A1. Define the product boundary

Draft pilot contract: supplied-context English answers, relevant clarification, short explanations, instruction following and corrections across two to four turns. No unsupported outside knowledge, hidden large-model fallback or tool access. Include topic switches and explicit “not supplied” cases. The eventual goal remains broader conversation and tools; this contract is the first demonstrable milestone, not a silent reduction of that goal.

Create 24 public-to-review example conversations:12 acceptable,6 borderline,6 clear failures. These are rubric anchors, never training or final tests. State required facts, prohibited additions, format requirements, expected dialogue act and state after each turn. Freeze how concise paraphrases and minimal reminders are treated. Agreement on borderline cases matters more than perfect scores on obvious failures.

Measure actual context needs. Preserve 256 context for a short diagnostic only when the complete prompt/history/output allowance fits. If representative pilot cases do not fit, declare the current architecture insufficient for that contract and scope a context extension with its own correctness/compute tests. Do not truncate hard cases to make the metric pass.

### A2. Build the evaluation matrix before curriculum tuning

Use a structured scenario generator with independent axes: entity identity, attribute value, answerability, target position, distractor, requested output format, correction, topic and instruction phrasing. IDs live in metadata; numeric IDs in user text appear only as an explicitly balanced distractor condition.

Four main cells, keeping each underlying scenario paired where appropriate:

| Cell | Fact/value combination | Instruction wording |
|---|---|---|
|A|Seen|Seen|
|B|Unseen|Seen|
|C|Seen|Unseen|
|D|Unseen|Unseen|

Separate known name components in new combinations from genuinely new components. Separate new times made from familiar digits from distractor-number challenges. Add ID-present/absent, value substitution, missing/present and reversed-update counterfactual pairs. Split by scenario family and paraphrase family, not random rows. No sibling paraphrases of a sealed test scenario may enter training.

Proposed development inventory: at least 32 scenario clusters per task family per cell across eight prerequisite families; label this a diagnostic sample with uncertainty, not a guaranteed population estimate. Use identical heldouts for all study arms, score by scenario cluster and report paired differences. Old repeatedly inspected development examples become a regression bank, excluded from model selection in this new study.

Separately prepare 240 naturally phrased final conversations,40 per each of six dialogue families, with two to four turns and topic variation. Independent author/reviewer where available; otherwise explicitly label primary-agent authorship and obtain user/human review before claiming independent confirmation. Audit ambiguity and feasibility before sealing. Keep the existing untouched final bank closed as an additional legacy check, not a substitute for the new product-representative bank.

### A3. Scorer and harness contract tests

One versioned runner, declarative configuration, explicit parent/config/data hashes and append-only accounting. Test without training:

- exact role framing and native token IDs; causal shifted labels, assistant/EOS masks, no user/padding targets;
- correct and wrong full names/times, negation, stale state, unsupported additions, concise valid variants, premature EOS/BOS and context overflow;
- deterministic oracle that answers from structured scenario state; known-bad answerers (copy first number, repeat previous answer, always ask, always say unknown) must fail relevant subsets;
- independent, blinded semantic rubric calibration including borderline cases; report disagreements rather than silently choosing favorable grades;
- source/target tokenizer and loader compatibility; preserve old MCP path separately;
- exact save/reload state contracts and tested graceful cap shutdown, with final checkpoint/evaluation reserve;
- after a future model-run approval, retain bounded independent numerical/gradient and resume checks in disposable states. Do not count these as capability work.

Ready gate: zero schema/mask/oracle mismatches; every task has positive and negative scorer fixtures; no exact train/final overlap; family-split and counterfactual coverage checks pass; all selected natural labels are reviewed; context fit is explicit. A checksum is not a semantic admission test.

### A4. Inference-only discrimination before training

This is proposed work, not executed by this audit. Freeze a separate inference budget after timing a small batch; initial ceiling 30 active-model minutes,5M input positions,0 updates,0 external calls/downloads. Evaluate a minimal diagnostic packet on the original foundation, factual child A, broader child B and one grounding adapter checkpoint. Use compatible loaders, never pick the latest checkpoint by filename.

Run paired normal/novel phrasing, familiar/unfamiliar values and numeric-ID present/absent tests. Compare gold-history versus generated-history only as a diagnostic of error propagation; acceptance always uses generated history. For name/time failures, inspect first erroneous token, correct-answer rank/log-probability and EOS behavior without suppressing EOS or replacing student output. Require differences across matched cases before attributing a bottleneck to wording or distractors.

This phase may eliminate unnecessary training arms. It does not establish a remedy or authorize optimization. Deliver the ready packet and update the hypothesis table before launch approval.

## Phase B — one controlled training study, conditional on A

### Data

Prepare a balanced 3,200-conversation prerequisite corpus:400 each for name, time, location, distractor binding, state update, missing information, clarification and requested sentence/short format. Sample independently across the structured axes; include same entities/values under different questions and answerable/unanswerable variants. Do not couple color to missingness or initial location to a single successor.

Make two matched versions using **identical facts, assistant targets, answer lengths and task proportions**:

- Single-pattern control: one canonical instruction per task.
- Diverse condition: at least 20 independently reviewed instruction/paraphrase families per task, balanced across facts and difficulty. Repeating one template with synonyms does not count as 20 independent linguistic patterns.

Both conditions include all eight tasks in the same proportions throughout; do not repeat Cycle 12's confound of adding variants while collapsing training to two tasks. No natural-teacher curriculum jump in this prerequisite study. If unreviewed synthesis is used for drafting, it is not admitted until deterministic labels and semantic preservation pass review.

### Four primary arms

| Arm | Training wording | Narrative replay loss coefficient |
|---|---|---|
|1|Single pattern|0.5|
|2|Diverse|0.5|
|3|Single pattern|0.0|
|4|Diverse|0.0|

The assistant objective has weight 1−replay coefficient, with equal per-task normalized shares. This tests two policy choices and their interaction; it does not purport to isolate every optimizer-scale effect. Report useful target exposure, input positions, actual wall time and update norms separately. Match assistant examples/targets and update count; the no-replay arms will consume less narrative compute. If compute-equivalent effectiveness matters, make it a separately reported comparison, not an unspoken equivalence.

Use the same original own foundation checkpoint and fresh optimizer in all four arms; full fine-tuning is the reference. Keep tokenizer, context, dropout, scheduler and data order fixed except for the stated factors. Choose LR through a training-only calibration with predeclared candidates 2e-5,1e-4,5e-4 and at most 100 disposable updates per candidate under each objective (≤600 updates total); select one common stable LR using balanced train loss/finite-update evidence, without looking at sealed development answers. If no common stable setting exists, redesign the optimizer comparison rather than mixing incomparable settings.

Primary screen:1,000 updates per arm, with coverage scheduled to include every training scenario at least twice. Evaluate the shared source baseline once; use a frozen 128-scenario balanced sentinel subset at 250 and 500 and the full development matrix at 1,000. Intermediate checks diagnose collapse; endpoint comparison uses the same complete packet. Use one predeclared endpoint selection rule rather than best-of-many manual cherry-picking. Then repeat the two informative conditions with two additional seeds. Eight retained experimental trajectories maximum; the four-arm first seed is screening evidence, not a final causal claim. Save all failed seeds and report variance.

### Quality rules and budget

Old story+5% is recorded as a reference line, **not an automatic stop in the new no-replay diagnostic**. Those branches are isolated research children. Stop immediately for nonfinite arithmetic, invalid inputs, verified implementation defects or resource limits. Prospectively stop a branch for gross degeneration only after two scheduled checks show at least a30-percentage-point loss of both source-grounded retention and intelligible-response rate on the independent regression packet; this is a proposed futility policy, not a calibrated law. Final eligibility still requires useful conversation and explicitly reviewed preservation. Never reclassify old failures under these rules.

Proposed total envelope:≤8,612 optimizer invocations (8,000 main,600 calibration,12 numerical/resume),≤100M input positions,≤2M assistant/EOS target exposures,≤20M narrative targets,≤3 active-model hours including validation,≤6GiB additional artifacts,≤12GiB process/GPU memory,≥60GiB free disk. These are ceilings, not consumption targets or time guarantees. Run a feasibility calculation from measured throughput and generation costs before approval; if the full primary comparison cannot finish with evaluation reserve, reduce the predeclared study uniformly or propose a larger budget. Never truncate just the last treatment arm.

Candidate prerequisite gate, proposed for freezing after A:≥90% factual/instruction-correct turns in the unseen-fact/unseen-wording cell,≥80% in every task family,≥80% complete state conversations, and no regression larger than 5 percentage points on independently varied preservation behavior. Report cluster uncertainty and individual failure types. These are operational choices for this pilot, not externally validated industry standards. A qualifying point must lie on a measured acquisition/preservation tradeoff, not just below a story-loss line.

Decision rules:

- Diversity helps across seeds while preservation holds → extend balanced curriculum to natural dialogue.
- Lower replay helps acquisition but harms preservation → quantify the tradeoff; test mixed-domain preservation data or a staged schedule next, not an arbitrary weight sweep.
- Seen fitting remains poor → investigate optimization/representation and training coverage before interpreting unseen scores.
- Seen fitting is good but cellD remains poor → improve scenario coverage/compositional supervision; retain specific counterexamples for next training generation, with a new sealed confirmation set.
- Every adequately fitted condition fails transfer → proceed to the foundation/capacity branch below; do not claim a capacity ceiling from this one study.

## Phase C — natural conversation, only if prerequisites transfer

Build a reviewed corpus with a gradual mix of short grounded answers, explanations, relevant clarification, corrections and topic changes. Match the pilot's task distribution and multi-turn lengths. Preserve all prerequisite families; validate labels for requested scope, unnecessary caveats and unsupported claims. Select examples for coverage, not merely whether they fit 48 generated tokens.

Use a two-condition comparison against the prerequisite source with an identical preservation mixture. Freeze the exact corpus size/exposure budget after admission; no automatic “generate more examples” escalation. Final acceptance proposal:≥90% supported/task-correct turns overall,≥80% per family and≥80% wholly successful conversations; material unsupported claims≤5%; no hidden repairs/fallbacks; context overflow counts as failure. Require blinded semantic review and report disagreement/uncertainty. Final testing occurs once after selection; a failed exposed final bank becomes regression evidence, never fresh evidence again.

The user-facing natural examples, not a single composite score, determine whether this pilot matches the intended conversation. Tool training remains a separate stage requiring schema/serialization integration and actual result-grounded end-to-end tests.

## Conditional foundation/capacity branch — not an automatic detour

**Broader foundation hypothesis:** create a provenance- and extraction-verified pilot corpus with genuinely different English domains. Reclassify valid-but-mislabeled documents; quarantine corrupt units; preserve source permissions/attribution obligations. Replace arbitrary global rejection with documented per-unit policy plus statistically honest fresh sampling and source-family splits. Do not require all factual prose to be independently fact-checked before a language-learning experiment, and do not treat unchecked claims as certified facts. No existing quarantine is lifted by this plan.

Compare equal added target exposures of admitted broad prose versus TinyStories from the same own checkpoint, with matched schedules, then apply the same successful or best-understood prerequisite curriculum. Size the pilot to test a measurable hypothesis; neither 10M nor a billion tokens is a magical threshold. Freeze this as its own study after corpus admission and measured throughput; current evidence cannot support an honest cost/ETA yet.

**Capacity/tokenization hypothesis:** if data/optimization controls are sound but capacity remains a plausible limitation, analytically screen one 40–60M candidate under the 100M ceiling, including embedding/head/context costs. First compare tokenizer fertility, name/time segmentation, memory and throughput. A new tokenizer requires a new pretraining lineage; do not transfer incompatible matrices or compare raw token NLL across vocabularies. Compare learning curves at equal data exposure and report the unequal compute; assess equal-compute efficiency separately. One well-controlled size comparison is preferable to a model sweep.

Broader English is still part of the eventual product, even if a bounded context-grounded pilot succeeds first. Conversely, do not block all low-cost skill diagnostics on a large corpus release that has not yet been constructed.

## Exit and resumption

This audit ends with a plan, not new training. Next authorized work should be PhaseA preparation and its separately scoped inference check. Training requires a ready packet and explicit approval of the new experiment and budget, consistent with the user's request to plan first. No changes to old thresholds, ledgers, data manifests or checkpoints are needed. Keep commits batched and raw data/weights private.
