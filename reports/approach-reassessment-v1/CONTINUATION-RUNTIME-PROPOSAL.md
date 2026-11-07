# Minimal own-base continuation runtime

Prospective CPU code assessment, 2026-11-08. Reads DECISION.md and the earlier post-optimizer PROPOSAL.md. No trainer edits, GPU activity, packing admission or activation. The user's new maximum is1B parameters;124M remains the existing control, not a commitment to final size.

## Concrete recommendation

Implement one new Torch continuation entrypoint, one narrow campaign-control variant, and CPU regression fixtures. Reuse the frozen GPT2/optimizer/checkpoint/resource primitives and existing selected-parent verifier. Do not build a general training framework or alter frozen files. Keep the old proposal's sound ancestry/resume/evaluation rules, but replace its60M target,50/50 mixture and30-hour defaults: DECISION.md supersedes those numbers and final source yield is not known.

The actual blocker is not merely a new corpus filename. `base_run_control.Campaign.__init__` caps campaigns at100M attempted targets,36active hours and7calendar days. `own_base_sft_control.SFTCampaign` inherits those caps. A hundreds-of-millions/billion-target experiment cannot use them unchanged. Four-hour leases do not expand cumulative entitlement; chaining unrelated100M runs to evade the chosen experiment budget would be misleading.

## Reuse map

| Existing interface | Reuse | Missing work |
|---|---|---|
| `own_base_sft_train.verified_parent(spec)` |Recomputes frozen optimizer comparison; verifies all three arm receipts under locks, selected endpoint, full payload and own-random ancestry; returns payload/name/receipt.|Use only parent-related spec fields and pinned imports. Do not invoke SFT training, which resets optimizer. Verifier currently assumes124M Config and200M cap; that is appropriate for this selected124M parent, not a future larger scratch branch.|
| `train.optimizer_for(model)` and `optimizer_ablation_train.validate_optimizer` |Construct identical parameter groups; load full selected optimizer state; validate every step/beta/group.|No `initialize_optimizer` call. New path restores parent CPU/MPS RNG after constructing/loading objects and moves optimizer moments to the intended device. Verify initial exact moments/steps with tiny fixtures.|
| `gpt2.GPT2`, `next_token_loss`, `base_train.precision` |Frozen architecture, shifted all-token causal loss, existing BF16 autocast/FP32 master state; one clip after accumulation.|Explicit512or1024 layout and preflight receipt; no runtime fallback. Every update's true target denominator must equal its sum of row lengths.|
| `checkpoint` save/load/protect/locks |Hash-verified publication and accepted pointers; rolling retention.|Pin new identity, source schedule/cursors and evaluation progress in saved state. Keep existing protected parent; no permissive latest selection.|
| `base_run_control.Campaign` |Reservation-before-work, no attempt refunds on rollback, leases, signed ledger, recovery and accepted checkpoint transaction pattern.|New separately named copy with prospective finite caps and new evaluation/source work accounting. Preserve original unchanged; do not subclass and mutate its immutable spec after construction.|
| `guards.Guard`, inherited STOP checks |GPU lock, resource/thermal/AC guards and positive elapsed limit.|New wrapper pins global/run/ancestor STOPs, measured disk+checkpoint margin and watchdog. Existing supervisor patterns can be copied narrowly; no unattended infinite restart policy.|
| `base_train.compare_losses`, `language_diagnostics` |Fixed paired deltas and unchanged strict context/raw generation series.|New source-stratified, variable-length document evaluator; transactionally retain matching document IDs, full raw generations and source-specific regression history.|

## Small implementation surface

1. `own_base_language_continue.py`: spec validation, selected-parent load, `MixedStreams`, immutable schedule/cursor reconstruction, variable-length evaluator, update/save/resume loop. Source files are read-only memory maps. No downloads or policy decisions inside trainer.
2. `own_base_language_control.py`: narrowly derived Campaign implementation with explicit reviewed maximums, an immutable experiment-level train/attempt/evaluation budget and per-source counters. Retain checkpoint semantics and guard interface. Do not introduce a generic job engine. Budget inputs have no permissive defaults; active/calendar caps must be sized from measured throughput and include evaluation/save/replay headroom.
3. `verify_own_base_language_continue.py` plus control tests: tiny CPU fixtures for the failure modes below. A separate metadata-only freezer can follow accepted data receipts; it must not infer or fill unavailable source quotas.

A small new supervisor is needed only if existing generic watchdog/ticket utilities cannot execute this entrypoint while preserving the new cumulative deadline. Reuse `own_base_dev_run` watchdog/ticket primitives rather than import its task-specific evaluation policy. Exact supervisor choice is a code-review decision, not a new framework project.

## Frozen run contract

- Bind selected `preserve-095` receipt from completed comparison (`no_candidate_qualified=true`), original experiment/report/runtime pins and protected foundation ancestry. Selected checkpoint has2,441 arm updates after12,207 foundation optimizer updates: initial continuation optimizer step14,648. Arm trained targets19,996,672 and foundation99,999,744 are historical exposures; new committed/attempted counters start at zero. Earlier lineage provenance remains intact; do not equate a new source offset with historical exposure.
- On initial load, preserve all148 model tensors, AdamW moments, steps, groups/betas/epsilon/decay and RNG. A new LR schedule is separately declared; constant6e-5 is the previous proposal, not an established optimum for a longer horizon. Report any scheduled LR change without calling it exact optimizer-policy preservation.
- On resume, load only the ledger-accepted checkpoint. Validate optimizer step=`14,648+new_committed_updates`, committed targets from layout, per-lane `(pass,offset)` from deterministic schedule, and evaluation/diagnostic state. Keep attempted reservations charged even when committed state rolls back. Save a rolling step-zero checkpoint before evaluation or training.
- Bind each admitted source's candidate/quality/custody/independent-verification/packed-stream/index receipts, tokenizer and EOT convention. Distinct narrative, expository and broad-English lanes remain separately traceable. Intake completion is not admission; unspecified broad-English yield is not a license for fallback or refill.
- Layout512 uses16rows of512targets/update, arranged as B2×accum8. Layout1024 uses8rows of1024targets/update, B1×accum8. Both have8,192targets/update. Keep each row within one source, though it may cross that source's document EOTs. Use a short frozen cycle of source row assignments to realize actual admitted proportions; compute its full per-source target counts exactly. Changing proportions or length requires a new spec.
- Adjacent packed rows may share one boundary input token; loss target positions must not overlap within a pass. Each lane needs its assigned target count plus one boundary token. No wraparound. For a substantial run exceeding unique source yield, repetition must be explicit in the new policy: finite passes, fixed per-pass ordering/offsets and per-source unique-versus-repeated exposure accounting. Otherwise fail admission. Repeated copies are not fresh billions of tokens, and the old no-repeat policy cannot silently disappear.
- Training committed goal and strict attempted ceiling are distinct. Replay reserve is explicit. If attempts are exhausted before the intended goal, mark budget-exhausted/incomplete, preserve evidence and stop; do not label the intended exposure complete. Checkpoint cadence, lease-save margin and total calendar/active limits follow measured checkpoint/update times.

## Variable-length validation without padded-target errors

For each source freeze one window per held-out document, with32–512targets and short/long strata, rather than discard short documents. Load exactly `target_length+1` tokens and run one document at a time in FP32 initially; this needs no padding and is the simplest correct implementation. Record summed NLL, actual target count and mean CE for every stable document ID. Aggregate document-mean and token-weighted CE separately, plus length strata and matched-document differences. Require identical ID/order/length on resume and comparisons. Independent validation token budgets include repeats after interruption.

Keep the original256web windows and context-pair/raw-generation checks as an unchanged transfer series. This source validation alone does not measure1024-position learning: a1024run additionally needs separately frozen upper-position/context diagnostics under its own accounting. Short documents packed at high positions do not prove long conversation competence. Each series retains its own best reference and two-consecutive-material-regression counter; save the new evaluation record and its cursor at an accepted checkpoint boundary to prevent restart ambiguity.

## Essential CPU evidence before activation

- Selected-parent verification refusal for changed comparison/receipt/ancestry; fixture equality of all moments/steps/RNG after initial load. Never load the real parent just to run preparation tests.
- Both layouts: exact8,192targets, source quota arithmetic, shifted boundaries/EOT handling, no off-by-one repeats, exhaustion refusal and explicit pass transitions.
- Uninterrupted versus save/resume equality of parameters, optimizer state, source cursors and next batches on tiny deterministic fixtures; interrupted reservation remains charged and cannot buy extra updates.
- Variable-length32/127/128/512-target examples agree with direct CE; source/document/token averages differ as expected; invalid window crossing or changed IDs rejected.
- Evaluation interruption, save-publication failure, tampered receipts, exhausted lease/calendar/attempt limits, STOP and checkpoint margin all stop without silently altering the spec. Reuse existing tests where behavior is identical and add only new-contract cases.

## Larger-model branch under the new1B ceiling

Do not enlarge124M in place or claim transferred weights/moments remain a full-state continuation. A350M/500M/1B candidate is a separately initialized own-random architecture and new tokenizer/shape/budget identity unless an explicit architecture-transfer experiment is independently approved. The selected124Mparent remains the control.

First record analytical lower bounds, then consider a separately bounded feasibility measurement after the current124Mbenchmark. FP32 parameters+gradients+two Adam moments alone require roughly16bytes/parameter:350M→5.6GB,500M→8GB,1B→16GB (decimal), before activations, logits, temporaries, framework cache, CPU checkpoint copies and OS. Weight+moment checkpoint payloads are roughly12bytes/parameter:4.2/6/12GB. These are lower bounds, not claims of fit;1B is already incompatible with the current benchmark12GiB active-allocation cap under this optimizer layout, so it cannot be smuggled into the existing envelope.

For any size candidate, freeze exact architecture/count and512/1024 workload; measure full training update speed, peak active/cache/driver/RSS, thermal behavior and atomic checkpoint time—not inference or parameter-linear speed extrapolation. Derive tokens attainable in the user's finite local time budget and compare that exposure tradeoff before choosing size. No new larger-model GPU trial, precision downgrade, offload or optimizer-state compression is authorized by this proposal.

## Work next

Root can authorize the small CPU runtime/control implementation while intake and the current benchmark proceed. Final training activation waits for admitted stream yield/repetition policy, selected architecture decision, measured throughput and memory, explicit exposure/attempt/evaluation ceilings, CPU resume evidence and pinned code/spec. The minimal124Mcontinuation can be prepared now without predetermining whether it is the final trained model.
