# Global finalizer preparation — not executed

This code requires a separately parent-frozen complete-input recipe after the residual profile is terminal and independently verified. It must not finalize the current partial frame. Inputs are read-only SQLite databases, including recovered NEW copies when original rollback journals are hot. Original shards/HTML/text are never rewritten.

The NEW internal recipe protocol contains:

- `status`: `PARENT_FROZEN_COMPLETE_RENDER_INPUTS_NO_ADMISSION`
- `oversize_identity_reconciliation_complete`: true
- `source_frame_complete_and_hash_verified`: true
- `expected_candidate_count`:89758
- `canonical`: absolute path and SHA256 of immutable canonical.sqlite3 (fixed7ff502...)
- `identity_reconciliation_receipt`: absolute path and SHA256 of the independently verified29-record supplement manifest
- `shards`: path/SHA256 pairs of all independently verified immutable old and residual SQLite inputs, maximum16

Parent reviews and externally pins the exact recipe SHA256. Supervisor and worker both require it, alongside an externally pinned exact code registry. Empty/partial/extra code inventories fail closed. The command is intentionally incomplete until parent freezes actual complete inputs:

```sh
python3 restart/execution-v1/wikibooks-global-finalizer-preparation-v3/supervise.py \
 --recipe <parent-frozen-complete-input-recipe.json> --recipe-sha256 <reviewed-recipe-sha256> \
 --output <new-absolute-intake-output> --code-pins-sha256 <readiness-code-pins-sha256>
```

For every active canonical row the finalizer checks exact source provenance, original captured license metadata, full rendered text hash/length and every stored block offset/hash. It rejects duplicate source ordinals or an incomplete active candidate union. It derives a common family from the parent-frozen canonical aliases, retains every structural/prior hold, and processes deepest pages first with binary title/page/ordinal tie breaks. A held page never acquires ownership. Exact text duplicates receive global holds; substantive blocks at least80characters receive whole-page overlap holds within the common family. A page held by overlap does not acquire its other blocks. Repeated blocks inside one page do not create self-overlap.

Cross-family substantive-block groups and exact-text groups are reported across all rows, including held rows; these are separate from within-family ownership. Family membership is joined from page metadata, not duplicated per block. Stored block hashes use32-byte BLOBs (inspect with hex(hash)); only substantive blocks are copied, while every source block is verified. This is global structural reconciliation, not language/rights/factual approval or train/split admission. No tokenizer is loaded and no usable-token claim is made; provisional content tokens require stable later filters and the pinned M1 tokenizer.

Resource caps:900seconds total (stop work at895 with5seconds cleanup reserve),1GB aggregate output including receipts/journals,1GB observed whole process-tree RSS,20GiB free floor plus16GB weights reserve,64GB combined intake ceiling. SQLite cache4MiB, main DB maximum100,000pages of4096bytes (409.6MB; a lower internal ceiling to leave journal/receipt room), WITHOUT ROWID key tables, and in-memory temporary query state avoid hidden unlinked disk temp files. Supervisor observes memory/disk every0.5seconds and kills/reaps the separate-session worker on limits or failed observations. Transient RSS between observations is not proven absent. On any limit or error preserve partials; no retry or cap extension.

Output is metadata/holds/ownership/groups plus bounded receipts. Full text and HTML remain solely in immutable input shards/source archive. Partial result and source evidence must be preserved, with copy recovery if needed.36synthetic/control checks pass; no real corpus finalization has run.

V2 parses one byte buffer checked against the externally approved recipe SHA, enforces a1MiB recipe bound, and rechecks that same digest before completion. A mid-run recipe change prevents complete status. V1 is preserved and superseded.

V3 additionally requires outer SQL page/revision identity to equal the immutable payload identity before any output insertion. Both mismatch regressions fail closed; the deliberate effective-family override remains. V1/v2 are preserved and superseded.
