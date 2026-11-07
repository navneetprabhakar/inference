# Independent custody review after corrections

PASS with documented limits for supplemental screening; not candidate verification or admission. The original findings and evidence remain in INDEPENDENT-REVIEW-V1.md and independent-review-v1.json. Current reviewed hashes and reproduction results are in independent-review-v2.json.

Root corrected both coverage issues: original chat parents now split into individual role-delimited utterances before screening; exact answer references resolve after the turn's expected fixture executions and must yield text. The independent discarded-prefix counterexample now detects the protected prompt. All ten CPU regression tests pass. The actual pinned public inventory remains 442 sessions / 632 turns / 496 expected call occurrences / 416 unique signatures.

The protocol now explicitly records inherited minimum-three-normalized-word lexical coverage (two short public prompts, 17 short literal exact targets; the 23 referenced exact targets now resolve, to short generic unit labels). Generic acknowledgements and unit labels alone do not establish semantic contamination. Expected calls still resolve correctly across synthetic observations, same-turn dependencies and errors; unresolved numeric results fail closed.

Final packing must independently require and pin both legacy and public receipts, exclude their union, and recount retained targets. This supplemental implementation intentionally does not admit data or implement final packing. No candidate or custody receipt was modified; no private input or GPU was used.
