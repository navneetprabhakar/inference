# Offline source-review console

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

An offline console makes the pending source/sample review usable without editing immutable records or hashes. It displays all **40 examples**, four pinned dataset cards/license texts, upstream references, local/upstream partitions and the existing review fields. It exports **decision-only patches**, with explicit human attestation and no automatic approvals. Public training approvals remain **zero**.

Local suite: **468 passed / 12 unavailable-CUDA skips**, including 15 focused console tests. JavaScript DOM simulation verifies event handling and export content on synthetic fixtures. Actual browser rendering/download behaviour remains **unverified**: the browser tool rejected the local `file://` preview under its URL policy. No alternate browser surface or HTTP workaround was used.

## Review the current packet

Private generated artifact: `data/review-console-v2/review.html`, bound to `data/official-split-audit-v1/pending-review.json` and `data/official-split-audit-v1/curated`. Its four source-evidence pairs are checksum verified against the pinned source descriptors under `data/audit-v1/`.

1. Open the saved HTML manually in a local browser. It contains unreviewed full text and should remain private. No server, account sign-in, external asset or network request is required by the console.
2. Inspect each source's pinned card, license label/text and upstream origins. Record approval/rejection/pending status, terms review, permitted categories and an evidence note. Embedded license text is provenance evidence, not a determination of all upstream rights or obligations.
3. Review examples individually. Set English/privacy/quality decisions, category, upstream partition evidence and approval/rejection. Existing OASST machine-mapped partitions are locked. Local validation/test protection remains authoritative at publication.
4. Export a draft with attestation unchecked to save partial work. Use **Resume decisions** to import the patch into the same console; stale/different packets are refused and attestation stays unchecked until explicitly set again. There is no browser storage/autosave; export before closing.
5. After actual review, check the named attestation and export decisions. Provide the saved patch path. Approved totals are review decisions, not counts of train-eligible records; held-outs can reduce the training subset to zero.

The HTML itself does not change the source packet, publish a release, train a tokenizer/model or approve future corpus intake. Tests' synthetic attestation fields are not human review of the real sources.

## Apply and publish separately

Run from the repository root. Fresh output paths are required.

```sh
.venv/bin/python -m slm.data.review_console apply --dataset data/official-split-audit-v1/curated --packet data/official-split-audit-v1/pending-review.json --patch PATH_TO_EXPORTED_DECISIONS.json --output data/reviews/reviewed-decisions.json
.venv/bin/python -m slm.data.review release --dataset data/official-split-audit-v1/curated --review data/reviews/reviewed-decisions.json --output data/reviewed/bootstrap
```

`apply` checks the original packet/dataset binding, complete inventories, strict decision fields/types, categories, notes and machine mappings. It copies only decisions into a new packet. Attested candidates must pass the existing review validator before materialization. Unattested drafts can be saved but the publisher still refuses them. `release` remains the authoritative frozen-record/source/hold-out boundary and the train reader still yields only accepted train records.

Rebuild the console after changing its bound packet; an exported draft can be materialized then used as the next rendering input. To regenerate the current console at a fresh location:

```sh
.venv/bin/python -m slm.data.review_console render --dataset data/official-split-audit-v1/curated --packet data/official-split-audit-v1/pending-review.json --evidence-root data/audit-v1 --output FRESH_PRIVATE_FOLDER/review.html
```

This is a reference review aid for **1–200 examples / at most 16 sources**, not a production bulk-review system. JSON inputs are bounded to 16 MiB, evidence files to 2 MiB each and notes to 8,192 UTF-8 bytes. The underlying bootstrap reader still materializes its snapshot. Calibrated production quality/privacy/language gates and bulk release remain open.

## Rendering and integrity boundaries

- Source data is base64-embedded JSON and inserted with `textContent`, never interpreted as HTML. No external scripts/styles/fonts, fetch, browser storage or source-content editing is included. Inline script/style hashes form the generated CSP, with network connections disabled; static hashes are tested, actual browser CSP enforcement is not verified.
- Decision patches bind the complete original packet and contain no record/source-provenance replacement fields. Rehashed modified records are still rejected against the frozen snapshot. Duplicate JSON keys, integer-as-boolean approvals, unknown categories, incomplete attestations, missing inventories and stale patches fail before output.
- A negative probe against the actual **unattested** packet confirms that changing an OASST mapped partition is rejected without output or mutation. Source/example decisions remain pending and original hashes are unchanged.
- Attestations are explicit fields, not cryptographic identity or proof of correct human judgment. The console cannot establish factual quality, licensing clearance or actual review completion by itself.

## Evidence and next action

`reports/milestone-twenty-three-console.json`, focused/full test XML, DOM simulation report, real-packet tamper guard and source/artifact-hashed summary retain the scope. The synthetic JavaScript export is materialized and published through the unchanged Python checks in tests; no public record is approved or published. Raw HTML, synthetic patches and fixtures stay ignored under `data/`.

The browser-policy rejection prevents visual/browser acceptance claims, but does not change the file artifact or Python gate results. No new teacher generation, API fallback, cloud job, numerical-policy decision or language pilot occurred. CUDA allowances remain **USD 7 of USD 10**, settled charges unknown. Actual source decisions, portability-policy selection and teacher/suite reviews remain required before dependent training work.
