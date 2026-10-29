# Training-runner readiness — 29 October 2026

**Runner components and zero-update verification are complete. Retained training is not ready to launch.** Actual optimizer-step correctness and post-update resume equivalence remain untested. More importantly, the selected foundation scores 0/80 on the proposed conversational preservation packet, so that packet cannot provide a meaningful no-regression gate for this source.

## Implemented

- [runner.py](runner.py): full-parameter MLX backend using the existing repaired embedding backward; BF16 compute with FP32 master parameters and fresh AdamW moments. Each of eight task rows is normalized by its own assistant-target count before averaging. Replay is an independently normalized loss with coefficient 0 or 0.5. Combined gradients are clipped to norm 1 before the optimizer application.
- [replay.json](replay.json): immutable historical native-token replay source and seeded 1,000-batch index order. The source has 400 batches of eight 257-token sequences; reuse is explicit, with two full shuffled passes and a partial third. Each replay arm consumes 2,048,000 narrative targets. Zero-replay arms skip narrative loading into the loss and consume zero narrative targets.
- Durable SQLite reservations precede work. Limits and update permissions persist across reopening; negative charges, budget resets and nested timers are rejected. Crashes retain reservations and conservatively charge elapsed active time. Checkpoints contain full parameters, optimizer state, RNG, schedule cursor, arm identity, manifest identity and ledger cursor. A checkpoint behind the ledger is rejected rather than silently replayed/refunded.
- [evaluate.py](evaluate.py): generated-history evaluation, unchanged structured scorer, per-task/per-cell counts, state-conversation completion, both-correct counterfactual pairs, and raw responses. Source/sentinel/endpoint hooks exist at 0/250/500/1,000. [preservation.py](preservation.py) extends those hooks with native held-out NLL and a floor-aware behavior decision. Use this extended evaluator for future execution.
- [config.json](config.json): proposed arm and optimizer configuration. CLI training remains deliberately disabled. The core runner takes an evaluator callback; [launch.py](launch.py) implements sequential four-arm orchestration with shared-baseline reuse, common-LR enforcement, approval/hash gates and the existing calibration ledger. No approved launch receipt exists; a callable runner is not authorization.

## Verification performed

| Check | Evidence |
|---|---|
|Both complete curricula and all scheduled batches|70,333 CPU assertions passed; shifted labels, masks, padding, task balance, replay/no-replay behavior|
|Synthetic lifecycle|1,000 fake-backend steps exercised callback schedule and checkpoint lifecycle; these are not model or optimizer steps|
|Durability and failure controls|Seven additional lifecycle checks passed: time/position caps, no resets, crash accounting, update denial, preservation-floor handling|
|Actual model forward|Canonical loss 8.884560; diverse loss 8.909765; paired replay loss identical at 1.353988|
|Cold state round-trip|Parameters unchanged and next loss exactly equal after serializing/restoring untouched optimizer and RNG state|
|Actual backward, no application|Two finite gradient evaluations were bitwise identical; norm 67.513046; no optimizer application|
|Native held-out validation|512 blocks / 131,072 targets; NLL 1.3430354334, reproducing the historical source baseline|
|Behavior acquisition baseline|0/80 scored turns, 0/64 complete conversations; all unmatched responses retained for inspection|

Total real verification: **255,560 charged input positions, 16.01 active-model seconds, two backward evaluations, zero optimizer applications**. The backward-only check exposed 106 assistant target positions, separately reported; it performed no training updates. The 300-second / 500,000-position verification envelope carried forward across forward, narrative and gradient checks without reset. Model parameter hashes remained unchanged. Raw results are in [forward-result.json](forward-result.json), [narrative-result.json](narrative-result.json), [gradient-result.json](gradient-result.json), [tests.json](tests.json) and [lifecycle-tests.json](lifecycle-tests.json).

Exact 257-token validation/replay block overlap is zero. This is not a document-level provenance/leakage audit. Replay and validation retain their historical native-corpus status; no raw quarantined corpus was admitted and no data were downloaded.

## Reassessment

The behavioral metric was labelled preservation prematurely. With a 0/80 source baseline, a five-point decline allowance is vacuous. `behavior_decision` now returns **INCONCLUSIVE_SOURCE_FLOOR**, never PASS, for a baseline below 50%. The 50% floor is an explicit diagnostic safeguard, not a validated universal threshold. Keep the 64 conversations as acquisition evidence. They have limited template diversity and primary-agent authorship, so do not call them independently validated natural behavior coverage.

Narrative NLL is a measurable preservation proxy for this foundation, but cannot certify conversation quality or replace missing behavior preservation. Record its trajectory and acquisition tradeoff. The historical +5% narrative line remains descriptive; it is not restored as an automatic stop for no-replay research arms. No candidate can meet the original behavioral preservation eligibility rule from this source packet; that eligibility decision must be revised explicitly before a retained experiment.

The measured repeated backward took approximately 0.16 seconds after compilation on one batch. This is not a reliable whole-study ETA: it excludes optimizer application, replay gradients, different shapes, full evaluation, checkpoint I/O and calibration. Do not approve a 90-minute run from this number alone.

## Next decision before retained training

A disposable **12-update numerical/resume calibration** is the smallest next execution step: for each replay coefficient, compare three continuous updates against an independently initialized three-update path interrupted and reloaded after update one. Same source, batches, LR and RNG; all 12 invocations charged, all outputs disposable. Verify actual parameter/moment/RNG equivalence, finite losses/gradients and identical next predictions. Proposed sub-cap: 10 active minutes, 2M positions, 10,000 assistant targets and 50,000 narrative targets; it counts within the previously proposed study budget, not on top of it. Stop on mismatch; do not continue to the four-arm screen automatically.

This requires explicit approval because the user requested reassessment before training and even disposable optimizer applications are training. It has not been run. A common-LR selection, full-run feasibility estimate and an explicit acquisition/preservation eligibility decision remain after numerical calibration. No retained model is promoted and no old training ledger is reopened.

## Limits of verification

Finite repeated gradients do not establish independent gradient parity. Cold-state reload and fake-backend resume do not establish post-update optimizer equivalence. A dirty-ledger resume intentionally refuses; automated recovery after a partially completed charged update/evaluation is not implemented. Recovery must preserve charges and use a new explicitly identified branch. Resource caps are checked between operations, not an operating-system preemption guarantee during a single kernel. Pickle checkpoints are local trusted artifacts only.
