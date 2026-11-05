# Varied offline tool teaching

**The training pool contains 5,465 distinct synthetic histories across 129 authored form/domain families at seed 1459.** Every history uses the same role/text/call/result interface and model-visible tool projection as the working chat. Assistant proposals are training targets. No student output or learned performance was measured here.

| Measurement | Training | Internal transfer |
|---|---:|---:|
| Histories | 5,465 | 439 |
| Form/domain families | 129 | 34 |
| Broker calls | 6,101 | 488 |
| Multi-user-turn histories | 2,122 | 182 |
| Multi-call histories | 700 | 61 |
| Histories with no call at all | 64 | 12 |
| Calls with fractional inputs | 1,704 | 220 |
| Calls with negative inputs | 1,093 | 68 |
| Distinct requests observed with two different outcomes | 62 | 10 |
| Longest input in the working serializer | 187 | 182 |

## Coverage

- Arithmetic spans direct operations, signed differences, change relative to a baseline, net versus gross amounts, division into shares, price per unit, area, rates, packing counts and multiplicative scale. Fixed verbal roles bind the numerator and denominator or starting value and deduction. Some requests present those roles in reverse order. Commutative argument orders are semantically equivalent. Integer, decimal, negative and spelled-out inputs are explicitly present.
- Conversion cases cover mass, volume, length and time in both directions. Some name the desired output unit first. Others require reading or recalling the original unit, computing a second step from the converted value or retaining the sign of an offset.
- The remaining cases include missing divisors, missing starting amounts, missing source/target units, explicit prohibitions, later permission grants, post-call no-call recall, corrected operands, within-turn two-call chains, transient failures followed by an explicit retry or recall, division by zero, and paired reported outcomes.
- Every call passes through `FixtureSession.propose`. The next user turn and subsequent proposal use the actual observation. Counterfactual outcomes are host-bound synthetic fixtures, labeled in the auditor's trace. The projected model-visible result matches serving. The teacher never replaces an observed failure with the ideal answer. The training set contains 5,549 ordinary observations and 552 recorded fixture observations. Counterfactual numerical values deliberately differ from ordinary adapter arithmetic. They teach reporting an identified offline fixture's reading.

## Reproduction and separation

`tool_teaching_varied.examples(seed)` returns only the train histories. `records(seed)` additionally exposes each training form, host policy and time-independent adapter records. `internal_records(seed)` uses a different form inventory, a different numerical stream, and removes overlap in first proposed tool/argument signatures against the corresponding training seed. It can be used for a diagnostic after locking training choices. The forms are independent within this supplement; they are not a sealed release benchmark and were not checked against other curricula or protected case families by the author.

`.venv/bin/python reports/varied-tool-teaching/verify.py` replays every policy and call, compares actual tool frames and stored observations, checks call boundaries and permission, verifies train/internal form isolation, tests history uniqueness, and encodes rows through the working training serializer on CPU. The original 129-form pool includes productive variations of shared arithmetic concepts, not 5,465 unrelated concepts.

A separate custodian must screen the train histories against protected development, validation and confirmation families before inclusion in a run. No protected files were opened for this work.
