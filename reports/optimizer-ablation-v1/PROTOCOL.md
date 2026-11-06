# Own-base optimizer screen v1

**Prospective protocol approved for runtime freeze; code and verification identities must be pinned before execution.** This document does not start training. The existing foundation campaign and its frozen files remain unchanged.

## Question and common parent

The screen asks whether short second-moment memory or resetting optimizer history limits learning at the current 8,192-target update size. It does not establish conversational or tool capability. The student remains the 124,439,808-parameter model from our own verified random initialization; no pretrained weights, architecture changes, tokenizer changes or new data mixture enter this experiment.

Wait for `runs/own-base-foundation-01` to reach its full 99,999,744 committed-target endpoint and terminal `completed` state. Verify its frozen specification, ledger and protected endpoint checkpoint. Bind the checkpoint basename, SHA-256, bytes, campaign specification hash and ledger hash into all three arm specifications before their first update. Never choose an implicit `latest` checkpoint or launch from a partial/resource-stopped parent. If the parent does not reach the exact required endpoint, report the blocked dependency; do not silently substitute another checkpoint.

## Three arms

| Arm | Weights | AdamW moments and step counters | Beta2 |
|---|---|---|---:|
| `preserve-095` | Exact own foundation endpoint | Restore full parent state | 0.95 |
| `reset-095` | Same endpoint tensors | Fresh moments, step zero | 0.95 |
| `reset-scaled` | Same endpoint tensors | Fresh moments, step zero | 0.9991988633566534 |

Beta1 stays 0.9; epsilon 1e-8, matrix-only decay 0.1, global clipping 1, FP32 master parameters/moments and the existing verified BF16 autocast stay fixed. In the preserved arm, bias correction uses the restored per-parameter counters. In both reset arms it starts from zero. Every later lease restores the arm's own complete optimizer/RNG/cursor state.

The approximate token-horizon mapping is `0.95 ** (8192 / 524288) = 0.9991988633566534`; the screen freezes the computed beta2 at **0.9991988633566534**. It is a hypothesis about second-moment memory, not permission to copy large-batch learning rates or assert a universal scaling law. Comparing the two reset arms isolates beta2; comparing the two 0.95 arms tests optimizer-history reset.

## Common restart schedule

The parent endpoint learning rate is approximately **6e-6**, after its original decay. Each arm uses the same new one-million-target linear warm restart from **6e-6 to 6e-5**, then stays flat at 6e-5. There is no end decay in this short screen.

For arm-local committed targets `t` at the **start** of the optimizer update:

`lr(t) = 6e-6 + (6e-5 - 6e-6) * min(t / 1_000_000, 1)`.

Thus the first update uses exactly 6e-6. Replay resumes the saved committed schedule position while still consuming attempted-token budget. The control is **preserved moments with a common LR restart**, not uninterrupted continuation of the previous schedule. Scheduler position and AdamW per-parameter step are distinct counters.

## Data and limits

Use the existing pinned corpus and the same next previously unused stream in all arms, beginning at target offset **99,999,744**. Context 512, microbatch 2, accumulation 8, update size 8,192, seed 20261106 and exact data order are identical. Preserve the original split, custody restrictions and all validation/diagnostic hashes. Assert the shifted input and target span fit the corpus; never cycle or fall back to another shard. A boundary input token may overlap the last trained token, but the new targets must not repeat prior targets.

Each nominal 20M arm is capped at **19,996,672 attempted targets = 2,441 updates**, ten cumulative active hours and four-hour execution leases. The three arms plan **59,990,016 attempts**, within the strict **60M aggregate ceiling**, **30 active hours** and **seven calendar days** from first experiment launch. Floor rounding avoids exceeding 60M when summed. Model/optimizer initialization, evaluation and checkpointing inside `Campaign` count against active training budgets. Read-only source/parent hash preflight is outside the active training timer and bounded by the supervisor worker watchdog and experiment calendar deadline. Interrupted/replayed work consumes budget again. Committed targets may therefore be lower than attempts; never extend caps to repair a comparison.

Run sequentially in order `preserve-095`, `reset-095`, `reset-scaled`, with one GPU lock holder. Parallel CPU preparation is allowed; GPU arms never overlap. The supervisor pins immutable templates and permits only terminal parent-receipt binding before freezing each executable arm specification. A changed template, runtime identity, checksum or STOP ends/pauses work under the established policy.

## Measurements and decisions

Evaluate baseline, nominal 1M, 5M, 10M, 15M and the actual endpoint. Scheduled target counts are **0; 1,007,616; 5,005,312; 10,002,432; 15,007,744; 19,996,672**. Reuse the existing 256 fixed within-document 512-target validation windows and FP32 mean CE; 32 strict counterfactual pairs; and 32 fixed raw greedy 48-token continuations. Both members of each context pair must strictly favor the correct whole suffix by mean log probability; ties fail. No decoding penalties, host repair, altered prompts or idealized tool traces are introduced. Baseline weights must match the common parent exactly.

Compare loss on matched examples and matched committed-token positions. All three arms must finish as terminal `completed` with exactly **19,996,672 committed targets** and complete measurements before selecting an alternative. A reset arm qualifies only if, at **each** of the three late measurements (10,002,432; 15,007,744; 19,996,672 targets), its paired mean CE gain over the preserved-moments control is **at least 0.02 nats AND strictly greater than two descriptive paired standard errors**, and its strict context-pair count is not lower than control. Its endpoint repetition-flag count must also be no higher than control.

For that endpoint heuristic, tokenize **generated continuation text only**, excluding the provided prefix, with Python Unicode `re.findall(r'\w+|[^\w\s]', text.casefold())`. Flag a continuation if any contiguous four-token tuple occurs **at least three times**. Punctuation is included. This deterministic heuristic is not a human fluency judgment; retain all 32 raw outputs so a favorable flag count cannot hide nonsensical text.

These are prospective engineering screening rules, not literature-derived guarantees or formal significance: documents can share domains, measurements recur, and this is one seed on one stream. Report every arm's curve, raw outputs, context results and paired loss differences. Compare the two reset arms descriptively to isolate the beta2 change; that secondary comparison does not replace the declared control selection rule.

If several reset arms qualify, prefer the lowest endpoint mean CE; exact ties use fixed order `reset-095`, then `reset-scaled`. If none qualifies, keep `preserve-095` as the reference. Missing exact endpoints, weak/mixed gains or diagnostic tradeoffs yield no qualifying alternative. A loss-only gain must be labeled as such. There is no automatic extension, second sweep, mixture change, SFT or promotion. Selection is **optimizer loss selection only**, never a base-quality, conversation or tool-capability pass. Sealed conversation acceptance cases stay closed.

## Recovery, resources and disk

Keep existing thermal, RSS, swap, free-disk and readable-telemetry protections. Numerical nonfinites stop immediately. Two consecutive material validation regressions beyond `max(0.20 nats, 5 paired descriptive SE)` versus that arm's best trigger the established deterministic reproducibility check and stop if confirmed. STOP, exhausted budgets, identity mismatch and corrupted state are never overridden.

For each arm retain **only the last two full checkpoints, with the endpoint counted in those two**, and protect **only its endpoint**. The initial baseline checkpoint is rolling, not additionally protected: the common foundation parent remains protected, and the exact optimizer initialization is specified and verified. Preserve all metrics/raw outputs. Do not protect intermediate or best-loss checkpoints in addition to the rolling pair. Never delete an original protected foundation artifact.

Before launching the experiment, forecast storage for every remaining arm's two full checkpoints, one atomic temporary checkpoint, and data/log headroom from measured parent checkpoint size; require that forecast **in addition to the 20GiB free-disk floor**. Recheck before each arm and save. A current approximately 1.49GB full checkpoint implies roughly 8.4GiB for six retained arm checkpoints plus 1.4GiB temporary space, before headroom. These are estimates, not a disk waiver. Pause/report if exact forecast does not fit; do not rely on deleting protected baselines to make space.

CPU verification before freeze must cover parameter/moment/step initialization, common scheduler boundaries, cursor/target identity, full-state interrupted resume and aggregate supervisor budgets. Root has approved this protocol; implementation verification and runtime identities must still be pinned before freezing launch specifications. The experiment may select a better optimizer setting; it cannot certify a useful assistant.
