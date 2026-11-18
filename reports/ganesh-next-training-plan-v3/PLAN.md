# Ganesh-base — next training plan, paused for reassessment

18 November 2026. Creator: Navneet Prabhakar. This supersedes the earlier plan's sequencing recommendations; frozen experiment specifications remain unchanged. **No overnight work, automatic retry, training or GPU allocation. Reassess with Navneet tomorrow.**

## Evidence to start from

- Existing model: approximately537M parameters,10B base-training tokens. No accepted conversational release.
- Reviewed candidates:1,026 English conversations plus67 separate maths/decision/orchestration conversations;1,093 total,6,259 assistant replies. Not admitted to a new training run; no claim that the new data has improved current weights.
- Ten mocked CRUD tools and a deterministic harness now exist. User stopped the main diagnostic after37/48 scenarios; all37 failed to produce valid native calls. Eleven scenarios and the multi-turn results are not complete-suite evidence.
- Token-limit RCA: prompts242–249tokens; a512-output continuation repeats the same failure. Two existing-schema tool controls terminate normally but make no calls and answer incorrectly. A greeting control also fails its instruction.
- Fit30's bound SFT dataset has24 English sessions and no positive tool-call examples. New CRUD training also requires a versioned structured-result protocol; production currently supports only calculate/convert. These are concrete missing pieces, not proof of an architecture ceiling.

## Decisions for tomorrow

1. Confirm whether to implement the tool-training contract and a tiny executable-tool fit diagnostic before the broader English comparison. Recommendation: prepare both locally, qualify the execution path once, then run separately bounded learning arms so failures can be attributed.
2. Choose a predeclared parent and comparison strategy from existing evidence; do not select a checkpoint just because it is newest. Preserve local weights and serving defaults.
3. Approve the exact curriculum mix and fresh grouped development design. Keep English primary; basic maths remains a small supplementary track, CBSE expansion deferred. Current correction/memory and advisory-style concentration needs balancing.
4. Only after readiness and workload sizing, request a finite GPU cap with backup reserve and measured stage forecasts. Previous budgets are closed; no current8K/context-extension or GPU authorization is inferred.

## Proposed execution sequence

### A. Local readiness

- Finish the real controller/lease/backup timeout integration and process-level fault tests identified in the earlier plan. Preserve failed receipts and exact source bindings.
- Introduce a separate versioned registry/structured-result serializer for the mock tools. Test strict arguments, policy enforcement, call/result IDs, errors, quotas, loss masking and exact train/serve prefixes. Keep historical frozen formats intact.
- Review the1,093 candidates for curriculum admission and group related scenarios before train/development assignment. No copying exposed diagnostics into pristine release claims.
- Author executable tool lessons with actual replayed mock observations and fully reviewed final answers. Start with one store's CRUD, then stateful workflows/errors/no-call decisions, then multi-tool selection. Use realistic fields/values in the next suite. Natural generated dialogue retains the exact Terra CLI provenance/review process.

### B. Bounded GPU learning, only under a new approved cap

- Complete operational qualification with real recovery/backup checks. Local unit tests do not qualify CUDA/GCS.
- Run the predeclared tiny tool fit: prove the optimizer sees correct call/result boundaries and the model learns valid calls, arguments, termination and faithful answers. Stop and diagnose if this fails; do not automatically add epochs or tokens.
- Run the separately bounded English comparison or mixed curriculum pilot, according to the decision above. Pin targets/exposures, update limits, packing, learning rate, observation cadence, parent and optimizer identity. Compare best and last generated behaviour.
- Two failed bounded pilots force a hold. Backup before normal shutdown; retain recovery storage if backup fails; provider lease still stops compute.

### C. Acceptance and local use

- Score complete conversations and workflows, including blocked turns, unintended calls, wrong arguments, state errors, fabricated success and English regression. Loss and successful job exit are not acceptance.
- Freeze prospective thresholds before training; the tool plan proposes95% exact calls/state and90% grounded workflows, with zero unauthorized mutations. These are development continuation proposals, not demonstrated scores or release guarantees.
- Preselect one candidate for protected release and local MPS qualification before changing the serving default.

## Explicitly not the next fix

Do not increase input/output budgets to4K+4K for the observed failure. The checkpoint is2K total, and8K is unqualified. Context extension is a separate future experiment only when real workflow lengths require it. Do not conceal model errors through prose-to-call rewriting, fallback models or repaired answers.

Evidence: ../ganesh-tool-crud-v1/RCA.md and IMPROVEMENT_PLAN.md; ../ganesh-english-sourcing-v1/scale-1000/RESULT.md; ../ganesh-foundations-extension-v1/RESULT.md; ../ganesh-action-plan-v2/PLAN.md for outstanding controller details. All work is paused after tonight's commit/push.
