> Superseded local status: see [current pilot readiness](../ganesh-controller-v1/READINESS.md) and [latest adverse review](../ganesh-controller-v1/ADVERSARIAL_REVIEW.md). The blockers and counts below describe the earlier review, not current local status. No prior budget is reopened.

# Ganesh-base: controlled English recovery launch plan

17 November 2026. Model: Ganesh-base. Creator: Navneet Prabhakar.

**Current decision: HOLD. The plan is consolidated; a hands-off VM launch is not yet ready.** Readiness is evaluated by evidence, not by renaming this document. No cap, cloud write, training or release exposure is authorized here. Default path is exact-resume qualification; the proposed no-resume exception is NOT selected. This replaces the two deleted overlapping proposals. Previous critique is retained at ../ganesh-continuous-vm-plan-v1/ADVERSARIAL_REVIEW.md.

## 1. Immutable objective and boundaries

Demonstrate everyday English conversation, within-window recall and correction precedence in Ganesh-base's own weights. Embed the supplied model/creator identity through reviewed training and test it without identity-bearing system prompts. Keep the current local model available; HTTP off. No hidden pretrained substitute, response rewriting, math/CBSE expansion,4K claims or cross-chat memory promise.

The retained base has approximately537Mparameters and10Bprocessed positions. Completed SFT used80natural sessions, with74.77%of assistant target mass from that family, but no enabled/no-call turns. Existing models show partial recall and unreliable corrections. These observations support a bounded fit/transfer experiment; they do not prove either that another small training run will succeed or that the foundation is incapable. Full RCA: ../ganesh-base-review-v1/REVIEW.md.

## 2. Current evidence and what it does NOT establish

| Item | Fresh result | Limit |
|---|---|---|
| Repository cleanup | 840,464,436bytes removed;31disposable/superseded paths;278,322,901byte replacement runtime built | No weights, frozen inputs or evidence deleted; cleanup.json records exact files |
| Targeted checks | 171tests pass, including28offline recovery-gate tests | Synthetic control-flow/receipt checks, not CUDA/GCS or provider qualification |
| Frozen files | All41hash-match | No release content inspected |
| Local models | base10B, SFT50, defaultSFT194 payloads validated | Not acceptance of their conversation quality; other selected weights retained |
| Current runtime |150members readback-verified;27module closure | Capture plus generic checkpoint probe runtime; not an integrated new hands-off controller |
| Actual tokenizer/data | Capture2-update and frozen64-update validate-only checks pass | No optimizer/training run |
| GCP access | Read-only inventory failed reauthentication | Last successful cleanup inventory had zero VMs/disks; no fresh zero-resource claim |
| HTTP |8765has no listener | Existing local CLI weights retained |

The new cloud_training/nano_recovery_gate.py checks local evidence/authorization, fixed lease and stage prerequisites and refuses the actual unapproved request. It has no cloud or training executor. Old launchers do not use it; they remain closed historical tools. A passing synthetic receipt test does not establish integration, authenticity of a human claim, or a safe launcher. Real evidence collectors must bind their source artifacts and produce receipts; booleans are not substituted for GPU proof.

## 3. Launch blockers: finish these in order

1. **Hands-off integration:** a new controller must exclusively invoke the new campaign worker through the checks. Never reuse expired launch-request.json, budget or retry state. Wire actual generation jobs and full per-turn review into stage transitions. A saved checkpoint is not a conversation check: --fit-eval-steps only pins/evaluates loss at milestones.
2. **Lifecycle qualification:** prove provider STOP before allowing fit/production. A controlled stop/restart of the same VM is permitted within the original absolute lease; do not reset it. If literal zero interruption prevents testing this, HOLD rather than silently substituting final shutdown as prior qualification.
3. **Approval-time facts:** refresh GCP auth; fresh inventory, image/version, quota, region price, service-account/backup/controller access, input GCS readbacks and explicit finite cap/lease. Read-only failure is recorded in cloud-access.json. Never print tokens or reset credentials automatically.
4. **Broad curriculum readiness:** do not include a production pilot in launch authorization until its new manifest, complete review/splits and executable quality contract exist. They do not exist yet. Existing frozen fit is ready as data; identity/source candidates are unadmitted.
5. **Independent release review:** nominate a distinct semantic reviewer/process with no training-feedback use of final suite outputs. No such review has been completed. Same-agent re-reading is useful adversarial review, not independent acceptance.

These are real blockers. Local preparation can continue without spending. Authentication, user budget approval and GPU evidence cannot be manufactured locally. Do not request a larger budget to conceal incomplete integration or data.

## 4. The next cloud experiment

One on-demand L4 g2-standard-8. One campaign ID, one VM, one writer. No Spot, automatic restart, automatic machine upgrade, parallel allocations or background retry campaign. Native2K, fixed tokenizer/base/runtime hashes.

**Qualification phase:** limited real-shape capture/replay, matching2vs1+1observations, actual signal rollback/resume, corrupt-upload rejection and GCS restoration, independent provider STOP. Capture actual fused Muon inputs once at absolute update1 on the relevant branches, using the existing2GiBper-capture bound. Preserve moments, order, numerical settings and exact comparisons. A mismatch ends qualification and produces evidence; it is not permission for fit. No tolerance change or optimizer reset after seeing a failure.

**Frozen fit phase, only if qualification passes:** existing24sessions/72turns,64epochs AND64updates maximum, LR multiplier0.25, batch8192positions, microbatch1, packingbuffer1, seed103, native2K. Full64epoch schedule is96updates; cap64wins. Regression guards remain5%relative tolerance/patience2 with persistent state. Save0/16/32/64when reached and best/last. Do not change the frozen contract to make a result pass.

**Explicit generation/review phase:** invoke a generation runner for the actual trained checkpoint hashes, preserving production framing, greedy decoding,128token reply budget, actual assistant histories and raw frame records. Run the entire72-turn fit suite at no more than six distinct retained checkpoints; run36-turn development at no more than three predefined candidates. Blocked turns remain in denominators. Review every turn; no automatic success from loss, valid JSON, identity strings or calculator answers. The new nano_fit_probe.py accepts explicit checkpoint/suite hashes, enforces fit/development scope and a bounded subprocess, and preserves raw/blocked outputs. Its three-turn MPS integration smoke completed; model result was one invalid frame plus two blocked follow-ups, not a quality pass. Automatic milestone scheduling and semantic-review transitions still need controller integration.

Fit GO requires >=23/24complete training sessions, zero invalid/forbidden actions and complete semantic review under the existing scorer. If not achieved, stop expansion. This is a failure under the tested recipe, not proof that the architecture cannot learn. If achieved, report disjoint transfer separately; no release or broader training automatically follows.

## 5. Measurable workload and cost decision

Actual frozen diagnostic workload from local-results.json:

- <=64updates =524,288input positions; assistant targets and replay exposures reported separately.
- <=432fit turns plus108development turns =540turns. Broker allows up to3model actions per turn: <=1,620model calls.
- At128tokens per action, <=207,360generated tokens, excluding separately bounded qualification controls. Invalid/blocked calls do not justify extra retries.
- Retain at most six fit checkpoint bundles plus necessary qualification states/captures. Before provisioning enumerate actual bytes, scratch peak and GCS transfer/readback bytes. Keep100GiBdisk only if that peak plus explicit headroom fits; do not auto-expand.

Required timing equation:

T = setup + qualification + scheduled_updates × measured_update_seconds + maximum_generation_tokens / measured_decode_tokens_per_second + measured_checkpoint/upload/readback_time + review/control_time + shutdown_reserve.

Measure on the chosen L4 with the actual checkpoint and framing; use conservative observed values, not the historical0.57second warm update. Total qualification work itself is capped independently; if learning no longer fits, save/stop without starting it. Review can finish locally after cloud shutdown; a GPU must not sit idle waiting for manual assessment.

Reference rate previously checked17November: $0.853624312/hour for listed L4 VM; verify exact selected region/account SKU at approval. Formula: approved cap >=1.25×rate×fixed_lease_hours + itemized incremental disk/GCS/transfer/reserve.10hours imply$10.67margin-adjusted compute BEFORE other costs;40hours imply$42.68before other costs. The old$15/$50envelopes are illustrative, not measured completion quotes. Source: https://cloud.google.com/products/compute/pricing/accelerator-optimized . Existing storage, tax/FX and unrelated project costs must be distinguished from incremental campaign spending.

Do not promise a full recovery for$50. First supply the workload-derived lease and bill of materials. User approves that finite proposal. Price/authorization expiry, resource creation/start time and fixed provider deadline are recorded before any billable request. No spare-cap reuse or extension without new authorization.

## 6. A later production curriculum, conditional on fit evidence

Prepare locally before authorizing its cloud stage. Approximately2,000training sessions is a design envelope, not a quota or already existing data. Prefer fewer fully reviewed diverse examples over filling a count. Sources: traceable OpenAssistant TRAIN trajectories, reviewed external synthetic Smol-SmolTalk, and Codex-generated missing scenarios. Existing organic correction/memory discovery has low yield; do not mislabel synthetic content organic or assume unreviewed source quality.

Mix hypotheses by assistant target mass:30%ordinary English,25%instructions,25%state/corrections, up to5%identity/controls,15%tool routing/regression. Identity is a ceiling, not repetition quota. Report actual policy/source/length mass and packing exposure. All three policy modes are mandatory in production. Neither tiny-fit success nor these percentages prove the mixture optimal.

Split by whole source/scenario/template group before related generation; review all assistant turns, replay every tool result, check state trajectories and counterfactual pairs, actual tokenizer/masks/end-marker coverage, deduplicate and screen against historical exposed tests. Frozen corrective-v1 and24-session fit remain unchanged. Keep full provenance/licensing/transformation receipts. Positive tool lessons are in production, not the isolated fit diagnostic.

Production starts from immutable base10B with original optimizer state, not fit-memorized weights. One separately admitted pilot only, <=3epochs AND1,024updates, fixed recipe before launch and development regression stops. No third identity pilot: identity is integrated into this version. No automatic LR/epoch/optimizer change. If the work cannot fit its separately approved envelope, stop; do not truncate acceptance testing.

## 7. Selection and final acceptance

New final suite, locked before production training:200scenario-disjoint sessions with50ordinary/instruction,40recall(20short/20near-limit),40correction(20short/20near-limit),20identity,20unrelated identity-leakage controls,30tool-routing(10each policy mode). Existing protected tool checks are additional and unchanged. These are proposed allocations; they are not a claim that the suite exists. Review ownership, actual turn counts and hashes must be settled before launch.

Proposed conjunctive gates: >=90%successful everyday turns, >=85%complete everyday sessions, >=90%recall and correction designated turns separately in each length stratum, >=98%valid terminated frames, all designated identity/control turns correct, zero forbidden/malformed tool actions and protected tool gates passing. Small category counts imply wide uncertainty; report exact counts and intervals, not universal reliability. Gold-history probes are diagnostic only and never substitute for generated histories.

Select one candidate on development: hard regression/tool gates first, maximize fully successful English sessions, tie-break correction score then earlier update. Consume final suite once. No second-checkpoint shopping, no answer resampling until good. Outcomes: pass, semantic fail, invalid/truncated, forbidden action, blocked, harness error. No outcome disappears; harness errors make the affected evaluation invalid and require documented same-candidate repair, not model tuning. Independent semantic review and local MPS qualification remain necessary before release/default change.

## 8. Shutdown, recovery and reporting

Use absolute provider STOP, earlier guest deadline and separately supervised controller; preserve non-auto-delete disk. Prove lease survival across controller restart/local sleep; controller and worker sharing a failed token are not independent recovery. Upload/readback milestones while running. Before normal shutdown join writers, verify required bundle payloads, restore/load selected artifact in fresh process, back up raw outputs/config/tokenizer/source/data manifests and confirm stopped state. Backup failure never extends compute indefinitely: STOP preserves disk and sole copies; report recovery/storage obligations immediately.

Keep the selected experimental model locally even if quality fails; retain current default. Do local MPS checks after cloud STOP when possible. No public HTTP unless requested. Updates every30minutes during execution, immediate alert on blocker/stop; report estimated and later settled costs separately. Do not describe idle review or checkpoint transfer as GPU training.

## 9. Approval contract and final status

A future approval must name scope (qualification-only versus qualified fit; production separate unless all readiness completed), selected machine/region, fixed duration/cap, cost reserve, qualification sublimit, specific immutable inputs and allowed failure branches. The unselected no-resume alternative requires separate explicit approval and separate implemented contract; it terminates after diagnostic evidence and cannot promote a model.

Current artifacts: cleanup.json; local-results.json; tests.log; cloud-access.json; proposed-request.json; gate-result.json; ADVERSARIAL_REVIEW.md; receipt.json. The actual gate result is HOLD. Nothing in this plan marks missing launcher integration, data, independent review or GPU evidence as passed. This is the honest launch decision after feedback consolidation, cleanup and another adverse review.
