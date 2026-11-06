# Read-only tool-data reuse audit

**Reuse the varied lesson semantics and broker, but not their legacy serialized histories.** The current tool generators are incompatible with `dialogue.training_row` for any history containing a call. A new replay-and-bind adapter is required before candidate preparation. No generator/import was executed, no new examples were produced, and no protected cases were read during this audit.

| Source | Actual execution and coverage | Reuse judgment |
|---|---|---|
| `tool_teaching.py` | Ordinary `observed` calls invoke validated `tools.execute` directly. Explicit numeric fixtures bypass execution. Includes arithmetic, bidirectional conversions, division-by-zero errors, prior-result recall, arithmetic chaining, original-unit recall and a small no-call/clarification set. | Legacy baseline only. Fixed templates, narrow integers and manually constructed result IDs; fixture results lack authoritative broker provenance. Prefer varied source. |
| `tool_teaching_varied.py` | Every proposed call passes through `FixtureSession.propose`. Ordinary observations run pure adapters; counterfactual numeric/error fixtures are host-bound replay, explicitly distinguished from actual adapter results. Stores full time-independent observations, per-user host policies and form families. | Best reusable source, after replay, binding, current framing validation and root custody. |
| `broad_teaching.py` | No calculator/converter traces. Curated Dolly/OASST text histories include corrections, rewriting, source extraction and real second turns; some Dolly follow-ups are editorial. | Separate compact conversation supplement only; not evidence of tool competence. Requires fresh source/custody/quality validation before reuse. |

Varied coverage is concrete: `followup` teaches observed-number recall, multiplication using the returned number, and original-argument/unit recall. `special_lessons` teaches missing input clarification, explicit no-call expressions, later permission grants, post-call no-call recall, corrected starting operands, within-turn arithmetic and conversion chains, transient errors followed by a user-requested retry, no-result readback, division by zero and signed conversions. `paired_observation` holds the request fixed while changing the broker-bound observed value; the final answer and later recall follow that value. Chained counterfactual cases feed the first observed result into the actual second adapter call. Synthetic changed readings must remain labeled as fixture observations, not represented as correct arithmetic.

The transient retry occurs after a new user turn clears the prior fixture binding; it is not autonomous recovery. Coverage does not include general arbitrary-tool planning, web access, production side effects, unsupported schema repair or broad autonomous retry policies. These should not be claimed as learned capabilities.

## Blocking format mismatch

Current `dialogue._frames` requires:

- Assistant proposal: exactly `role`, `call`, `call_id`.
- Following tool frame: exactly `role`, `record`; the authoritative record must bind matching `call_id`, tool name, arguments when present, boolean `ok`, and exactly data or error semantics.
- Final assistant text before the next user; each assistant JSON body and EOT is supervised, while headers/user/tool frames are masked.

Both generators instead call `proposal`, which emits only `role` and `call`, then emit `role:tool,result:...`. Varied uses `local_chat.tool_view`, projecting authoritative records into the old `{name,id,result}` or `{id,error}` shape. Current framing rejects the missing call binding before training. The legacy `local_chat.encode_frame` also uses `User:`/`Assistant:` prefixes, unlike current `[user]\n`/`[assistant]\n` framing. Do not reuse that serving serializer or its documented token-length figures.

Plain `broad_teaching` alternating role/text histories structurally fit current framing, but actual lengths must be remeasured. Its historic 127-history/8,200-target-token receipt and varied's 5,465 histories/129 families/187-token maximum are old published preparation observations, not newly verified current-format counts.

## Broker and verifier

The broker validates finite bounded numeric inputs, exact flat fields, allowed operations, dimensional compatibility and duplicate JSON fields. It owns permission, tool scope, call IDs and immutable deep-copied traces; quota is two proposals per turn and four per session. Permission/schema failures are recorded without dispatch. Numeric/error replay binds to an exact proposal. A matching fixture remains active for that turn; it is not automatically consumed after one call. `start_turn` resets the binding. Adapter arithmetic is deterministic and offline.

`verify_tools.py` tests permission/revocation, malformed proposals, quotas, immutable returned traces, exact fixture binding, replay without live dispatch, retry after a cleared error fixture and actual division-by-zero failure. These are broker contract tests, not student capability tests. Its decision flag `dispatched=True` covers entering the adapter/replay stage: a synthetic recorded fixture does not necessarily execute arithmetic. Preserve the `source` field when reporting real versus replay observations.

## Concrete prospective reuse plan

1. Freeze selected **own-base** checkpoint lineage and a separate bounded SFT diagnostic specification. No model training or release admission follows from this audit. Use the neural next-token model under the later training specification; no host answer head, tool-selection shortcut or conversational fallback.
2. Use `tool_teaching_varied.records(seed)` in a new preparation process only after approval of its pins and limits. Preserve `family`, original history, observations and per-user policy. Replay each call through a fresh broker while following those policies; compare deterministic observations, excluding volatile timestamp, with the recorded source.
3. Build new histories with host-generated `call_id` and complete timestamp-free broker `record`, retaining source/schema/name/arguments/ok/data-or-error. Bind the assistant proposal to the returned call ID; never make call IDs student-generated JSON fields. Verify every following answer and chain references the actual broker observation. Do not merely rename legacy `result` to `record`.
4. Validate complete current `training_row(context=1024)` and each inference prefix with the fixed256-token reply reservation. Reject overlength full lessons or use a separately specified complete-turn policy; do not silently truncate utterances, tool observations or unresolved call cycles. Recompute assistant-target counts under current framing.
5. Root custody must screen train candidates and any public diagnostic families before admission. Split whole authored form families and keep paired counterfactual variants together. Keep `internal_records` separate from fitting: it uses distinct forms and excludes matching first-call signatures, but is an exposed development diagnostic, not a sealed release test. It does not remove all later-call/signature/concept overlap.
6. Report tool/text mixture by actual assistant-target tokens, not history counts. Varied data are heavily tool-positive; no-call histories are scarce. Preserve ordinary conversation, missing-information and no-call examples so a tool-only loss reduction is not mistaken for general interaction progress. Any balancing/repetition needs its own prospective budget.
7. Evaluate unassisted generated proposal syntax/arguments, broker execution, final readback, paired counterfactual sensitivity, correction use, chaining, error reporting and no-call behavior separately. Count prohibited-call proposals as model failures even if the broker correctly blocks them. Report attempted calls as well as dispatched calls, and raw outputs. Invalid JSON must remain visible; no host repair or canned answers.

## Memorization and access limits

Numerical variation does not create new linguistic tasks. Fixed templates, small operand domains, repeated answer strings, distinctive fixture wording and reusable correction phrases permit template memorization. Training and internal inventories share operations and scenario structures. A later evaluation needs locked unseen surface forms/numeric domains, observation-swapped pairs and full multi-turn interactions; in-family exact match is insufficient. The broad supplement changes only ordering with its seed and is too small to establish general instruction following.

Static import review found no protected-case reads in the audited import paths: `tool_teaching` imports the pure tools package; varied imports `local_chat`, which imports torch, dialogue, guards and tokenizer definitions but does not instantiate a model/session/guard at module import; broad imports definitions only, and reads selected archived training files when `records()` is called. `internal_records()` generates public internal lessons and training lessons, not sealed cases. No imports were executed to test these conclusions. Avoid invoking old verifier/trainer entry points merely because a historical README recommends them; their current serializer and custody status must be reviewed separately.

## Subsequent serving contract clarification

Root requires the new standalone `own_base_chat` serving path, not legacy `local_chat`. The tool adapter must share its stable broker projection and `policy_text` once frozen. Current permission is supplied in the leading host-policy system frame. Because permission can change between user turns, prepare one prefix per user turn and supervise only that current turn's assistant frames; earlier assistant frames remain context with masked targets. Use the separate `own_base_sft_rows.last_turn_row` helper, deriving shifted token boundaries through `dialogue._frames`, without modifying frozen `dialogue.py`. Revalidate fixed256-token reply reservations after policy insertion and stable projection. Candidate v3 text lengths before this transformation are not final training-row admissibility.
