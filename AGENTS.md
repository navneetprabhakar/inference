# Own-model work: quality-first operating rules

Read OWN_BASE_HANDOFF.txt before training, dataset admission, model selection or cleanup.
The user's current instructions override this file. Current campaign status: GPU QUALITY HOLD; corrective-corpus-v1 data admitted and release frozen.

- User priority: English conversation first, then maths, then CBSE through Class12. Defer maths/CBSE corpus expansion until preceding capability gates pass. Tool checks protect regressions but do not substitute for English conversation acceptance.
- Optimize for demonstrated conversation/tool quality, not tokens, epochs, corpus size or job completion.
- Never label a model accepted from loss, checkpoint age, a few calculator probes or successful job exit.
- Use the mandatory nano_sft quality contract. Bind exact dataset parent, tokenizer, context, review/split receipts and required data intent. Missing evidence blocks training.
- Train/dev must cover tools-disabled/no-call, tools-enabled/no-call and tools-enabled/call. Report unique assistant targets and family target mass separately from sessions and replay exposures.
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

- Corrective-corpus-v1 is immutable. Do not regenerate it in place. Release tests are single-use for a preselected candidate; do not consume them for exploratory baseline/model selection. Current pilot contract caps each run at10updates.

- Corrective pilots default to packing buffer1 to preserve seeded order; longest-first packing was measured to starve short lessons inside a10update pilot. Bind buffer size to checkpoint identity.
- Evaluate all61development sessions/232turns through local-readiness-v1/development-shards, preserving system prompts and predeclared per-turn reply budgets. No partial-shard pass. Independent release remains separate and unused.
- The proposed$15A100 or$10L4 caps are NOT approved. Keep VMs off until explicit cap approval. Never reuse a DELETE-on-timeout launcher for corrective qualification; require provider STOP and preserve recovery disk on backup failure.

- Second review found qualification observation schedules differ for2vs1+1updates. The user15USDcap is conditional on an unchanged assessment, so it is NOT activated. Report/read readiness-second-review-v1 first; fix the controlled experiment before any GPU launch. Passing component tests is not full qualification-runner readiness.

- Latest user start/cheaper-GPU/hands-off instructions follow the changed assessment: prepare L4 under10USDoperational envelope within prior15USDceiling. Historical conditional-cap notes are superseded for this bounded English diagnostic. No A100 upgrade. Native2K diagnostic_only contract is separate from production; it permits64bounded updates/epochs, preserves regression stops, and can never authorize release. Qualification must precede the fit pilot.
