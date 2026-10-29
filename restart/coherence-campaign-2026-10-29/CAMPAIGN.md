# One stage-gated coherence campaign

**Decision: close the open-ended diagnostic loop. Require foundation readiness, then execute one frozen conversation comparison, one confirmation and one final test.** This is a proposed campaign with fixed limits; it is not authorized or launch-ready. The [foundation audit](FOUNDATION_AUDIT.md) finds readiness unestablished, not a proven capacity ceiling.

The first deliverable is short, supplied-context English conversation under the [acceptance contract](ACCEPTANCE_REGISTRY.md). It is not unrestricted English chat. The model stays15,191,712 parameters,256-token context and the current tokenizer. No architecture expansion, tokenizer change, tools, pretrained weights or hidden helper model is permitted inside this campaign. Those become an explicit product/architecture decision if this recipe stops.

## Gates and allowed transitions

### G0 — complete and freeze admission, measurement and execution contracts

Before model work: create/review the fresh readiness packet,120-conversation development set and240-conversation final set; calibrate reviewers; audit scenario-family and exact overlap; prove generated-history context fits; freeze the data, replay, hashes, schedules, scorer and stage budgets. Final payload custody must be separate from training/example selection. Existing exposed packets remain regression/calibration assets only.

Create6,400 reviewed training conversations:800 per each of six natural functions, plus800 name-copy and800 time-copy examples. Natural cases have2–4turns and match the pilot's function/structure distribution. At least25% of each copying task uses novel combinations from its training component pool; at least25% uses varied component lengths/segmentation. Every paired fact change must affect the reference correctly. All training/final scenario families and concrete assignments are disjoint. Such quotas are operational coverage requirements, not a claim that a data count guarantees learning. All labels require nonauthor semantic review;20% get a second review. No unresolved ambiguity is admitted.

Preservation replay is drawn only from training-side admitted material, frozen once and shared by both SFT conditions. Use a deterministic deduplicated block inventory with counts/weights reported; do not silently reuse3,200 historical rows as3,200 distinct examples. Native validation stays separate. Exact block separation is insufficient by itself: inspect document/source-family leakage before release. If native source provenance cannot support that claim, record the limitation and do not call native loss an independent broad-language test; the fresh readiness behavior packet remains the principal preservation test.

For the conditional recovery branch, freeze the candidate source inventory and prospective admission policy before baseline outputs are inspected. Require≥4M admitted broad training tokens after document/source-family splits, with≥1M each everyday, procedural and explanatory prose; the remaining≥1M may be any of those domains. This is a fixed supply floor for this comparison, not an evidence-based universal threshold. Check permissions/provenance, extraction completeness, duplicated units and domain relevance separately. Unverified factual prose is neither automatically unusable nor certified true. On a fresh100-document stratified audit: zero severe corruption/wrong-language cases and at most5 major extraction/domain defects; quarantine defective units and rerun one fixed100-document sample after the single permitted repair batch. No second repair cycle. No current D0 quarantine is lifted by this document. If this branch is needed and admission fails, stop; do not substitute an unreviewed corpus.

One pre-launch revision batch is allowed for data/scoring defects. If it still fails admission, terminate preparation. Do not repeatedly relax quotas until something passes. Once model outputs are seen, no data, threshold, optimizer, schedule or selection changes are permitted. Technical fixes require a new version; affected comparison is invalid, not silently resumed.

Measure timing within the engineering allocation, then prove **all remaining scheduled work plus25% reserve** fits both its stage caps and the global remainder. Use actual frozen context/token counts. If infeasible, stop before training; no asymmetric truncation, cap increase or reduced last arm. Historical throughput only motivates the budget proposal.

### G1 — measure foundation readiness once

Evaluate the existing B checkpoint using the fresh non-chat packet. The existing source has no readiness pass; grammar choice scores cannot substitute for generation.

All thresholds must pass:

-≥48/60 coherent native continuations and≥11/15 in every domain. Passing means intelligible grammatical English, preserved premise/entities, logical continuation, no material contradiction or pathological repetition. Ignore only a final cap-cut fragment; a complete sentence is required. Do not turn fluent but unrelated text into a pass.
-≥96/120 grounded choices, with≥24 more correct than **each** empty/shuffled-passage control. Balanced option positions and validated joint-token suffix scoring are required.
-≥54/60 distinct grammar contrasts. This is necessary but never sufficient.
-Reviewer calibration/agreement meets the fixed registry contract. Invalid measurement is not a model failure and does not release training.

If all pass, bypass recovery and use B. If valid measurement fails any capability threshold, allow G2 once. No separate low-LR copying follow-up is part of this campaign; that prior suggestion is deferred so it cannot become another side loop.

### G2 — one conditional foundation-recovery comparison

Only after admission and engineering checks, start two independent children of the same B weights, with fresh matching optimizer state:

| Control | Treatment |
|---|---|
|100% native-story training targets|50% admitted broad prose +50% native-story targets|

Each arm:128 updates ×131,072 target positions =16,777,216 targets. Same input/target budgets, seed291101, packing/boundary rules, microbatch16×accumulation32, native256 context, BF16 compute/FP32 master and moments. Fixed AdamW LR1e-4, betas0.9/0.95,epsilon1e-8,zero weight decay, global clip1.0, no warmup/LR search. This is a new prospective constant-LR recipe, not continuation of the old optimizer/scheduler state. Verify accumulated gradients and save/reload with the reserved disposable checks before applying it to retained arms.

Endpoint-only readiness evaluation with the same frozen packet and full native NLL. An endpoint qualifies only if G1 passes and native NLL≤1.25×B. If neither qualifies: **STOP_FOUNDATION**. No additional epochs, different mix or larger model inside this campaign. If both qualify, select higher coherent-continuation count, then higher grounded count, then lower native NLL; an exact tie selects native-only. This identifies a bounded useful starting point, not universal evidence of domain or capacity effects.

### G3 — one conversation screen

Use the passed foundation, identical fresh optimizer/RNG, LR1e-4,AdamW settings as above, seed291102. Two arms differ only in narrative replay loss coefficient:0.25 and0.5. Assistant weight is1−coefficient; loss is per-conversation target-normalized then averaged. Replay changes gradient allocation, not merely example counts; do not claim it isolates all mechanisms.

Each arm runs exactly1,000 updates. Batch8: one conversation from each of six natural functions plus one name-copy and one time-copy case. Each of the800 records/task appears once in the first800 updates, then a frozen balanced200-record subset repeats; both arms see identical data. One fixed eight-block replay batch is paired with each update. No lesson is added in response to failures. This is a prospective natural-conversation curriculum, not an extension of a tiny-copy checkpoint.

At500: evaluate only the existing24-case/88-turn natural regression packet for diagnosis; it cannot select an endpoint or trigger subjective quality stops. At1,000: evaluate new120-conversation development, readiness preservation and native NLL. Keep full failures. Source conversation baseline is measured once on the same development set but cannot alter the recipe.

Eligibility uses the conversation gate below and preservation: the foundation-readiness gate must still pass, no decline greater than5 percentage points in any of its overall generation/grounding/grammar accuracies versus the selected foundation, and native NLL≤1.25×that foundation. The decline field is the maximum positive decline; gains cannot compensate for another metric's loss.

If neither arm is eligible: **STOP_RECIPE**. If both qualify, select more wholly correct development conversations, then better worst-family whole-conversation accuracy, then more correct turns, then lower native NLL, then replay0.5 on an exact tie. Never select lowest training loss as a surrogate for coherent conversation.

### G4 — one confirmation run

Repeat the selected recipe once from the same passed foundation with fresh seed291103 and a frozen alternate data/replay order,1,000 updates. Keep examples, exposures and all hyperparameters unchanged. Repeat the fixed midpoint/end evaluations. Both original and confirmation endpoints must pass the development and preservation gates. A failed confirmation gives **STOP_UNCONFIRMED**; no third seed, cherry-picked best checkpoint or averaged-away failure. Passing is limited replication evidence, not a precise seed-variance estimate.

The confirmation endpoint is the sole final candidate. Do not choose whichever seed looks better.

### G5 — open final once

Generate the240 custodied final conversations exactly once under generated history and normal EOS, then have blinded reviewers grade every turn. No final-set-based model selection. Apply the same conversation thresholds. A failure gives **STOP_FINAL**; no corrections/retest within this campaign. A pass means **BOUNDED_PILOT_PASS** only, with limitations and a representative transcript pack—not general open-domain or tool readiness.

## Conversation gate: all conditions required

Use actual turn denominators; do not round percentages up. Development has120 conversations/20per function; final240/40per function.

-≥95% turns use intelligible grammatical English;≥90% are relevant.
-≥90% turns satisfy the complete semantic/act/instruction/continuity contract.
-≥80% whole conversations pass overall and≥80% in **every** function (development≥16/20;final≥32/40).
- Material unsupported claims≤5% of turns; factual/state contradictions≤2%; normal termination≥98%. These failures also make their turns/conversations fail, so metrics do not forgive one another.
- Review validity, complete review coverage and no hidden repairs/fallbacks are mandatory.

These are fixed operational pilot thresholds, not industry standards or a promise that humans will find the product broadly useful. Raw transcripts, failure categories and conversation-level uncertainty accompany every result. Exact strings are required only where explicitly requested.

## Hard budget and accounting

All figures below are **additional** to the closed successor ledger. A stage stops at its first cap. Stage limits cannot borrow from one another; unused conditional recovery or engineering allowance stays unused.

| Stage | Maximum new updates | Active student minutes | Input positions |
|---|---:|---:|---:|
| Fresh readiness |0|20|5M|
| Disposable numerical/resume/throughput checks |12|10|2M|
| Conditional foundation recovery, two arms |256|90|40M|
| Conversation screen, two arms |2,000|90|30M|
| One confirmation |1,000|45|15M|
| Final acceptance |0|30|8M|
| **Total** |**3,268**|**285**|**100M**|

Engineering allocation is at most6 updates for the accumulated foundation recipe and6 for the conversation recipe. Previously verified arithmetic is reused where applicable; no generic hyperparameter calibration sweep. Checks still count even when disposable. Recovery is skipped if baseline passes; its check allowance may likewise remain unused.

Other global ceilings:3.1M assistant/EOS training targets,41M foundation/replay language targets,6GiB new artifacts,12GiB process/GPU memory,≥60GiB free disk. All startup, inference, backward/optimizer work, validation, checkpoint writes/reloads and failed work count. Reserve before work; atomic time overrun cannot authorize another operation. A hard stop preserves available evidence and labels incomplete comparisons as incomplete.

Separate authoring/review envelope:≤80 model requests and≤6M total input+output tokens, counting failed requests; zero such calls are authorized by this planning turn. Use one batch of pre-launch revisions and at most one repeat output-grading pass. Cannot silently increase reviewer calls or switch reviewers after seeing unfavorable grades. Preflight must show the planned review volume fits this ceiling. Human time and model wall time are not hidden inside student active minutes.

Carry the latest tiny-copy successor ledger once:5,636 updates,24,847,840 positions and1,732.4593 seconds (28.87active minutes). Full proposed cumulative maxima: **8,904 updates,124,847,840 positions,313.87active minutes**. These are successor-study totals, not lifetime pretraining expenditure. Older foundation/campaign ledgers stay separately documented and immutable. No budget is reset or recycled.

Historical evidence suggests the fixed foundation comparison's33.55M targets would take roughly46–47 active training minutes at12k targets/sec, before evaluation/startup. Recent SFT steps were much cheaper. Neither number certifies this future mixed-data run: the launch feasibility gate must use the actual admitted corpus, schedule and measured recipe, with25% reserve. The285minutes are a hard ceiling, **not an ETA or intended spend**.

## Terminal conditions and what happens next

Stop for any numerical/resource/integrity breach; unresolved input/scorer/reviewer defect; inability to admit the fixed data; inability to fit remaining work plus reserve; failure of the sole foundation recovery; no eligible conversation endpoint; failed confirmation; or failed final acceptance. No spontaneous smaller experiment, new learning rate, data patch, checkpoint repair, tokenizer or architecture change may follow inside this campaign.

A terminal report must choose a clear interpretation: measurement invalid, foundation unready, acquisition/retention incompatible under this recipe, unconfirmed result, or failed final generalization. It must separate evidence from hypotheses. After a stop, the owner decides whether to change data/model/context constraints in a **new** campaign. The current plan cannot guarantee coherence from15M parameters, and must not disguise uncertainty as an endless sequence of inexpensive tweaks.

Current execution status: **G0 incomplete; no training or new inference authorized.** Fresh packets, independent review/custody, admitted data, executable manifests and measured feasibility remain. The audit and consolidated decision/budget contract are complete; the missing launch artifacts are not represented as finished.

Once the owner approves the full campaign and G0 is satisfied, eligible stages proceed automatically under this decision tree; no repeated permission request is required at every passing gate. A terminal stop ends the campaign and requires an explicit new decision rather than an improvised continuation.
