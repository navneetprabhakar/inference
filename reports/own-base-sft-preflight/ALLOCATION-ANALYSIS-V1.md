# Prospective bounded SFT allocation

CPU-only analysis through the actual admitted `Sources`, deterministic `updates`, and `work_for` helpers; no model, GPU, SFT activation or runtime edits. Exact source costs and worst 250-update replay windows are in `allocation-analysis-v1.json`. Counts below include every prescribed full development evaluation, but exclude checkpoint I/O and replayed attempts.

| Allocation (chat / primary tool / extension passes) | Updates | Training rows | Assistant targets | Input = padded positions, including evaluation | Attention cells, including evaluation | Evaluation targets |
|---|---:|---:|---:|---:|---:|---:|
| 1 / 1 / 1 | 4,565 | 36,511 | 3,939,349 | 21,727,764 | 11,713,257,860 | 502,440 |
| 1 / 3 / 3 | 6,423 | 51,369 | 4,402,347 | 28,306,530 | 14,378,530,650 | 669,920 |

Selected next diagnostic: **1 / 1 / 1**, using the measured forecast and exact activation in `reports/own-base-sft-diagnostic-v1/`. This tests the existing teaching interface without assuming repeated templates improve behavior. The1/3/3alternative would raise tool assistant targets from231,499(5.9%)to694,497(15.8%), at about30%more input positions and23%more attention cells including this comparison’s proposed evaluations. It explicitly repeats existing examples, adds no diversity, and may memorize templates; defer that intervention until actual development behavior warrants it. Neither allocation establishes that SFT can repair the weak base.

Comparison-only cadence (the final one-pass activation instead uses100-update checkpoints): checkpoint every **250 updates**; full teacher-forced evaluation at step0, every1,000 updates, and endpoint. Use all511 chat,583 primary-tool and24 extension development rows without relabeling exposed development as held-out. The exact formula yields6 evaluation events for1/1/1 and8 for1/3/3. One full event consumes83,740 evaluation targets,508,647 input/padded positions and250,503,261 attention cells. Source-specific CE is diagnostic only; loss cannot establish usable behavior.

For1/3/3, per-source nominal costs including8 evaluations are:

| Source | Assistant targets | Input/padded | Attention cells | Evaluation targets |
|---|---:|---:|---:|---:|
| Chat | 3,707,850 | 18,104,442 | 10,377,953,496 | 513,824 |
| Primary tool | 676,278 | 9,903,774 | 3,798,198,300 | 142,672 |
| Four-call extension | 18,219 | 298,314 | 202,378,854 | 13,424 |

Work ceilings must exceed nominal if recovery is intended. A conservative explicit allowance for each authorized failed attempt is the per-source/component maximum250-update window in the JSON **plus one complete evaluation event**; sum source bounds for the global limit. These independent maxima are conservative and need not occur in the same window. The trainer charges attempted work before execution and never refunds it; evaluation restarts can recharge already evaluated rows. Successful lease checkpoints do not themselves require replay headroom. Do not use an arbitrary assistant-target-only percentage while ignoring inputs, padded positions, attention cells or evaluation targets.

The current implementation saves initially, after each evaluation, periodically, and protects the endpoint. Under this cadence1/3/3 entails35 save calls (some share a cursor);1/1/1 entails26. Checkpoint I/O is not measured by hardware preflight. Root should include this cost, initialization/validation, sustained slowdown margin, explicit recovery allowance and lease cleanup margin when choosing time ceilings; adjust cadence prospectively if measured update time makes250 updates unreasonable. No time budget or learning rate is selected here before the hardware receipt.
