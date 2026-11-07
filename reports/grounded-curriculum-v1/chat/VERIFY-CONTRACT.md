# Independent verification contract

The author-owned builder and semantic snapshots are not the verifier. A separate agent owns the verifier and reviews every finite surface and canonical split before instances exist. It must not import builder renderer/semantic execution helpers as its semantic oracle. Frozen templates can be used to extract bindings after manual semantic review; this is finite authored-domain verification, not a general prose entailment engine.

Required checks:

- Candidate complete state, no recorded failure, all policy and code/tokenizer pins, raw and SQLite integrity/hash, matching row counts and document/task links.
- Every full raw original history equals the selected whole history; no role changes, missing messages, undeclared system turns, duplicate normalized content, or unexpected rows.
- Independently extract each state value from reviewed prompt/answer templates; verify types, distinct entities/values, bindings, identity/split ranges, and matching frozen surface identity and first-user form index (instance index modulo form count).
- Independently execute grounded initial fact/event/query semantics, including overwrite, add/remove, role swap, unchanged bindings, ambiguity/missing facts, source authority, negation and requested formatting. Check answer claims against those derived values. Record surface-level manual assumptions and limitations.
- Canonical construction family does not cross splits, equivalent merged surfaces share it, all six groups retain both splits, and exact canonical/surface counts match prospectively approved split.
- Independently reconstruct host frames, target masks, positions and prefix lengths with frozen tokenizer/framing contract; recompute each document and aggregate target/input count. Do not rely solely on build_chat_rows results.
- Independently replay deterministic proposal ordering, distinctness/duplicate/framing refusals and first-non-fitting cap stop, verifying no adaptive refill or hidden rows. Check train≤540000 and development≤60000 after actual framing.
- Confirm root's legacy and public custody are pending, not represented as satisfied by candidate verification.

Only a complete independent PASS may produce the sole candidate-verification.json. For existing protect_own_sft.py compatibility use state PASS_pre_host_policy_not_admitted; declare scope explicitly independent_grounded_candidates. Include database_sha256, manifest_sha256, verified_rows, failures=[] and verifier/manual-review/code pins. New public custody also accepts PASS_independent_grounded_candidates_not_admitted, but do not create contradictory receipts. On failure preserve evidence and report failure; no self-issued PASS, silent repair or regeneration of frozen identity.
