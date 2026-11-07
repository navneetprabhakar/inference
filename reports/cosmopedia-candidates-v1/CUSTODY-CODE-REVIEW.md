# Root custody code review

Code-only review of protect_cosmopedia_candidates.py and imported helper implementations. No protected case files were read, Shield instantiated, or screening executed by reviewer.

Core behavior is appropriate: requires matching independent DB/receipt/count proof; scans full generated text and original prompt plus recognized role-delimited spans; uses read-only SQLite, quick_check, before/after hashes, bounded resources and STOP; records exclusions only with no split/admission/student-scoring claim. Limits raise rather than treating unscanned text as clear.

Before launch recommended: compare proof.policy_sha256 with receipt.policy_sha256; require explicit not-admitted flag and positive integer verified_rows. Include A/release/B/private/public protected hash identities in receipt and final recheck, not only private/SPEC. Shield/BShield enforce A/release/B hashes during construction, but current protected map/final check omits them. Recheck historical holdout hashes at final boundary, beyond checks immediately after reading each file.

Scope limitation: candidate_history recognizes User:/Assistant: only; Alice:/Bob: children dialogues are scanned as full text but not individually segmented. Short embedded overlaps can be missed. This is inherited lexical scope, not semantic independence; document explicitly or prospectively extend root-owned plaintext segmentation with synthetic fixtures.

No code modification or private fixture tests by reviewer. Root notified of recommendations.
