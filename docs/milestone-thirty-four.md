# Offline quality signals and whole-group audit

Creator: Navneet Prabhakar

## Delivered

A sample-only auditor now measures language, privacy candidates and quality features over canonical data without rewriting it. It runs a pinned official fastText CLI/model offline, stores records/windows/groups on disk and selects whole split groups with recorded strata and inclusion probabilities. See the [contract](quality-audit-contract.md) for limits, provenance and interpretation.

## Actual existing sample

- **901 records, 674 groups, 3,446 message windows**; 3,444 windows scored and two lacked alphabetic content. The scan takes about **1.02 seconds** locally. Parent process peak RSS is about **49 MiB**; this does not include a measured child-process high-water mark or establish a hard total-RAM bound.
- **93 records in 64 complete groups across 23 strata** are selected for audit. Source coverage: FineWeb-Edu 18, UltraChat 12, OASST2 41, Dolly 22. Selection is conditional on the existing first-N-derived snapshot, not representative of full upstream sources. Judgments remain null.
- Fourteen records have at least one non-English top-labelled window; four records contain eleven IPv4 literal candidates. One window returns only one label. These are review signals, not established defects; code, examples, quotations and short text can trigger them. All 901 original records/labels remain unchanged and unapproved. No match values are copied into committed reports.
- Sixteen authored controls include ten clear-language sentences, all matching the expected English/non-English top class, and six intentionally ambiguous short/code/mixed cases. `yo` receives Khmer, numbers French, code Catalan and a romanized mixed sentence English. The diagnostic is not representative accuracy or calibrated confidence; it demonstrates why the classifier cannot decide admission.
- Private result/sample: `data/quality-audit-v3/`. The original forty-example review packet remains byte-identical; this audit does not replace it or produce a reviewed release. Training correctly refuses the new artifact.

## Negative control and verification

The existing 11,000 random-word synthetic records produce 22,000 windows. The real detector assigns English as top label to 2,699 windows despite the fixture not being coherent conversation. Every assessment remains unverified and every row remains ineligible. Runtime is **10.94 seconds**, parent peak RSS about **50 MiB**, peak main database about **60 MiB**; nine whole groups/records are sampled. This is bounded mechanics and a quality negative control, not evidence of production corpus quality or natural-data throughput.

Final local suite: **677 passed / 15 hardware-dependent skips**. Focused audit suite: **23 passed**. Tests cover text preservation, privacy offsets without matched values, complete window coverage, probability accounting, whole-group selection, input-order invariance, cross-partition refusal, artifact/input mutation, process failures, malformed/incomplete scores, budgets and cleanup. No student numerical implementation or tolerance changes.

The initial real audit refused a legitimate one-label CLI result because the parser incorrectly required exactly two labels; it published nothing. A retained probe found one such case among 3,444 prediction lines. The parser now supports up to two results while keeping line coverage exact and missing evidence explicit. The successful full suite before this fix is retained separately from final verification. Three terminal HTTP 403 acquisition attempts are recorded; publisher source-card and license evidence were then retrieved from pinned official GitHub repositories. Binary/model/card/license hashes are retained. The detector model is an audit dependency, not pretrained student weights.

## Remaining requirements

Language/privacy/quality eligibility suitable for production remains partial. Samples still need actual judgments; source and teacher permissions/approvals remain pending. No corpus-admission threshold or policy is accepted, no production tokenizer is frozen and no actual language pilot has run. Numerical portability acceptance remains unresolved.

No teacher generation, Platform teacher API call, cloud job, credit action or real/synthetic neural training update occurred in these audit runs. Read-only public dependency/GitHub retrieval did occur. Teacher reservations stay 17/20; conservative CUDA allowances USD 7/10, settled charges unknown. The full goal remains active/incomplete.
