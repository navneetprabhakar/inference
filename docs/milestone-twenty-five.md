# Continuation supervision and explicit teacher replies

Creator: Navneet Prabhakar

## Delivered scope

- The active teacher recipe uses `scenario-cli-demonstration-v2` through the existing saved-auth Codex CLI path. `reply` explicitly means the final post-tool answer when a mock action/result exists. Clarification must request missing information; corrections must preserve corrected facts. No API fallback is enabled.
- Version 1 keeps its exact prompt bytes and historical request construction. Version 2 sorts scenario object keys before deriving schema arrays, preventing cache misses caused only by JSON object insertion order. Different prompt versions have different request keys. This instruction contract does not prove free-text compliance.
- Plain and typed serializers accept `supervision='last-user-turn-v1'`. The final user message determines the boundary; earlier assistant messages are context with zero direct loss. New assistant call frames, assistant payload/end markers and final EOS are supervised. User, system, tool-result and role-marker tokens are not targets. Context still participates in attention and may receive gradients through that path.
- Reviewed examples opt in through immutable `validation_results.supervision`. Unmarked student corrections remain refused. Continuation records cannot enter the foundation/all-token objective. Records exceeding context are rejected rather than truncated.
- New shard version 3 has separate `plain-continuation-v1` and `tool-continuation-v1` formats. Readers reconstruct the boundary from token roles and reject incorrect masks, including artifacts with recomputed checksums/accounting. Legacy plain-v1 and typed-v2 shards retain their original behavior. Different formats require separate filtered components.

## Verification

- Final local suite: **477 passed / 13 unavailable-CUDA skips**. This includes independent historical-error mask checks, verified synthetic review-to-shard round trips, rehashed mask tampering, legacy reader coverage, prompt/cache version separation and a fixture executable that asserts the actual submitted v2 prompt.
- After the final prompt predicate clarification (`action.kind is call`), **23 CLI contract tests pass**. Source/artifact hashes and scope are recorded in `reports/milestone-twenty-five-summary.json`.
- Synthetic typed continuation masked loss and exact checkpoint resume pass on local PyTorch CPU and MLX. CUDA variant skips locally. This is training mechanics, not learned English/tool competence or new NVIDIA validation.
- All seven existing real v1 candidates are read from cache with no provider/network invocation. Request keys match; the six candidates with previously recorded full prompt hashes also match those hashes. The oldest candidate did not record that hash. None becomes training eligible.
- Initial fixture checks failed: two expected-error regex mismatches and two held-out fixture partition errors. Correcting the tests preserves production partition rules. Fixture partition selection varies the synthetic example identity, whose hash actually determines the local split.

## Retained cache-audit failure

A cache-only audit initially rebuilt an old scenario from sorted JSON. Version-1 schema `required` arrays preserve original dictionary order; the rebuilt request therefore had a different key despite equivalent field values. An in-process `CacheOnly` provider immediately raised before any CLI subprocess or network operation. The reservation was retained and explicitly reconciled using the observed failed terminal Python audit process. It is abandoned and cannot be replayed; no journal reset/refund occurred.

The corrected audit restores historical schema field order and checks the reconstructed key before entering the lifecycle. Seven cache reads then leave the journal unchanged. Combined journals now retain **10/20 reserved slots**, including the local audit failure; actual historical CLI generation launches remain **9**, with seven successful candidates. There are ten unreserved slots. The active journal is not halted. See `reports/milestone-twenty-five-cache-audit-failure.json` and `reports/milestone-twenty-five-cache.json`.

## Remaining work

- Compose candidate teacher continuations into registered host-tool transcripts, execute the host oracle, attach source/rights lineage and obtain human review before release. The teacher mock name `multiply_amount` is not a registered student host tool and must not be copied directly into training data.
- The last-user-turn contract supports complete user-turn continuations. A future bridge must require user-ended input context; histories already partway through a tool exchange need a separate boundary contract. No automatic teacher-record conversion is implemented here.
- Seven real teacher candidates remain unapproved. Public source review, portability-policy choice, evaluation/style review, production tokenizer selection and real language pilots remain open. Earlier failed trajectory gates are unchanged.
- No new live teacher/API generation, cloud job, source approval or real-data training. CUDA validation allowances remain USD 7/10; settled charges unknown.
