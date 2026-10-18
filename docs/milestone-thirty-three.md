# Disk-backed reviewed-release intake

Creator: Navneet Prabhakar

## Delivered

Review schema v2 replaces giant per-row review JSON objects with an explicit decision ledger and small source/attestation header. SQLite reconstructs approved records and group constraints, then checks complete released-row coverage before exposing train-only iteration or indexed lookup. It preserves the existing row/source/teacher/official-partition gates; it does not approve a corpus from a sample. See the [review contract](streamed-row-review.md).

- Legacy conversion preserves judgments, including pending status. Every successful v2 release binds its exact parent snapshot, ledger and header. Unreviewed rows remain absent. Rejected rows with known stronger partition evidence still protect approved group peers.
- Dataset hashing is incremental. Pilot validation uses disk-backed approved-record lookup and duplicate tracking while retaining full source re-encoding/mask checks. Token-shard retained-group counts move to disk.
- BPE candidate intake streams its identity digest and byte counts, spools only checked training text to disk and feeds a generator to the tokenizer. This removes the full Python text list; it does not bound the tokenizer library's vocabulary/word-frequency state or make every pipeline inventory streaming.
- The [corpus-admission contract](corpus-admission-proposal.md) remains proposed. Its population, deterministic eligibility, family-aware representative audit, error/uncertainty thresholds, source evidence and human acceptance are required before a future policy-admitted release. No thresholds, actual judgments or accepted policy were invented.

## Evidence

- Final local suite: **654 passed / 15 hardware-dependent skips**. Focused review/pilot/tokenizer/shard suite: **84 passed / 3 skips**. New tests cover exact legacy parity apart from the intentionally different versioned receipt, source/category/boolean/scope gates, duplicate review identities, frozen membership, rejected-group protection, budget failures, mutation, cleanup and complete-before-yield refusal of resealed content/coverage tampering.
- Actual tiny synthetic v2 → BPE → token shards → pilot controls execute one optimizer update on each of local MLX GPU and PyTorch CPU. No real public/teacher training or learned capability is claimed. The runner's existing own-resume, cross-backend import and failure-recovery controls remain in the passing suite. No new NVIDIA verification occurred.
- The existing synthetic 11,000-row staging fixture produces a 49,545,964-byte review ledger. Release takes **3.15 seconds**, checked reading **4.56 seconds**, with **51,527,680 bytes (49.14 MiB) process peak RSS** on macOS. The release's peak main database is **104,288,256 bytes**; reader peak is **53,030,912 bytes**. It retains 9,944 train / 540 validation / 516 test records. All judgments are simulated fixture data, not actual human/source approval. Measurements do not establish natural-corpus quality, dense-case performance or a hard RSS ceiling.
- Actual public packet conversion preserves **40 pending decisions, four source reviews, null reviewer and false attestation**. The original packet SHA256 is unchanged. Release fails with the human-review-attestation error and creates no output. Current private bundle: `data/review-stream-public-v1/`; it is not a new review decision or replacement for the current review console.
- Retained failures: initial pilot integration still referenced the removed `seen` set; that became a bounded scalar nonempty check. An exit-time stamp recheck masked the pilot's original mutation error; the checked index now remains an immutable snapshot after full prevalidation, while the pilot's own guards handle ongoing mutation. Tokenizer iteration crossed threads and could not share the original SQLite connection; a private immutable text spool fixes it. New pilot assertions initially used a nonexistent `completed` status and now check the established `update_target_reached` status. Gate thresholds were not relaxed.

## Remaining work

This closes specific intake/materialization gaps, not source approval or production corpus admission. English/privacy/quality eligibility and a representative audit/admission policy remain missing; all 901 actual source candidates and fourteen teacher candidates remain unapproved. Production vocabulary selection, real 1M/10M language pilots, numerical portability acceptance and sustained training remain open.

Teacher transport stays CLI-only, with no new generation/API call/cloud job or credit action. Teacher reservations remain 17/20; conservative CUDA allowances USD 7/10, settled charges unknown. The full project goal remains active/incomplete.
