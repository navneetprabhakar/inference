# Accepted portability and delegated source review

Creator: Navneet Prabhakar

## Decisions implemented

- **Option A accepted** by the actual user on 19 October 2026. `configs/portability-acceptance-v1.json` records the response and required gates: exact training-state transfer, same-checkpoint inference parity and measured resumed-training quality. Strict multi-update trajectory failures remain failed diagnostics; inference tolerances are unchanged. Useful resumed-training quality has not been demonstrated.
- **Source/sample review delegated** by the actual instruction: “this is a simple problem statement, you can review as expert”. The earlier manual-export prerequisite is superseded. No personal human review, human attestation, HTML export or real browser verification is claimed.

## Checked review authority

Bounded review packets and disk-backed explicit-row headers now support `review_mode: delegated_expert`, `reviewer: delegated_expert`, `human_attestation: false`, and a dataset-bound authorization receipt. It records the owner, actual instruction, date and explicit-row scope. Missing/misbound authority, mixed human flags, mode downgrade and whole-corpus scope are rejected. Human packets retain their original behavior.

Approved rows carry `delegated_expert_reviewed` validation markers and `delegated_expert_review` receipts, never invented `human_attested` labels. Existing source provenance, record hashes, teacher-specific checks, heldout protection, source-category constraints, disk limits, shard coverage and train-only verification remain enforced. The authority receipt records the method and instruction; it is not cryptographic proof of judgment.

## Actual source and sample decisions

The review binds the existing complete-source parent manifest `1c50b116a72202c6ed8c10eb41a1a4b3ce411f4d308c713f0a3d1c804558e730` and immutable quality sample. The original pending master, HTML parts and original 40-row packet remain historical artifacts; decisions are a separate checked bundle.

| Scope | Result |
| --- | ---: |
| Dolly sample rows disposed | 93 |
| Complete Dolly texts assessed | 91 |
| Dolly rows screened out by high-stakes topic, without full fact-check | 2 |
| Explicit Dolly rows accepted | 42 |
| Dolly rows excluded/deferred | 51 |
| Other-source sample rows excluded without content grading | 194 |
| Accepted train / validation / test rows | 17 / 7 / 18 |
| Unsampled rows approved | 0 |

The pinned Dolly publisher card explicitly permits academic/commercial use under CC-BY-SA-3.0 and describes employee-written responses with Wikipedia contexts. Source/card/license hashes and required attribution are preserved. Approval covers explicit SFW rows for private research; it is not unrestricted rights, distribution clearance or a guarantee of exclusive provenance. Other sources are deferred: FineWeb needs underlying-web-content/terms treatment, UltraChat needs its synthetic-origin terms resolved, and OASST still needs its own conversation/privacy/quality assessment. These deferrals are not assertions that those sources are prohibited or unusable.

The sample contains substantive defects: incomplete extraction, incorrect award categories, an answer changing the Moon's age from billions of years to years, faulty chess explanations, ambiguous classifications, unanchored current records and unreliable health targets. Rejections include conservative scope/verification deferrals as well as errors. **51/93 is not an estimated corpus defect rate.** The sample is stratified/purposive, and near-family correlations remain. Accepted targets have known minor spelling/style limitations recorded individually; this is a research subset, not a factual gold standard. Privacy judgment means no visible private identifiers were found in the accepted text, not proof of origin.

Actual artifacts:

- `data/delegated-source-review-v1/decisions.json`: all explicit decisions, source notes, authority and unchanged reviewed records.
- `data/delegated-source-review-v1/stream/`: checked v2 header and JSONL ledger.
- `data/delegated-source-review-v1/release/`: verified 42-row explicit release, including 17 train rows.
- `scripts/review-dolly-sample.py`: recorded row-specific decisions bound to the exact input SHA256; not a classifier or an instruction to grade new data automatically.
- `reports/milestone-thirty-seven-source-review.json`: counts, release hashes, scope and limitations. Raw source text stays outside Git.

## Verification and next work

- Focused review suite: **45 passed**. Full local suite: **702 passed / 15 hardware-dependent skips**. Both human and delegated modes retain train-only access; missing/misbound authorization, false human flags, changed source/text and heldout contamination are refused. No new CUDA run is claimed.
- The 58-criterion readiness audit recognizes the actual release and accepted Option A; it no longer requests source-review exports or an A/B answer. Historical strict failures remain in evidence. No readiness percentage or project completion is inferred.
- Seventeen train records cannot responsibly supply a 1M-position pilot. Next: develop a bounded research admission policy under the delegated authority, expand representative training data, compare/freeze the train-only tokenizer, then run the real local pilot. Do not replay these rows to manufacture a token milestone or infer population approval from this sample.
- No neural updates, cloud jobs, new teacher launches or Platform API calls. CUDA allowances remain USD 7/10; settled costs unknown. Teacher reservations remain 17/20. The full execution goal remains active/incomplete.
