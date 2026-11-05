# Preview calculator operand order

The final preview code passed **24/24** cases on the frozen CPU development regression, up from **10/24**. The earlier 15-session usability smoke remains a separate historical measurement.

| Check | Before | Final |
|---|---:|---:|
| Ordered subtraction with two numbers or an observed result | 6/11 | 11/11 |
| Clarification for missing or ambiguous operands | 1/4 | 4/4 |
| Missing prior after an actual adapter error | 0/1 | 1/1 |
| Disabled tool notices | 0/3 | 3/3 |
| Unevaluated arithmetic expression | 0/1 | 1/1 |
| Live-service capability limitation | 0/1 | 1/1 |
| Non-command controls with zero calls | 3/3 | 3/3 |

The host parser recognizes calculator preambles, single quantity-bearing noun phrases and directional wording such as “deduct A from B” or “take A off B”. Each operand must have one unambiguous number or a bound reference. Differing registered units, several possible quantities, missing operands and unsupported subtraction directions produce a clarification. A learned subtraction proposal cannot dispatch without an authenticated direction. A statement that tools are enabled never grants permission.

The preview can transcribe a simple unevaluated expression without using an adapter. It distinguishes questions about external live lookup from requests for offline arithmetic. Both kinds of host notices carry explicit host frame origins and leave the trace empty.

The seven supplemental compound plumbing checks passed. Four used a synthetic first-call fixture of 41 or −10 and verified both subtraction directions against the actual returned value. Ambiguous direction and incompatible units each produced zero calls. A first-call outage stopped the chain after one failed event.

These rules cover a bounded command grammar. Unrecognized subtractive requests now abstain more often. Other open-ended arithmetic phrasing still depends on the learned router, and free-form conversation quality is outside this regression. The cases were frozen before editing the parser, and the same cases were used to check regressions during implementation. Their pass rate is a development measurement.

**Evidence.** The 24-case suite digest is `5bdbbe2f9a7cfe70b284b9b96414bf6bb5fb3f7c0e17f9e5cbb63f23bf1df90c`. The final implementation digest is `f7369250fb3b1216e8e6c7ccc5162524116e77e67d26d7da427d78f8d4c93116`. See `before.json`, `frozen.json` and `compound-f7369250fb3b.json` for actual answers, origins and broker traces from the pinned local CPU checkpoint.
