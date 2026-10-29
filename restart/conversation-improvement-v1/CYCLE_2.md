# Cycle 2 — fresh optimizer for curriculum transition

Cycle 1 stopped at control step 50: narrative NLL 1.375497 passed, but retention content fell 72→53/80. Teacher arm was never started. Nineteen lost turns concentrate on the exposed record-wording variant and repeated owner names; this is behavioral forgetting, not a narrative-loss failure. Do not train on these evaluation answers.

Hypothesis: inherited Adam moments from the previous narrow objective contribute to unstable transition. Change one major factor: reset moments/counters/RNG at original B weights. Keep fixed LR 2e-5 (no added warmup), data, order, coefficients, deterministic engine, decoding and all guards unchanged. This is a separate run, not continuation of cycle 1's stopped weights.

Alternate control/teacher 50-update blocks, up to 400 each. Content floor72, narrative≤original×1.05, numerical/resource stops unchanged. Development/secondary at200/400. Stop both on either guard failure. Campaign ledger and remaining caps apply cumulatively. If stopped, diagnose before another versioned cycle; no final-test exposure or promotion.
