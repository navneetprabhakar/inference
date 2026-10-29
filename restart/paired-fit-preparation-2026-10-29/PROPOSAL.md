# Controlled small-fit proposal — not authorized to train

## Decision and review

Run a bounded **ordering feasibility experiment**, not another retained research screen. The independent [semantic review](SEMANTIC_REVIEW.md) examines the original packet/corpus and successor repairs. The frozen parent curriculum remains unchanged. Eight affected presentations in the selected subset replace references to two objects with supplied-record wording; references and target counts are identical. Other defects in the full parent corpus remain unrepaired and that corpus must not be launched wholesale.

## Matched design

| Setting | Fixed for both arms |
|---|---|
| Initialization | Own foundation `restart/foundation-resolution-v1/B/checkpoint.pt`, fresh identical optimizer/RNG; not the best screened endpoint |
| Source SHA256 | bf45241501cee600bd618677dc1a3ae666e6f50d9c628e29e7326ee9c87d338d |
| Optimizer | Existing repaired AdamW, LR0.0005, betas0.9/0.95, eps1e-8, zero weight decay, existing clipping and BF16 compute/FP32 masters |
| Loss | Mean of eight per-conversation assistant/EOS means; narrative replay coefficient0.5 |
| Fit data | 32 pairs per task ×8 tasks =256 pairs/512 conversations; two presentation views,1,024 presentation records |
| Schedule | Two epochs, each with view0 then view1;256 updates/arm,8 conversations/update; every presentation appears twice |
| Replay | Same existing eight-block replay batch at each update, same256 frozen index entries |
| Response contract | Native serialization, greedy normal EOS,32-token cap,256-token context, generated history |

The paired arm places before/after batches consecutively. The control permutes the **same complete batches** within each64-update epoch/view block. Batch composition, padding totals, task weighting, target exposure, replay-by-update and total updates match. This tests local adjacency **and systematic before→after order together**; it cannot isolate those effects. Shuffled batches may accidentally place partners adjacent. Pair-distance/side-order diagnostics must be reported. One initialization/order seed gives no reliable population effect size; no seed sweep or adaptive LR search is included.

Starting from the foundation tests whether these repaired examples can be acquired under the existing setup. It does not test whether continuing arm1 would repair its errors. LR5e-4 is a fixed hypothesis from prior training-only calibration; a failure cannot distinguish unsuitable LR from inadequate curriculum or capacity.

## Measurements, fixed before execution

Evaluate source once and each arm at update256 only. No intermediate generated evaluations, early checkpoint selection or development-driven tuning.

- Generate all1,024 fit presentations (1,408 turns) and128 prespecified development conversations (176 turns) at each of the three checkpoints. Development is every fourth index per family:16 per family, including8 familiar-name and8 new-component cases for name. It is a small synthetic probe, not acceptance or paired transfer evidence.
- Measure teacher-forced assistant loss by family over all fit presentations and native held-out narrative NLL at each checkpoint. Shared source measurements are reused, not rerun per arm. Use the existing512-block native validation set.
- Primary fit outcome: complete paired correctness—both conversations entirely correct—separately per task and view (32 pairs each). Also report each turn, whole state trajectories, changed-answer correctness and unchanged-answer errors. For clarification only the supplied-value second turn is expected to change. For state turns0,1,2 all change; other families turn0 changes. Termination failures count as failures.
- Proposed **fit gate**: at least29/32 complete pairs in every task/view, including name, state and missingness; no family hidden by a pooled average. This is an engineering threshold, not statistical certification. Report paired-minus-shuffled differences with raw denominators; a small difference is inconclusive.
- Report development by family, familiar/new name components, scope and representation. With16 cases/task, results are directional. Do not infer counterfactual transfer because development has no matched pairs.
- Report native NLL relative to source and historical screen. Predeclare a research viability guard of at most1.65×source NLL (approximately the prior best arm's degradation, rounded). This is a permissive research guard, **not acceptable preservation**; the behavior baseline floor remains unresolved. No model can be promoted by this experiment.

If neither arm passes fit, stop and inspect per-task loss and outputs; do not add updates. If both fit, adjacency is not shown necessary. If only paired fits, treat it as an ordering hypothesis requiring replication. If fit succeeds but transfer fails, the bottleneck remains generalization. Every outcome ends in reassessment, not automatic full training.

## Proposed hard budget

[budget.json](budget.json) is machine-readable and explicitly `authorized:false`.

- **512 new updates total:256 per arm.60 new active minutes.20,000,000 new input positions.** Stop at the first cap; no extensions, retries, additional seeds or calibration updates.
- Exactly24,808 assistant/EOS training targets and1,048,576 narrative training targets across both arms. Evaluated labels are forward-only and included in input-position accounting, not training-target counters.
- Worst-case counted work: approximately15.51M input positions, assuming32-token generation at every turn with worst-case prior generated lengths. Timing projection55.7 active minutes uses historical maximum per-forward latency, training p95, a120-second startup/checkpoint allowance and25% reserve. It is conservative but not guaranteed; the cap remains binding.
- Checkpoint at each endpoint only; at most2GiB new artifacts, keep completed work on a stop. No automatic resume; a partial arm is incomplete and unmatched, not a valid winner.
- Carry forward the retained-screen ledger **once** (already includes612 calibration updates), plus inference-diagnosis ledger once:4,612 updates,15,036,342 positions,19.7235 active minutes. Proposed aggregate caps:5,124 updates,35,036,342 positions,79.7235 active minutes. Older campaigns and engineering ledgers remain separately recorded; these are successor-study totals, not lifetime compute totals.
- Charge startup, all forwards/backwards, checkpoints and validations. Keep previous ledgers read-only. Before launch, verify ledger hashes/totals and import carry-forward once into a new ledger; reserve each operation before work. Timer overruns can occur only for an already-started atomic operation; no subsequent work may start after the cap.

## Readiness and launch boundary

Prepared deterministic schedules, repaired inputs, replay indices, source identity, input adapter and CPU checks. No model loaded or trained during preparation. This proposal contains no training launcher. After user approval of this exact budget, wire the verified adapter into the existing runner and bounded ledger, verify fresh initialization equality, source/manifest identity and baseline accounting, then execute. Do not silently restore old optimizer state or reuse the old1000-step Inputs class. Any change to these frozen data, budget, scorer or control requires an explicit versioned amendment before execution.
