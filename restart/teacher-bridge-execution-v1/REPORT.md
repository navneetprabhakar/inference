# Teacher bridge execution — terminal preflight stop

**The approved plan reached its mandatory numerical-repeatability stop. No fit or teacher-versus-control result exists.** Four disposable optimizer updates ran; no candidate was promoted. Original, A and B checkpoints and the historical retention stop remain unchanged (see [audit](audit.json)).

## Execution and evidence

| Check | Result | Meaning |
| --- | --- | --- |
| Data preparation and CPU checks | Passed | 800 unique grounded records, 400 rehearsal records and 144 reviewed teacher conversations prepared; split/mask/schedule checks passed |
| Independent PyTorch/MLX numerical comparison | Passed | Maximum loss difference 0.01448; maximum gradient relative L2 difference 0.02889; minimum cosine 0.99967, within frozen thresholds |
| Checkpoint serialization and exact restoration | Passed | Saved weights, moments, RNG, counters and metadata restored exactly |
| Two uninterrupted updates versus save/resume trajectory | Failed | Exact embedding-weight equality failed after four total disposable updates; frozen stop enforced |
| Fresh optimizer two-update check | Not run | Preceding prerequisite failed |
| Name/time fit gate, matched main study and fresh final evaluation | Not run | No capability or teacher-benefit conclusion possible |

The teacher subset contains 24 two-turn conversations per family across six families. The primary agent directly reviewed 254 structurally eligible records, held eight, and selected 144 without rewriting. This is a narrow pilot admission, not independent review or admission of the full 1,000-record bank. Teacher examples entered disposable preflight updates only. Prepared development/final banks received no model evaluation. The reviewer authored those banks; independence is limited even before evaluation.

## Read-only diagnosis

At the same saved state and with identical inputs, repeated gradient calculations returned identical losses but different embedding gradients. Relative L2 differences were **0.1053% and 0.1150%** for two same-order comparisons. Only the embedding gradient differed in these comparisons. Weights and optimizer moments remained unchanged throughout diagnosis.

Parameter dictionary order changes after an update, but same-order repeats also differ: ordering alone does not explain the failure. Backend embedding-gradient nondeterminism is a plausible explanation; the specific kernel cause is unproven. The failed two-update terminal weights were not persisted, so their actual discrepancy cannot now be quantified. These observations do not establish that the resulting optimizer trajectory differences are harmless.

The current exact-trajectory requirement is stricter than the repeatability demonstrated by this execution path. This is evidence about the experiment machinery, not evidence of insufficient model capacity, corrupted checkpoint restoration or unsuccessful learning.

## Resource accounting and preservation

- 4 optimizer invocations; 612 assistant/EOS target exposures; 8,192 narrative target exposures.
- 59,392 total model input positions, including read-only numerical/gradient diagnostics; 11.84 seconds of recorded active model time; peak process RSS 2.90 GiB.
- Zero new teacher calls or downloads. No additional training after the stop. No budget reset or relaxed threshold.
- The sole new checkpoint is a disposable preflight step-1 snapshot under ignored `private/`; it must not seed a main study.
- Plan, training/evaluation data, runner and historical dependencies were frozen before model work. Post-stop diagnostic scripts are separately hashed in the closing audit; they were not part of the initial freeze.

## Reassessment and next decision

1. **Resolve numerical repeatability before resuming experimental training.** Isolate the embedding-gradient operation and reduction path; establish deterministic execution if feasible. Preserve exact checkpoint serialization requirements.
2. If deterministic execution is impractical, propose a new preflight with prospectively justified trajectory tolerances, multi-step weight/moment comparisons and a bounded engineering budget. Do not retrospectively mark this run passed or reuse its partial budget as a fresh attempt.
3. Only after that prerequisite passes should a new approved run execute the prepared name/time fit gate, followed by the matched teacher comparison if fit succeeds. The existing data/schedule can be reused after verifying frozen hashes.
4. Broad-English development remains blocked independently by corpus admission. The [broad-data readiness packet](BROAD_DATA_READINESS.md) identifies the actual supply and gaps; there is no admitted new broad release.

Current retained-model capability evidence remains the earlier matched improvement (25/152 to 56/152 exact answers) and its limits, including 0/16 complete names and 0/16 exact times on that held-out diagnostic. This run neither improves nor overturns those measurements.

Evidence: [approval](approval.json), [frozen inputs](freeze.json), [CPU checks](cpu-checks.json), [numerical preflight](numerical-preflight.json), [terminal stop](STOP.json), [gradient repeats](repeat-diagnosis.json), [ledger](ledger.json), [decision](decision.json), [closing audit](audit.json).
