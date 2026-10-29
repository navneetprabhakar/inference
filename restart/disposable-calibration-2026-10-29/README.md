# Disposable numerical and resume calibration — 29 October 2026

**PASS. Exactly 12 approved optimizer applications completed; retained training remains unstarted.** This resolves the short-run optimizer and actual post-update resume gate for the tested runner configuration. It is not a capability result, learning-rate selection or authorization for the four-arm screen.

[Result](result.json) · [Audit](audit.json) · [Frozen execution script](calibrate.py)

## Execution and evidence

For replay coefficients 0 and 0.5, compared a three-update continuous trajectory with an independently initialized trajectory interrupted after one update and resumed in a new process for two more. All used the same original foundation, diverse-curriculum batches 0–2, seed, fresh optimizer and engineering learning rate 2e-5. No source checkpoint, historical runner, curriculum or threshold was edited.

Both comparisons matched **bit for bit** on final parameters, complete optimizer state, RNG state and the next batch's full logits/argmax predictions. Per-step losses and gradient norms also matched. Reload exercised the real serialized checkpoint in a different process, not an in-memory copy or fake backend.

Each of the 12 optimizer applications was checked against independent NumPy Adam equations using the actual clipped gradients. Declared tolerance was rtol 2e-5 / atol 2e-7, frozen before execution. Maximum absolute errors: parameters 2.98e-8, first moments 0, second moments 7.28e-12. Parameter changes and optimizer-step increments were verified; numerical checks fail closed. The reference verifies optimizer arithmetic on supplied gradients, not independent correctness of the entire model backward implementation.

Resource use: **12 updates, 29,792 input positions, 628 assistant/EOS target exposures, 12,288 narrative targets, 14.33 active-model seconds**. All consumed one durable calibration ledger under the approved 12-update / 10-minute / 2M-position envelope. An attempted reservation for update 13 was rejected before work, with no extra charge or optimizer application.

## Reassessment before retained training

- **Resolved:** finite short-run updates, optimizer arithmetic, real checkpoint reload, state/RNG equivalence, prediction equivalence and enforcement of the 12-update ceiling.
- **Not established:** a suitable common training LR, long-run stability, completion time for the full screen, instruction transfer or acceptable conversation. Three updates cannot answer those questions.
- **Preservation remains a policy issue:** the foundation's behavioral baseline is 0/80, so the five-point behavior-regression gate is inconclusive. Native narrative NLL is measurable but does not certify conversation preservation. Before retained training, explicitly classify the screen as acquisition-versus-native-narrative-retention research, or establish a meaningful behavior baseline. Do not switch starting checkpoints silently.

Next proposed execution is the already specified training-only LR/feasibility calibration, capped at 600 additional disposable updates across three candidate learning rates and two replay objectives. Select one common LR from training-only finite/stability/loss evidence and reserve enough budget for all four arms and evaluation. It requires separate approval and must not automatically launch retained training afterward.

These 12 updates consume the numerical-check allowance within the proposed 4,612-update study envelope; **4,600 remain if that envelope is later approved unchanged**. The current ledger has a 12-update hard cap and must remain closed. A future aggregate study ledger must import this audited charge and active time explicitly; copying the file and changing its stored limits would violate the runner's policy lock. Retained-launch wiring must use that reconciled ledger, not assume a separately capped calibration database can be reused directly.

All four calibrated child checkpoints are disposable evidence only, kept locally and excluded from Git. None is promoted or designated as a source for retained training. A retained arm must start fresh from the frozen original source. Original verification ledgers and previous exhausted training ledgers remain unchanged.
