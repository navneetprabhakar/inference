# Tool-calling improvement plan

This is a separate capability track alongside English recovery. Do not train on this exposed diagnostic suite and call it independent evaluation. No model training or GPU launch is authorized by this document.

## RCA update

The bounded RCA is complete; see RCA.md. A512-token output probe repeated the same invalid output, while native calculate/convert controls terminated normally but failed semantically. The tested Fit30 SFT phase has24 English sessions and zero positive tool examples. Prioritize task-aligned call/result supervision and a versioned registry; do not spend on4K-input/4K-output context as a fix. Stage learning from one-tool CRUD to multi-turn errors/no-call behaviour and then ten-tool routing. The original full suite remains stopped; no automatic resume.

## 1. Establish the failure boundary

Complete the ten-tool CRUD diagnostic and the unchanged production calculate/convert controls on the same Fit30 weights, greedy decoding and reply budget. Report valid native frames, exact tool/argument selection, actual effects, grounded final answers, blocked turns and whole workflows separately. A successful mock dispatcher proves harness behaviour, not model competence.

This adapter is experimental. Existing production serialization, validation and broker policy accept only calculate/convert and numeric results. New CRUD tools are unseen schemas with structured results. Failure in this adapter is a transfer failure; it cannot by itself establish whether the model can learn CRUD after supervised training. Plain-text or incomplete output remains failure; do not repair it into a successful call.

## 2. Make the training/runtime contract support the tools

Introduce a versioned tool registry with explicit schemas and immutable identifiers. Preserve the old serializer and frozen datasets. Implement strict arguments, allowlist and no-call policies, bounded calls, call/result ID binding and structured error observations. Retain native assistant call delimiters and mask prompt/tool observations from supervised loss. Verify exact training-to-serving prefix identity for success, missing records, duplicates, rejected calls and multi-turn workflows.

The ten mocks currently accept opaque strings, including the email/URL-labelled fields. Before domain-realistic training, either document them as generic record fields or add corresponding schema validation and new tests. Do not imply this simple harness exercises a real contact/calendar/database integration.

## 3. Prepare executable, reviewed training trajectories

Build small, balanced lessons covering all four CRUD operations, not just call-shaped JSON. Every positive trajectory must contain a proposed call, an actual replayed mock result and a correct final answer. Include:

- Create then read; update then read; delete then read/not-found.
- Corrected IDs/values and retained state across user turns.
- Duplicate-create and missing-record errors, without fabricated success.
- Tools-enabled/no-call and tools-disabled/no-call examples.
- Ambiguity that needs clarification, and complete authorization that does not need redundant approval.
- Partial failures and bounded retry decisions; distinguish original attempts from retries.

Use exact Terra CLI for natural conversational wording and review it fully. Tool observations come only from deterministic execution, not generated narration. Split scenario/template groups before related variants; separate values and IDs, and reserve unseen tool names for a distinct transfer slice. Count unique assistant targets separately from replay exposures. These current48 exposed scenarios may guide diagnosis, but are not pristine release data.

## 4. Bounded learning pilot after local gates

First prove the actual optimizer receives correctly masked tool-call and final-answer targets. On a tiny development fit set, require observable valid calls and faithful result use; loss reduction alone is insufficient. Then run a bounded mixed English/tool pilot from a pinned parent and optimizer identity. Fix exposure counts, update limit, checkpoints, stop rules and budget before launch; do not automatically extend after failure.

Keep English as the primary objective. Select the tool mixture by assistant-target mass and compare English development behaviour against the same parent. Prefer the cheapest GPU that passes readiness and measured throughput constraints. Provide a new finite cap only after local readiness and dataset sizing; old closed authorizations cannot be reused. No GPU estimate in this plan is a measured cost forecast.

## 5. Predeclared capability gates

For a fresh, reviewed development suite with at least five examples per tool/operation combination, propose these pilot continuation gates (not a release guarantee):

- At least95% exact valid call/argument sequences and end-state correctness overall, with no hidden per-tool collapse.
- At least90% complete workflows and faithful final answers, reviewed against actual observations.
- Zero unauthorized mock mutations in disabled/ambiguous/no-call controls; all unexpected calls retained in the denominator.
- No unexplained regression on the existing English and calculate/convert controls; compare complete sessions, not selected successes.
- Two failed bounded pilots force diagnosis/hold. Do not increase learning rate, epochs or budget automatically.

Freeze thresholds and suites before training. After a development pass, preselect one checkpoint for protected release checks, then qualify the selected weights on local MPS before changing any serving default. Passing tool tasks alone does not establish conversational release readiness.
