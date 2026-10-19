# Corpus admission contract proposal

Creator: Navneet Prabhakar

Status: proposed. No corpus-wide approval, accepted threshold or implementation is created by this document. The implemented release scopes remain explicit rows only.

User delegation recorded on 19 October 2026 now authorizes expert source/sample review; it does not silently admit an unsampled corpus. Routine review decisions no longer require manual exports from the owner. The explicit 42-row Dolly release is documented in [milestone thirty-seven](milestone-thirty-seven.md). A bounded research admission policy should be distinguished from production release assurance.

## Required before any sampled corpus admission

1. **Population:** name the exact staged manifest, source revisions, source-card/license evidence and eligible record identifiers. Resolve terms for each source and underlying/teacher origin; document allowed content categories. A source license label alone is insufficient evidence.
2. **Deterministic eligibility:** specify versioned language, privacy, quality, content-setting, duplicate/family and contamination rules. Preserve slang, quantities, negation and context. Undetermined classifications must be quarantined unless a separately explicit decision resolves them. Declared `en` and the existing regular-expression redactions are not adequate production classifiers.
3. **Coverage:** define strata by source, conversation/prose/tool task, content category and relevant style/length slices. Freeze the candidate population before selecting samples. Account for unequal source sizes, correlated families, rare slices and repeated message exposure. Convenience first-N samples are not representative.
4. **Sampling and judgments:** record a reproducible random seed, family-aware selection, inclusion probabilities and independently reviewed record IDs. Define each failure class before inspection, with source-specific denominators and treatment of ambiguous cases. Sampling estimates cannot prove that every unsampled row is safe or correct.
5. **Acceptance:** explicitly choose sample sizes, uncertainty method, tolerated error by class, handling of any critical privacy/content/partition defect, minimum stratum coverage and when a full source is rejected. Values remain undecided; do not choose them from whatever a pilot happens to pass. Record the residual risk and a recorded owner or explicitly delegated expert decision authorizing the exact eligible population and intended research/production scope, rather than treating sample acceptance as implicit authority.
6. **Artifact:** bind the accepted policy, original population, eligibility output, sample selection, judgments and admission decision by hashes. Mark approved rows as policy-admitted, never individually human-verified. A new manifest, changed rule, upstream revision or expanded content scope requires a new admission decision.
7. **Checked reader:** recompute eligibility and selected sample coverage, propagate held-out constraints across the complete population, verify exact admitted-row coverage, reject policy/status/lineage mismatches and never yield validation/test or quarantined rows. Explicit-row review v2 is not this reader and must reject a whole-corpus scope.
8. **Operational proof:** test representative natural text and dense duplicate populations at the intended volume. Bound time, RAM, database/spill/output disk, repeated exposure, failure cleanup and restart cost. Synthetic random-word throughput does not establish production suitability.

## Next concrete implementation boundary

Produce a non-admitting eligibility/audit artifact with measured language/privacy/quality signals and a deterministic family-aware sample. Keep all results sample-only until the policy, source terms, judgments and exact population scope are explicitly accepted. Do not promote the 42 accepted explicit Dolly rows into approval of unsampled rows or a downloaded corpus.
