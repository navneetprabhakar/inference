# Disk-backed explicit-row review

Creator: Navneet Prabhakar

## Scope and commands

Review schema v2 stores individual decisions in JSONL and small source/attestation metadata in `header.json`. It approves only the rows carrying explicit successful decisions. It does not infer corpus approval from reviewed samples or introduce a sampled-admission policy.

```sh
.venv/bin/python -m slm.data.review_stream export \
  --packet /absolute/existing-review.json --output /absolute/new-review-bundle
.venv/bin/python -m slm.data.review_stream release \
  --dataset /absolute/frozen-sample --review /absolute/review-bundle \
  --limits /absolute/review-limits.json --output /absolute/new-training-release
```

Legacy export is bounded to 16 MiB. It preserves pending, rejected and approved judgments, reviewer identity and human attestation; it does not invent decisions. The large-corpus path must write its explicitly reviewed entries directly as JSONL rather than constructing a giant legacy packet.

The limits file has exactly these positive integers:

```json
{
  "max_input_bytes": 268435456,
  "max_records": 100000,
  "max_record_bytes": 1048576,
  "max_db_bytes": 1073741824
}
```

`max_input_bytes` sums all files across the frozen snapshot and review bundle during release, or all release files during verification. `max_records` bounds each snapshot/decision/released inventory; row byte limits include the newline. Metadata files are capped at 16 MiB. The main database has a minimum 1 MiB ceiling; journal, temporary sort, output and tokenizer-spool disk space are additional. These are engineering limits, not financial budgets. The reader uses the release's saved limits unless the caller supplies explicit limits to `open_checked`.

## Integrity and approval contract

- `header.json` contains exactly: `version: 2`, `scope: explicit_rows_only`, frozen dataset manifest SHA256, reviewer, human-attestation flag, source reviews, decision-file SHA256 and optional legacy-packet SHA256. The only recognized reviewer name remains Navneet Prabhakar. Source terms, allowed categories and evidence requirements remain unchanged.
- Each JSONL entry contains the original canonical `record`, its `record_sha256`, and the existing `decision` object. The record includes its example identity; duplicate ledger identities fail even when a decision rejects the row. Every reviewed record must exactly match the frozen snapshot at release time.
- Existing strict English/privacy/quality, category, teacher-specific history/style/host semantics and OASST official mapping checks are reused through the same entry validator as schema v1. Pending/rejected decisions remain absent from training. Stronger upstream held-out evidence on rejected rows still constrains approved peers sharing their split group.
- The release binds the header, ledger, source metadata and derived approved rows. Its review receipt explicitly identifies schema v2; v1 receipts are not silently rewritten in an existing release. Changing a receipt changes record identity and requires rebuilding dependent token shards.
- Checked reading replays the ledger into SQLite, computes final group partitions, then checks **every** released shard and exact row coverage before exposing any train-only iterator or lookup. Missing, added, duplicated, changed or moved held-out rows fail even when an attacker recalculates file checksums. Test/validation records never appear in the training mapping.
- `open_checked` exposes an immutable-in-content SQLite snapshot; callers receive newly parsed records, so mutating a returned dictionary cannot alter later lookups. Physical inputs are checked before exposure. The snapshot remains authoritative while open; it is not refreshed if source files change later. The pilot separately pins the source tree and detects mutation during training. Context exit closes/deletes the temporary index without masking the pilot's original error with another source-stamp failure.
- Publication uses a fresh private working directory and a final rename. Failures remove it. A host crash may leave an unpublished working directory. No interrupted-ingest recovery is claimed. Checked reading always revalidates; there is no persistent trusted-index cache.

These checks establish recorded attestations, data integrity and coverage. They do not authenticate who edited a local JSON file, prove judgment quality or settle underlying rights. A checksum is not a human signature.

## Downstream integration

- `training_examples` dispatches v1/v2 releases and keeps sample-only refusal. Legacy JSON review packets remain bounded and materialized within that bound; corpus-sized packets must migrate.
- Pilot preflight uses indexed approved-row lookup and disk-backed duplicate tracking instead of an in-memory record dictionary and identity set. It still re-encodes each approved record and compares actual masks/tokens before backend construction. The added reference source bindings intentionally prevent old pilot checkpoints from silently resuming under changed validation code; use the original code revision for those checkpoints.
- Token shards count retained groups on disk. Dataset verification hashes shards incrementally rather than calling whole-file `read_bytes`.
- BPE intake counts bytes/messages and streams its canonical record-identity digest, then writes only verified training text to a private JSONL spool. The tokenizer can consume that spool on its own worker thread without using a SQLite connection created on another thread. The spool is removed on completion/failure. No full Python text list is retained; the tokenizer library's own vocabulary/word-count memory can still grow with corpus diversity.

This does not make all mixture, lineage, tokenizer-learning or evaluation state globally memory-bounded. It removes these specific materialization points. Production tokenizer selection, representative quality and corpus-wide admission remain open.
