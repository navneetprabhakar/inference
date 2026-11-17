# Second adversarial review after cleanup and local implementation

17 November 2026. Same-assistant review, not independent certification.

**Decision: local review can continue without GCP authentication; launch remains HOLD.** No successful local test converts an unimplemented controller, unadmitted curriculum or unavailable cloud receipt into a pass.

## Newly tested findings

1. **Conversation-check loophole confirmed in real code.** nano_sft --fit-eval-steps pins checkpoints and runs loss checks; it does not generate/review conversations. Added nano_fit_probe.py for explicitly bound arbitrary checkpoints, strict fit/development purposes, bounded subprocess, raw decoding and complete output retention. It cannot run a release scope. Actual MPS smoke on default194 completed3scheduled turns: one malformed tool frame and two blocked follow-ups. This verifies runner plumbing only; it is a model failure, not3successful replies. Milestone scheduling/semantic progression still need controller wiring.
2. **Generation-cost undercount fixed.**540user turns can invoke up to3model actions each. Upper bound corrected to1,620model calls /207,360generated tokens at128/action. No L4 throughput claim is inferred from the6.85second failing MPS smoke, which generated only one short bad action.
3. **Null approval/lease draft crashed the checker.** Real unapproved-request invocation exposed an AttributeError missed by initial synthetic fixtures. Fixed explicit timestamp validation; added regression test. It now returns a structured HOLD, not a traceback.
4. **Type confusion found and fixed.** Boolean VM counts, negative/noninteger failed-pilot counts and nonhex candidate hashes are rejected by the offline checker.
5. **Release relabeling path closed in new probe.** Development requires its exact purpose; heldout_release cannot be passed as development. Oversized per-action budgets are rejected. Purpose checks and hashes do not replace custody or independent semantic review.
6. **Disconnected gate explicitly identified.** The new gate is an offline helper, not a provisioning or training executor. No assertion that old launchers now use it. proposed-request.json sets launcher_integrated=false; actual gate-result.json refuses it. This is an unresolved integration blocker, not a tested safe controller.
7. **Stage state versus immutable identity remains an integration design requirement.** Production selection and receipt state evolve after qualification; the controller must keep immutable campaign inputs separate from journaled outputs and bind each stage's evidence chain. Do not create new qualification authority by editing a candidate hash and writing a self-reported pass. The helper alone is not sufficient to solve this.

## Prior feedback disposition

| Feedback | Disposition |
|---|---|
| No-resume must not authorize production | Defaulted to exact-resume only; unselected exception remains explicit and diagnostic-only; negative tests cover attempted transition |
| STOP must be qualified before training | Required; real provider proof still missing; no substitution of final shutdown |
| Cost should be workload-based | Actual frozen counts and maximum action/token bounds computed; region-specific BOM and L4 measurements still pending |
| Quality needs full denominators | Existing scorer tests cover missing, blocked, unreviewed and tool-action cases; raw new smoke retains all3turns |
| Independent evaluation | No false independence claim; broad production/release remains blocked until review ownership is settled |
| Fixed parent and no blind retries | Plan fixes immutable base10B; new draft prohibits automatic retry/restart; live enforcement not yet qualified |
| Backup must be restorable | Local payloads and archive validated; GCS fresh restore remains a cloud gate |
| Cleanup must preserve sole copies | Hash/file-level deletion receipt; no model/frozen/source dataset deletion; replacement archive readback verified first |

## Evidence

-171targeted tests pass;28offline recovery-gate tests plus7probe input tests and136existing regressions. These counts describe this single suite, not additional unique tests across historical runs.
-All41frozen hashes unchanged; three retained model bundles fully validated.
-Two actual tokenizer/manifest validate-only commands pass:2-update capture and64-update fit.
-New runtime150members/27adapter modules, independently extracted and compared with current source. SHA256 in local-results.json; no upload or GPU qualification.
-Local smoke raw results in probe-smoke.json, command and log retained. No weights trained or altered.
-Cloud read-only inventory failed reauthentication; error retained in cloud-access.json. No cloud writes.

## Launch decision

Do not claim launch-ready. Remaining local work is controller/receipt/generation orchestration and, for the broader campaign, actual reviewed curriculum and release-review arrangements. GCP auth is not a blocker for those local tasks. Fresh auth, cap/lease approval, cloud backup/price/inventory checks and real GPU/provider qualification are separate external/execution gates.

A plan document cannot resolve these by declaring future checks passed. LAUNCH_PLAN.md is the sole current plan and identifies precise stage requirements. Closed historical requests remain closed. No new budget, VM start, release exposure or promotion is authorized by this review.
