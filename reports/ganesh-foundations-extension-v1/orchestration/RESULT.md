# Orchestration candidates

- 24 preplanned scenarios generated using `codex exec --model gpt-6.1-terra`; at most two CLI processes ran concurrently. Fresh sessions reviewed every assistant turn; maximum two revisions per candidate. Requested model is recorded, while backend routing was not independently verified.
- Selected 19 conversations / 95 assistant turns; SHA-256 and verifier results are in `verification.json`. Full-content review and every raw generation version, including excluded versions, are retained.
- Excluded orch_003 after its second revision failed cold review. Full orchestrating-agent review excluded orch_013 and orch_015 for unsupported approval and test gates; orch_020 for an unsupported sequencing restriction; orch_022 for describing two performed checks as partially checked. No replacement generation was attempted.
- `verify_new`, `verify_full_content`, and `selection_memory_integrity` passed for every selected row. No memory credit is claimed. Both native 2K no-call policy encodings were checked during generation.
- The retained dialogues are text-only decision examples, not positive-tool training. Candidate selection does not establish training admission, source-group splitting, decontamination, model improvement, or release acceptance. Arithmetic in orch_019 was independently replayed and bound in ../supplemental-arithmetic.json.
