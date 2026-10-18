# Reviewed-data pilot runner contract

Creator: Navneet Prabhakar

Status: implementation specification from the production-readiness audit; no runner or real language pilot is claimed here.

## Purpose

Provide a reproducible command for finite local language-training pilots using the existing reference trainer, token shards, mixtures and curriculum state. Remove the need to assemble diagnostic scripts manually. Do not change the model, optimizer, numeric acceptance policy, review authority or spending scope.

This is the next independent implementation task. It can be built and validated using explicit synthetic fixtures while source/policy inputs remain pending. It must not silently enable unreviewed public data or run the actual 1M/10M pilots.

## Inputs and preflight

- Require an explicit model config, complete recipe, canonical random-initialization seed, tokenizer, immutable data binding, output directory and finite cumulative update/processed-position ceilings. Record both processed and supervised positions; do not call either unique tokens without the corresponding inventory evidence.
- Support verified token-shard and single-objective mixture inputs first, with the same binding model extending to existing curricula. Do not silently flatten a curriculum, reset stage clocks or discard its exposure receipts.
- For every leaf token component, require its reviewed source release. Match the release/tokenizer/leaf manifest fingerprints and lineage record identities, content hashes, source revisions, family/split groups and counts against the checked train reader. A sample-only manifest, stale review, held-out example, changed tokenizer or rehashed arbitrary corpus must fail before model allocation or output creation.
- Require model vocabulary/context compatibility. Pin logical run identity to config, recipe, initialization, tokenizer/data/source identities and format versions. Backend/device selection is recorded separately so legitimate checkpoint transfer can retain the logical run.
- Never initialize from pretrained student weights. Fresh runs use the canonical initializer; resumed runs preserve an explicit random-origin chain, moments, global/stage counters and data position.
- Validate all paths/settings before starting work. This command has no teacher transport, public download, cloud launch, credit/reset or billing side effects.

## Bounded execution

- Use the existing update-boundary trainer semantics; do not modify its numerical recipe. Check the next entire accumulation group against the cumulative position ceiling before executing it. Never truncate a message, split an optimizer update, reset a cursor, wrap a finite dataset or exceed a ceiling to reach a round token number.
- Report a boundary stop with unused positions when the next atomic update cannot fit. Dataset exhaustion below the planned workload is incomplete work, not a completed pilot. A short resumed invocation cannot claim the total positions consumed by earlier attempts as newly executed work.
- Allow a per-invocation update ceiling for controlled interruption/resume tests and a soft wall-time limit checked at safe boundaries. State explicitly that an in-flight update/checkpoint may exceed a soft time limit; it is not a hard spending guarantee.
- Emit bounded, streaming update events with loss, learning rate, global/stage counters and timing. Do not hold an entire long training history in memory. Nonfinite state and data-integrity failures must leave the latest committed checkpoint usable and the report incomplete.
- Synchronize backend work for timing. Separate data/preflight, initialization/restore, optimizer execution, checkpoint and evaluation time. Record peak memory with its method/limitations. Measure useful training throughput, not reader-only hashing speed.

## Checkpoints and resume

- Wrap the existing atomic training checkpoint with a hash-bound run identity and provenance receipt. Avoid modifying the trainer's established checkpoint schema or adding unchecked state. Publish any latest-checkpoint pointer only after checkpoint completion and durable metadata writes.
- Save at an explicit cadence and at safe final/interruption boundaries. Keep bounded checkpoint retention within this runner's managed output only; do not remove arbitrary external paths or the last usable checkpoint before its replacement is verified.
- Resume into a fresh attempt directory from an explicit complete checkpoint. Verify wrappers and all trainer state before allocation. Restore optimizer and data clocks exactly; reject config/recipe/data changes instead of silently restarting. Record backend transfer separately from numerical/quality acceptance.
- A crash after an update but before checkpoint publication may require replay from the last committed state. Preserve prior attempt logs, distinguish logical consumed positions from work actually executed/replayed, and do not infer successful checkpoint completion from an update event alone.

## Curriculum and evaluation

- Preserve existing stage-local warmup/stable/cooldown and accumulation settings. Stop at a capability-gated stage exit unless the corresponding evidence is explicitly bound to the current checkpoint, evaluation suite, result, policy and reviews. A proposed policy or `insufficient_evidence`/`reject` screen cannot advance a production stage.
- Do not replace a learned student with a scripted adapter during stage evaluation. Keep raw-history and host-assisted results separate. Reference-mechanics tests must be unmistakably synthetic and cannot create actual policy/source/capability approvals.
- Record source/slice validation and baseline regressions when actual eligible evaluations exist. A finite trainer finishing its schedule does not prove English/style/tool competence or accept the original failed trajectory criteria.

## Acceptance evidence for implementation

1. Invalid sample-only data, stale releases, vocabulary/context mismatch and rehashed unapproved lineage fail before output/model allocation.
2. A finite verified fixture stream stops without wraparound, dropped tails or over-budget updates. Processed/supervised and new-invocation counters match independent expectations.
3. A fresh run and update-boundary resumed run match exact parameters, moments, scheduler and next-batch state on local MLX and PyTorch CPU. Wrong resume bindings are refused. Actual CUDA wrapper validation remains separately identified.
4. Interrupted/corrupt checkpoint and orphaned-event controls recover only from a complete checkpoint. Retention does not delete the last usable state or unrelated paths.
5. Existing mixture/curriculum recipes retain their stage/exposure state; unaccepted stage screens cannot be mistaken for advancement authority.
6. The command and its saved run specification are exercised from a separate process, with source/config/data/artifact hashes and an explicit synthetic scope. No real source approvals or language-learning claim are produced.

## Real pilot gates remain separate

After eligible data/admission review, tokenizer selection, portability-policy choice and evaluation preparation, use this runner for the actual target-model 1M-position smoke workload and required 10M pilot. Report actual processed positions and retained checkpoints rather than assigning those labels to a shorter run. Main GCP training still requires its own budget and fresh full-instance checks.
