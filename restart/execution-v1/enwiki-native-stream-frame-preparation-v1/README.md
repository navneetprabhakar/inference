# Native streaming frame prefix pilot — preparation only

Not dispatchable. No XML source bytes have been read. The full archive must first finish publisher verification and external supervision, followed by a freshly pinned parent-reviewed source binding. The template is deliberately invalid.

The once-only metadata preparation froze the first 16 complete index offset groups (1,600 rows), before XML access. Exact prefix: [0, 17,948,470), including the original 570-byte compressed header. The initial 16 MB feasibility failure is retained. Parent explicitly revised the compressed limit to 20 MB; selection and all other limits stay fixed. This is a prefix feasibility result, not a yield estimate.

Limits: 20 MB compressed, 128 MB decoded, 2,000 pages, 16 MB output, 115 worker / 120 external seconds, observed process-tree RSS 1 GB. No network, ledger writes, rendering, tokenization or admission. Namespace-aware Expat rejects DTD/entities; native IDs, models, slots, source spans, text hashes, negative namespace/redirect outcomes and exact index-group order are retained. Every selected BZ2 member must pass complete CRC/EOF checks. The actual XML root stays open: PREFIX_ONLY, with no global XML validity, uniqueness, article, English or prose-yield claim.

43 controls passed: 27 parser and 16 actual synthetic worker/lifecycle/binding cases. Static pin/runtime preflight passed. These controls do not parse the live archive.

Proposed source-verification cost: reuse freshly completed, externally pinned worker and supervisor full-file publisher/local hashes; require exact completed path and unchanged device/inode/size/mtime/ctime before the opened FD and afterward. Independently hash selected compressed segments and verify all-member BZ2 CRC/EOF. This adds zero whole-archive verification reads. Parent must review this custody plan; an additional physical full SHA read would cost 26,668,484,995 verification bytes and needs a separately explicit budget.

Nonexecuting static validation:
```
.venv/bin/python restart/execution-v1/enwiki-native-stream-frame-preparation-v1/pilot.py --code-pins-sha256 0bcc64fc5ee11fc98492328d6660ba57b039485cd7d55632c7e0d38c3a918c95 --profile-sha256 6240f8dc97d9c95a500a3f56ed3c794efb56b23211b8f33f9a87381f3078474e
```
Do not add --execute until parent verifies complete-source receipts, freezes the binding and reviews final limits. No replacement groups or automatic retry are permitted.
