# Teacher decisions in the offline review console

Creator: Navneet Prabhakar

## Delivered

- The existing console now supports the publisher's four additional teacher decisions: reply meaning, style/content, history conversion and host grounding. Each remains pending until explicitly selected. The required field set is derived from the frozen composition receipt, not from an imported patch.
- Teacher views identify requested style/content, input history, newly supervised assistant messages and unsupervised host results. Legacy pre-tool/post-tool ambiguity is displayed explicitly. Historical assistant wrappers are not presented as verified claims.
- Teacher content categories stay bound to the original controlled setting. The UI offers that setting for explicit selection; mismatched imports and patches fail. Reject the example if its actual content is wrong rather than changing its control label.
- Export/import preserve all nested teacher decisions. Missing, extra, wrongly typed or injected fields fail, including draft imports. Generic approval or a false/pending teacher gate cannot produce an attested teacher approval. Imports still clear attestation, and frozen records/source metadata remain noneditable.
- Teacher rendering requires pinned source card/license evidence, loaded from a one-source sample snapshot or an explicit evidence root. Missing/rehashed evidence cannot bypass the Source hashes. Mixed-source teacher packets require an explicit complete evidence root. This does not manufacture actual account terms or training-use clearance.
- Existing public-source packets and decision patches remain supported. No training release is created by rendering or patch application; the existing publisher and checked train reader retain final authority.

## Verification

- Full local suite: **581 passed / 13 unavailable-CUDA skips**. Focused public-console/teacher-console/bridge suite: **96 passed** before the final added public teacher-field-injection control, which also passes in the full suite. Initial public-console/bridge compatibility checkpoint: 80 passed.
- A synthetic teacher fixture exercises actual DOM event-handler code, pending/false teacher-gate export refusal, explicit completion of all four fields, import field removal, content relabel refusal, stale import, attestation reset and JSON Blob content. Its exported patch passes the Python patch/publisher/read path for one synthetic training record. This is not actual human approval or real teacher training.
- The DOM simulator still accepts only the designated `fixture` source/license metadata. It refuses the actual 40-example/four-source packet before DOM event execution and creates no patch/report for it.
- The actual pending public packet is regenerated with the updated UI at `data/review-console-v3/review.html`, with all four pinned source card/license pairs. The packet remains byte-identical, reviewer null, human attestation false and approvals zero.
- No actual teacher source snapshot or console was fabricated. Fourteen real teacher candidates remain unapproved; their reading worksheet is still `data/teacher/host-bridge-v4/REVIEW.md`. Account/source evidence is still needed before the source-bound teacher console can be built for them.

Evidence: `reports/milestone-twenty-nine-tests.xml`, focused/initial XML, `reports/milestone-twenty-nine-dom.json`, `reports/milestone-twenty-nine-console-evidence.json` and `reports/milestone-twenty-nine-summary.json`. Private synthetic UI/patch/publication controls live under `data/teacher-review-console-fixture-v1/`; these must not be confused with actual teacher approvals.

## Browser and operational limits

- The checks use Node DOM simulation plus static CSP/hash/text-escaping checks. Actual browser layout, CSP enforcement and file-download interaction remain **unverified**. No browser was launched, and no alternate route was attempted after the earlier local-file URL-policy rejection.
- Both actual teacher journals retain their prior state: **17/20 reserved slots**, fourteen successful candidates, sixteen historical actual CLI launches and three unreserved slots. The active journal is not halted. No new real generation/API call, purchase/reset, cloud job, source approval or real-data training occurred. CUDA validation allowances remain USD 7/10, settled charges unknown.
- The full project goal is incomplete. Public source review, account training-use evidence, teacher/style/suite human review, portability-policy choice, production bulk intake/tokenizer and actual language pilots remain open. Next audit the remaining production/training requirements against current evidence; do not count additional fixture mechanics as language learning.

## Using an eligible teacher snapshot

After actual evidence has been supplied and a sample-only teacher snapshot exists:

```sh
.venv/bin/python -m slm.data.review prepare --dataset /absolute/teacher-snapshot --output /absolute/pending-review.json
.venv/bin/python -m slm.data.review_console render --dataset /absolute/teacher-snapshot --packet /absolute/pending-review.json --output /absolute/new-review.html
```

Manually review the pinned evidence and complete the applicable decisions. Export with explicit attestation, apply the patch with `slm.data.review_console apply`, then separately invoke `slm.data.review release`. A draft or incomplete teacher decision cannot publish training data. Ordinary public-source use and `--evidence-root` remain available.
