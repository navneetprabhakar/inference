# Production-readiness audit

Creator: Navneet Prabhakar

## Decision

The project has a substantial reference implementation, but **no language-trained conversational model or completed 1M/10M language pilot**. Stop treating fixture growth, teacher formatting or transport success as evidence of that outcome. The next independent code task is a general reviewed-data pilot runner; production-scale data admission/intake is another real implementation gap.

The read-only audit maps **58 criteria** across every execution-sequence section, evaluation and operating rules. Each criterion records its scope, status and hashed local evidence. No aggregate readiness percentage or goal-completion claim is derived from the counts. See `reports/milestone-thirty-readiness.json`.

## Observed state

| Area | What is proved | What remains |
| --- | --- | --- |
| Architecture/checkpoints | 80,765,440 parameters; canonical FP32 model/optimizer state; atomic saves, finite cursors, accumulation and curriculum recipes | A user-facing bounded real-data pilot driver and sustained runs |
| Portability | Retained tiny MLX/CUDA round trips; full exact state imports and fixed-checkpoint context checks | Full trajectory gate still fails; acceptance option A/B remains pending; reduced precision unvalidated |
| Public data | Four pinned sources; 901 sample-only rows, split 799/70/32; grouped/official-split safeguards | Zero source/row approvals; 398 language-unknown rows, all 901 content-unreviewed; no production bulk/admission policy |
| Tokenizer | Disjoint IDs, reviewed-train builder and 16K/24K comparison tooling | Synthetic candidates yielded 432 IDs; no eligible representative production candidate or freeze |
| Teacher | CLI-only transport, 14 cached candidates, host normalization, style guides and review workflow | No actual rights evidence/human release; two families and narrow arithmetic do not establish broad coverage |
| Training/capability | Tiny/full synthetic mechanics, finite mixture/curriculum support | No 1M/10M language pilot, conversation/style/tool SFT or useful learned model |
| Runtime/MCP | Five local handlers; bounded actual stdio/HTTP SDK controls, including retained NVIDIA checks | Scripted controls are not learned tool competence; production OAuth/action authorization unimplemented |
| Evaluation | 500 candidate cases, rubrics and stage screens | Zero approved cases; proposed policy; no release-grade learned scores or measured p95 deployment target |
| Later stages | ESCI/relevance/replay/compression design | Correctly deferred until the core unquantized conversation/tool checkpoint exists |

The 2,600,025-position scale result was a synthetic **reader** probe with zero neural updates. Short synthetic T4/M4 throughput is not a sustained language pilot or current full-instance cost estimate. Retained hardware/cleanup reports were read; this audit did not requery resources, prices, quotas or billing.

## Missing code versus missing inputs

**Missing implementation**

1. A general training command binding reviewed releases, token artifacts, config/recipe, finite budgets, checkpoint cadence, report recovery and continuation. The trainer APIs exist, but the inspected commands are audits and diagnostics. The [runner contract](reviewed-data-pilot-runner.md) defines the next implementation and its acceptance checks.
2. Production intake/curation that scales beyond 32 MiB input files and 10,000 rows without materializing the corpus. It must retain global deduplication, official splits and exposure provenance; raising a limit is not a solution.
3. Scalable corpus admission under an explicitly reviewed sampling/quality policy. The current publisher only admits individually reviewed rows. Reviewing forty examples does **not** approve the other 861 or a bulk corpus. Do not bypass that bootstrap contract or silently require manual review of billions of documents.
4. Production tokenizer selection/freeze, sustained run/evaluation integration and later learned capability work. Mixed precision, fused kernels, constrained decoding, production authorization, ESCI and compression remain unimplemented/deferred as recorded in the matrix.

**Inputs needed at the relevant gates**

- Actual public source terms and review decisions; separate corpus-admission policy before scalable release.
- Portability acceptance option A or B. No tolerance or original failure is waived by this audit.
- Actual account/source evidence and human judgments before teacher release.
- Evaluation suite/rubric/stage-policy review.
- Main-training budget/hardware selection before paid GCP pretraining. Existing USD 10 authority remains CUDA-validation-only, with USD 7 conservative allowances and unknown settled charges.

Implement the runner with explicit synthetic controls while these inputs are pending. Do not run real training, bulk downloads or more teacher generations merely to keep the loop active. The remaining three teacher slots are not an instruction to spend them.

## Audit verification

- Fresh config count, source manifest/checksums, packet binding, Source-bearing local training-manifest inventory, checked sample-reader refusal, candidate review states, stage proposal, failed trajectory report and actual journal counts are inspected.
- The audit refuses to preserve this baseline automatically if public approvals/releases or evaluation approvals have changed; classifications must then be revisited. It is a point-in-time diagnostic, not an automatic promotion or legal-clearance tool.
- Model/runtime code is unchanged. Latest local suite remains **581 passed / 13 CUDA skips**; no new neural update, generation, API/cloud action, approval or numerical policy change occurred. Teacher reservations remain **17/20**, active halt false.
- The full goal remains active and incomplete. The audit exposes independent implementation work, so it is not an impasse declaration or a narrowed definition of success.
