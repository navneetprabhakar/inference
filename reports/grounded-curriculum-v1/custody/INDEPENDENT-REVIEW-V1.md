# Independent supplemental custody review

Changes requested for the documented full-parent coverage contract. This is a public-only code review and synthetic regression check, not candidate verification or admission. Evidence and exact reviewed hashes: independent-review-v1.json; reproducible entry point: independent_review.py.

## Required correction

`candidate_content(chat)` supplies the full original transcript as one text plus selected utterances. It does not split individual utterances in an unselected original prefix. A protected three-word prompt, `Locate violet folio.`, is detected standalone but missed when embedded only in the discarded original parent prefix. The existing `protect_language_mixture.candidate_history` parser correctly detects it. Split the original role-delimited parent too, and add this regression. Current grounded chat construction retains complete histories, so this counterexample does not demonstrate contamination of its current candidates; it is a real gap in the screener's advertised coverage.

## Verified behavior

- Independently reconstructed the pinned public inventory: 442 sessions, 632 turns, 496 expected call occurrences, 416 unique concrete signatures.
- All nine existing CPU regressions passed. Same-turn dependencies use actual fixture results, including overrides. Cross-turn proposal-argument references survive execution errors; numeric-result references after errors raise. Each case resets its session and each turn resets turn policy while retaining session state.
- Expected calls are included before execution, so failed calls remain exclusions. Numeric normalization and commutative ordering are inherited from the existing signature implementation. Nested structured proposals across original tool histories are traversed, including later turns.
- Activation SHA and corpus/runtime hashes are checked before indexing. Invalid independent state, nonempty failures, hash mismatch, missing artifacts, nonpositive or mismatched counts, malformed JSON/SQLite, resource ceilings and STOP fail without a successful receipt. Candidate file symlinks are rejected, artifacts are rehashed, and existing supplemental receipts cannot be overwritten.
- The independent-proof check is a receipt contract, not proof of organizational independence: trusted root review still establishes who produced the receipt. No builder self-check state is accepted.

## Limits to make explicit

- `augment` intentionally omits fewer-than-three-token texts. The actual inventory contains two such user prompts and 17 literal exact targets. Another 23 exact targets are references; these are passed unresolved to `augment` and contribute no textual target. They currently resolve to generic unit labels. Thus 'all exact textual targets' overstates literal coverage; document the minimum-token/reference policy or deliberately add suitable exact handling. Do not indiscriminately exclude every candidate containing generic unit words or common acknowledgements.
- The supplemental code does not enforce the legacy/public exclusion union; its state is only `screened_not_admitted`, and protocol and receipt limitations correctly require the later packer to pin both receipts, union document IDs, and recount retained targets. No final-packer implementation was in this review's scope. A public screen alone is insufficient for admission.
- Runtime/corpus checks protect against accidental drift, not an adversarial writer changing and restoring files during a run. Offline immutable inputs and single-owner custody remain assumed.

No candidate, custody receipt, frozen runtime, private input or model was modified or opened by this review. Existing tests created and removed their own synthetic temporary directories only.
