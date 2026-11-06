# Specific error-cause correction and v4 controls

All **422 exposed-development lessons /583 turns** recompiled against scorer SHA256 `7f79ca61facd74a3bfb7ca0e16d31cff3b53618155202f1aa688c599e9176877`. Source replay, identity, policy, context fit and explicit dependencies passed; source-answer controls remain **557 automated passes /26 manual-pending turns**. Compilation took **1.68 seconds**. No source answer or rubric was changed.

The corrected scorer accepts timeout/unavailable/denied/rejected statements only when the actual error supports that specific cause. Generic complete failure/error/no-result acknowledgments remain allowed. Twenty CPU fixture groups pass, including real Chat controls rejecting timeout, unavailable and denial claims after division by zero; actual timeout and service-unavailable acknowledgments pass. Nine compiler-family fixtures and compilation checks pass.

V3's specific-cause false pass is preserved in its separate REVIEW_FINDING.md and ignored review-finding.json. Original v3 frozen artifacts are unchanged; v4 binds that evidence and the corrected scorer. Current freeze hash is `876edcdf5783037eca65940fded2da5405183131ca8af78d5b64df615d44bcc3`. The canonical 422-case hash remains `dbd21270e504df0ae5e2581c42676a2b93a9074b6400245ab1fb5d0e47d2c0f8`, unchanged from v2/v3.

Current receipts are under `data/own-base-tool-dev-rubrics-v4/`. These are exposed teacher-reference and scorer-wiring controls, not model performance or arbitrary semantic certification. Conservative language/call matching remains a diagnostic limitation. No model, GPU, protected case or training admission was involved. The extension compiler owner was notified to create a separate v2 freeze against this scorer without changing extension cases.
