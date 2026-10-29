# Proposed prerequisite screen — 29 October 2026

Status: specified for review, zero training authorized or executed. This supersedes the original Phase B wording-family claim and scopes the first screen; it does not restart historical ledgers.

## Question and controls

Does training with 20 surface instruction variants per task improve transfer to reserved wording, and how does narrative replay change acquisition and preservation? These are surface variants, not 20 independently established linguistic families. Both arms balance question order, attribute order and all eight tasks. Multiple attribute questions share the same fact worlds. Wording diversity is the treatment; changing task proportions or adding order variation only to one arm is prohibited.

Use the frozen Phase A prepared-v2 canonical/diverse curricula and schedule, unchanged. Use the original own foundation checkpoint named in the Phase A inference manifest, fresh full-fine-tuning optimizer state per arm, native tokenizer, 256 context and the existing loss masking/serialization. No LoRA substitution or pretrained imports. Four arms: canonical/replay 0.5, diverse/replay 0.5, canonical/replay 0, diverse/replay 0. Use assistant weight 1 minus replay weight; normalize assistant loss equally across tasks. Replay changes objective scale as well as data exposure; the study does not isolate those mechanisms.

The proposed optimizer is AdamW (betas 0.9/0.95, epsilon 1e-8, weight decay 0, bias correction, global norm clip 1.0), with a constant learning rate chosen by training-only calibration. This is a design choice requiring numerical validation, not a demonstrated optimum. Freeze dropout/model config, precision, replay token stream and runner hashes in the runnable launch manifest before calibration. These cannot be selected from development performance. A prose plan with those fields missing is not executable readiness.

## Scope and context decision

The immediate screen is the eight-task prerequisite study at a 32-token reply cap, including EOS. No history truncation, EOS suppression, answer repair or hidden fallback. Reaching the cap without EOS is a failed turn; reserve the cap for every earlier reply when checking history length. Prepared-v2 prerequisite records fit with maximum 241 tokens.

The revised 24-case / 88-turn natural development packet is an additional qualitative transfer diagnostic under the same explicitly short-response cap. Its references use at most 16 tokens including EOS; worst-case history plus current reply is at most 224 after reviewer corrections. This supports feasibility for these cases, not all acceptable paraphrases or longer conversation. Recompute after corrections. The 48-token natural product contract remains unsatisfied at 256 context; a context extension is separate work before broader acceptance.

All 24 new cases are development, never a sealed final set. The old 240 templated candidates also remain development/context fixtures. No claim of representative natural final acceptance may use either set. A genuinely separate final bank is required before a natural-conversation claim, but is not a reason to prevent a scoped prerequisite experiment.

## Measurement and acceptance

Use the 1,024-case A/B/C/D matrix and 256 counterfactual cases. A/C reuse training worlds intentionally, B/D hold out relevant facts/relations. Compare the same clusters across arms; report per-task and per-cell counts, exact/content/instruction/EOS results, complete conversations and paired gains/losses. Report names with new components separately from new combinations of known components. Counterfactual success requires both members correct; invariant and answer-changing interventions are separate metrics.

Proposed eligibility thresholds, fixed before training:

- Cell D: at least 90% correct turns overall and at least 80% in each task.
- State: at least 80% wholly correct conversations in cell D.
- Numeric-invariant and answer-changing counterfactual pairs: at least 80% both-correct in each intervention group. Publish denominators; small groups limit inference.
- Preservation: no more than five percentage points below the shared source baseline on a separately frozen, varied behavior regression packet. Freeze its membership and score contract before launch; historic narrative loss is supplemental, not a substitute.
- Natural diagnostic: publish every reply with semantic review. A timestamp-only reminder fails its requested act. A supported causal inference may pass without matching reference words. Borderline is not a pass. Do not call prerequisite eligibility acceptable general conversation.

Generated history is always the scored condition. Gold history, if run, is labelled diagnostic only. The current structured clarification scorer can accept minimal times; report that subtask as clarification/value handling, not natural reminder writing. Do not retroactively change frozen historical grades.

## Schedule, selection and resource envelope

Screen one seed, four arms, 1,000 updates each, same ordered assistant examples. Evaluate the shared baseline once, the same fixed 128-scenario sentinel at 250 and 500, and the complete matrix/counterfactual packet at 1,000. Use the endpoint only for selection. Select a diverse-versus-canonical pair at the same replay coefficient: prioritize eligibility, then cell-D paired gain; ties choose replay 0.5. If neither coefficient yields an informative fitted contrast, diagnose before adding seeds. No automatic extensions or checkpoint cherry-picking.

Training-only learning-rate calibration: candidates 2e-5, 1e-4, 5e-4, at most 100 disposable updates each under each replay objective (600 total). Choose one common finite/stable rate using training losses and update norms; no development score selection. Reserve at most 12 disposable numerical/save-reload/resume checks. Save calibration failures as evidence. A common stable rate is required; otherwise redesign the comparison.

First-stage ceiling: 4,612 optimizer invocations including calibration/checks, 50M charged input positions, 1M assistant/EOS targets, 10M narrative targets, 90 active-model minutes including inference/validation, 6 GiB additional artifacts, 12 GiB process/GPU memory, at least 60 GiB free disk. These are proposed maximums, not a runtime forecast or present authorization. Full two-extra-seed confirmation remains a separate decision; the original eight-trajectory/three-hour envelope is not implicitly approved.

Exact CPU accounting for 1,000 scheduled updates per arm, batch of eight, padding to the longest full conversation in each batch:

| Arm wording | Assistant targets | Unpadded input positions | Batch-padded positions |
|---|---:|---:|---:|
|Canonical|47,909|632,443|977,344|
|Diverse|47,909|656,032|1,067,560|

Across four main arms: 191,636 assistant targets and 4,089,808 batch-padded assistant input positions. Replay, calibration, numerical checks and evaluation are additional. Equal targets do not imply equal compute. These estimates require the runner to use the stated whole-conversation batching; recompute for turn batching, packing or fixed-256 padding.

Before launching retained arms, measured disposable calibration must project completion of all four arms plus at least 25% evaluation/checkpoint reserve within remaining limits. Backward throughput is currently unmeasured for this exact grouped implementation. If infeasible, stop and propose a uniform reduced screen or new budget; do not run only favorable/early arms. Reserve before every model forward/update and preserve cumulative charges on failure/restart.

Stop immediately for nonfinite arithmetic, serialization/masking defects or a resource ceiling. Preserve failure evidence. Narrative +5% is a reported historical line, not an automatic stop for the research no-replay arms. Gross-degeneration stopping requires the separately frozen behavior packet and two scheduled checks; it cannot be invoked from subjective inspection.

## Launch checklist still required

1. Finish the reviewer corrections and freeze the new diagnostic packet.
2. Build and verify the actual grouped runner, versioned scorer overlay, regression/sentinel membership, replay source and concrete optimizer manifest without changing frozen data.
3. Obtain explicit approval for this scoped training/calibration budget. Preparation approval does not authorize disposable optimizer steps.
4. Execute numerical/resume checks and measured calibration inside that budget, then launch only if all gates pass. Reassess after the four-arm screen before repeat seeds or natural-dialogue training.
