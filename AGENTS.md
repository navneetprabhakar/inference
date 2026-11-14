# Own-model work: quality-first operating rules

Read OWN_BASE_HANDOFF.txt before training, dataset admission, model selection or cleanup.
The user's current instructions override this file. Current status: PAUSED by user; final A100 run closed; VM/disk retired after verified backups. No GPU starts, allocations, retries, extensions or training without explicit resume. Signal-resume exactness failed; no fit pilot or release acceptance. Evidence: reports/english-a100-v1/. Corrective-corpus-v1 remains immutable.

- User priority: English conversation first, then maths, then CBSE through Class12. Defer maths/CBSE corpus expansion until preceding capability gates pass. Tool checks protect regressions but do not substitute for English conversation acceptance.
- Optimize for demonstrated conversation/tool quality, not tokens, epochs, corpus size or job completion.
- Never label a model accepted from loss, checkpoint age, a few calculator probes or successful job exit.
- Use the mandatory nano_sft quality contract. Bind exact dataset parent, tokenizer, context, review/split receipts and required data intent. Missing evidence blocks training.
- Production train/dev must cover tools-disabled/no-call, tools-enabled/no-call and tools-enabled/call. The isolated english_fit_diagnostic requires both no-call modes, deliberately excludes positive tool training, and cannot authorize release. Report unique assistant targets and family target mass separately from sessions and replay exposures.
- Fully review generated data before admission; replay every tool result. Split by source/scenario/template group before generating related variants. Do not put exposed evaluations into pristine release claims.
- Preserve regression-stop state across restart. Do not automatically increase epochs, learning rate, retry counts or budgets after failure. Compare generated behavior of best and last checkpoints.
- A new GPU campaign requires verified readiness receipts, explicit finite budget and reserve, bounded pilots, backup/shutdown qualification and at most one training writer. Two failed pilots force diagnosis/hold.
- Training completion is not release acceptance. Use the hash-bound release gate with complete per-turn review and protected checks; separately qualify the selected model on local MPS before changing a serving default.
- Never rewrite an incorrect model answer with a rule and report it as model improvement. Keep raw frames, actual tool calls and blocked follow-ups in assessment denominators.
- Keep the local requested model/runtime available. HTTP remains off unless requested. Keep VMs off during local work.
- Stop/join writers and verify required GCS backups before normal shutdown. A finite lease still stops compute on backup failure; preserve the persistent disk and sole copies for recovery. Never delete unverified sole copies.
- Retain future-use data, selected weights, provenance and compact evidence. Delete disposable caches/intermediates; do not blanket-archive obsolete experiments.
- Update the handoff with current facts, evidence links, limitations and next blockers. Preserve historical facts in Git rather than appending contradictory current-state paragraphs.
- Batch related changes into few commits/pushes. Run the meaningful objective, masking, restart, serving, quality-gate and retention checks before delivery.

- Corrective-corpus-v1 is immutable. Do not regenerate it in place. Release tests are single-use for a preselected candidate; do not consume them for exploratory baseline/model selection. The frozen4Kpilot contract caps each run at10updates. English diagnostic bounds are separate and cannot authorize promotion.

- Corrective pilots default to packing buffer1 to preserve seeded order; longest-first packing was measured to starve short lessons inside a10update pilot. Bind buffer size to checkpoint identity.
- For the existing4Kcorrective candidate, evaluate all61development sessions/232turns through local-readiness-v1/development-shards, preserving system prompts and predeclared per-turn reply budgets. No partial-shard pass. Independent release remains separate and unused.

- Historical L4 start/cheaper-GPU/hands-off authorization: L4 under10USDoperational envelope within prior15USDceiling; no automatic upgrade/extension.11supported zones failed capacity; all VMs off, no new disk, no worker ran. No automatic retry is pending. Reconcile the ledger and prepare a fresh lease before any future attempt; never rerun the closed request.
- Native2K english_fit_diagnostic is isolated from production. Explicit fit flag and reviewed24/12input hashes are mandatory; <=64finite epochs/64updates, LRmultiplier<=.25, active development regression stops, no release eligibility. Keep unique targets separate from replay exposures. Actual64epoch schedule is96updates, so64update cap ends earlier.
- Restart qualification MUST align observation schedules (cadence1 for2vs1+1), preserve exact comparison and prove actual CUDA/GCS recovery. CPU control-flow checks do not establish GPU readiness. Current worker is qualification-only; signal/upload/provider-stop fault checks remain outstanding before a fit pilot.
- Never use DELETE-on-timeout launchers. Require fixed absolute provider STOP, non-auto-delete recovery disk, verified GCS backups before normal shutdown, and hard stop with disk preservation on backup failure.

- Final run closed on14Nov2026 at09:42:45UTC. Normal CUDA/GCS restart passed; signal rollback was exact but resumed update failed exact comparison. Upload-rejection and independent provider-STOP drills were not reached. Keep project paused, local models available, HTTP off.
