# Independent tool v2 verification result

PASS for every retained candidate after independently replaying the complete prospective pools and deterministic selection. No admission, packing, GPU, private-case access or model-quality claim.

| Source | Whole histories | Turns | Targets | Exact numeric readbacks | Observations |
|---|---:|---:|---:|---:|---:|
| Primary | 4,417 | 5,930 | 226,330 | 4,420 | 5,021 |
| Four-call session | 552 | 1,656 | 97,731 | 1,656 | 2,208 |

All 6,076 numeric readbacks exactly match observed numbers, resolving the v1 rounding defect. Independent Fraction arithmetic checks ordinary results within float tolerance; readback equality has no tolerance. All 786 synthetic observations have explicit fixture bindings and provenance. All 472 error observations agree with their declared timeout or division-by-zero behavior. Every session has actual call counts [2,2,0] with observed-result dependencies and no third-turn execution.

Verified all original histories, tasks, chosen prompt forms, independent program calls, correction/retry/clarification/no-call semantics, observations and provenance, stable replay records, dispatch decisions, adapted whole histories, actual role/JSON/EOT tokenization, current-turn masks, reply-prefix reservations, per-row/aggregate counts, position exposure, hashes, family splits, complete call/parameter separation, source records, refusals, first-overflow stop and unused target caps. No builder/adapter/production-framing helper imported. Tokenizer and actual offline FixtureSession are shared runtime primitives; arithmetic and serializer/masking logic are separately implemented.

Both selected wording forms survive for every retained family. Primary conversion coverage is 16/16 directions in both splits. Sessions cover 16 train and 14 development directions; missing development directions: [('cm', 'mm'), ('m', 'km')]. This fixed-selection coverage limitation is disclosed, not repaired by refill. Mathematical primitives overlap across splits; authored wording/compositions are not unseen mathematical skills.

Sole receipts are candidate-verification.json in data/grounded-tool-candidates-v2/ and data/grounded-session-candidates-v2/. Both bind verifier SHA1a5806d7b686fb40abce2a2ae4d6ca3204d0d78da0f52186635970bd4cb174d8 and finite-surface review. Full receipts copied into verification-summary.json. Root legacy/private and exposed-development custody union plus independent final-stream verification remain required.
