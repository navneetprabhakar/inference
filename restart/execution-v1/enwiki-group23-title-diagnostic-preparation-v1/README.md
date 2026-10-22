# Group 23 title identity diagnostic — preparation only

No retained source bytes have been opened or decompressed. Parent dispatch and independent review are required.

This is a separate diagnostic, not a retry of failed calibration v1. Its original 22 durable groups/2,200 pages and all receipts remain unchanged. The diagnostic reads exactly the actual header [0,570) and selected complete BZ2 group 23 [24,391,408,25,767,196), totaling 1,376,358 compressed bytes. The parent hypothesis is raw XML entity escaping in the upstream index title lexeme; no decoder/normalization is applied here.

Observed local pages 1..100 are mapped explicitly to frozen global index ordinals 2201..2300. IDs/order must match; title literal equality or difference is recorded, not normalized away. Output contains only titles, IDs, expected raw-line hashes, native raw-page XML hashes/coordinates and bounded metadata/CRC receipts. Raw-page coordinates belong to the concatenation of the actual header plus group23, not the original global decoded offset. No wikitext/text or full semantic revision objects are written.

Reuses pinned semantic SAX v3/raw span v4. The original header and target group are separately CRC/EOF checked; strict real root remains open, no invented closing tag. Terminal source custody is the separately authorized TLS/ETag/local-prefix fresh-hash/stat class, never whole-publisher verification. Exact old v3 source is O_RDONLY|O_NOFOLLOW and stat checked before/FD/during/after; only two exact reads are permitted. No full-prefix rehash, GET, ledger writer, tokenizer, training or admission.

Limits: 32MB decoded, 100 pages, 30s worker/45s external including preflight/postflight, 256MB observed owned-tree RSS, 4MB output, zero retries. Strict RSS parser requires live positive root/worker entries. Preallocated terminal slots are included. Existing output refusal preserves prior evidence. Parent must kill/reap owned process group after a supervisor SIGKILL; Python finally is not universal crash recovery.

Eight synthetic checks cover literal title escaping and local/global mapping/raw page SHA, native ID mismatch, truncation/CRC/trailing data, decoded cap, exact read ranges and strict RSS. All checks and a nonexecuting 46-pin static preflight passed. Synthetic read fixture is unrelated temporary data; no retained bytes read.

Static command:
/Users/navneetprabhakar/Documents/git/image/inference/.venv/bin/python -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/enwiki-group23-title-diagnostic-preparation-v1/pilot.py --profile-sha256 1d54b02a684c5ef668831145c2225fa3bcd70f7f8f2afae5eb69f5dab20d165b --code-pins-sha256 5a9be08c7c3e129e39db714a33cdfcc240419ed9e0929863ae7278c8a5c5bed9

Parent-only once-dispatch command, not executed:
/Users/navneetprabhakar/Documents/git/image/inference/.venv/bin/python -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/enwiki-group23-title-diagnostic-preparation-v1/pilot.py --profile-sha256 1d54b02a684c5ef668831145c2225fa3bcd70f7f8f2afae5eb69f5dab20d165b --code-pins-sha256 5a9be08c7c3e129e39db714a33cdfcc240419ed9e0929863ae7278c8a5c5bed9 --execute
