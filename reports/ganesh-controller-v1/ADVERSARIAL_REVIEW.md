# Adverse review of integrated local pilot

17 November 2026. Same-agent second review; not an independent release review.

**Verdict: local bounded-pilot preparation passes; cloud launch HOLD.** Tests cannot establish CUDA numerical equivalence, provider shutdown or English capability.

| Failure attempted or found | Resolution / evidence |
|---|---|
| Offline gate disconnected from execution | Controller and child adapter both gate actual dispatch; unapproved real request spawns nothing |
| Stage spoof, review-dependency removal, no-resume curriculum, unbound data, injected argv | All five graphs rejected; adversarial-graph-checks.json |
| Exit zero treated as success, changed outputs, crash replay | Expected result schema, bound output hashes and durable in-flight reconciliation required |
| Partial candidate/turn review or misleading checkpoint step | Full planned candidate set, exact ordered turns, raw hashes and actual checkpoint metadata checked |
| Detached decode worker survives controller termination | Signal handler terminates and joins worker group; subprocess regression test |
| Two training directories bypass writer exclusion | Machine-wide SFT lock added; competing-writer test |
| Frozen development reply budget silently reduced | Probe supports actual 192-token frozen budgets; workload repriced in token bounds |
| Curriculum omits baseline or protected regressions | Baseline/best/last English and protected probes required; raw protected scores recomputed |
| Review consumes paid VM time after lease | Nonbillable semantic review may proceed after STOP; next command still gate-bound |
| Identity examples dominate tiny corpus | v1 rejected; frozen v2 identity mass 4.28%; still not learned identity |
| Small corpus mistaken for broad recovery | Explicit seed-pilot label; seven actual updates, exposed development, short context, no release eligibility |

202 distinct targeted tests pass. Full semantic data review covers 138 turns, six replayed calls and a separate scenario-oracle pass. Runtime extraction/source verification passes; 41 older frozen hashes remain unchanged. Evidence: final-tests.log, curriculum-adverse-review.json, local-readiness.json, unauthorized-dispatch.json, integrated-*-preflight.log.

Residual risks: model may fail even the fit; existing CUDA restart mismatch remains a hard gate; decode is uncached and unmeasured on the prospective GPU; synthetic short examples do not establish natural broad conversation or delayed long-context memory. Reviews are performed by the same agent and remain fallible. Cap, image/price/inventory/backups, real recovery/fault/STOP evidence must precede permitted execution. No guarantee of zero exceptions is credible. Fail closed and retain diagnostic evidence.

## Pre-commit third pass

202 targeted tests rerun successfully. Rechecked controller/task gate and stage deadlines. Found a planning limitation: maximum generation volume is not proven to fit the two-hour probe-stage limit. BUDGET.md now makes measured worst-shape, overhead-inclusive timing a pre-training gate; no timeout expansion or reduced evaluation is implicit. $20 is a bounded-attempt proposal, not a proven completion cost. No GPU activity was performed.
