# Semantic review final checkpoint — 1 November 2026

Status: **review coverage complete; candidate not admitted for training.** The immutable source is `data/author-only-v2/conversations-2500.jsonl`, SHA-256 `f4e2fdc22bd92ea083cc2b97f4684315681306186802855ca996fdc468081c7b`.

The reviewer was Codex CLI assistant review using externally selected `gpt-5.6-terra`. That is neither independent server attestation nor independent human review. The old `state_5.sqlite` note described an unnecessary nested-CLI attempt; it was not a blocker for this authenticated model invocation and remains preserved as superseded audit history.

| Decision | Count |
|---|---:|
| Keep | 870 |
| Repair | 1,475 |
| Exclude | 155 |
| Unreviewed | 0 |

Every ledger record was validated against the original index, ID, source hash, messages hash, complete-conversation attestation, reviewer provenance, before content, after role structure, and decision/change relation. The earlier 24 sampled records were rechecked: 7 kept, 15 repaired, and 2 excluded. The derived candidate contains 2,345 records, has hash `3c30fc0934544dfa929e3ed3aafc30a7fa6cfd45bc746c42f353689110a3b6ac`, and remains a review projection rather than approved training data.

The immutable-source mechanical audit confirms 2,500 unique IDs, alternating roles, no context overflow, final supervised EOS for every record, and the expected frozen checkpoint hash. Derived-candidate lexical validation found zero full normalized duplicate groups, one duplicate first-user group, and no exact or near overlap with prior held-out user turns. Mechanical checks are not semantic certification.

Twelve hand-authored development cases and twelve separate frozen confirmation cases have balanced coverage across grounded explanations, precise rewrites, instruction constraints (including required exact repetition), follow-up continuity, strict single-tool calls, and strict chains. Tool scoring checks ordered full names, exact argument objects, executable completion, and final answers. Prose scoring is predeclared and independent of reference length; repetition, generated length and stop reason are reported separately.

The expected checkpoint exists and matches SHA-256 `93bb235b29c8bdff5efe4e14bac223b92b5bc70fecc3023a22d8ed2d9b6fd781`. The authorized development-only baseline versus prose-only penalty comparison is implemented with tools left at the baseline decoder. It did not run: this execution environment’s MLX runtime reports no accessible Metal device. No outputs or performance claim are substituted for that missing run. No confirmation cases, training, paid API, cloud compute, source corpus, STOP files, local-author-v1 state, commits, or pushes were changed.
