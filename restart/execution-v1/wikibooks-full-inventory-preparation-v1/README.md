# Full-source Wikibooks inventory implementation

**Ready for parent code review. No full-source inventory has been launched.** Prior discovery outputs remain unchanged. `supervisor.py` is the execution entrypoint; `inventory.py` requires its live direct supervisor parent and original monotonic start time.

The fixed production bounds are **12,000,000,000 actual gzip-decoded bytes**, **1,000,000,000 aggregate output bytes**, **900 seconds**, **500,000 encountered nonblank records**, **4,194,304 parsed-record bytes**, and **64 tar members** with names up to4,096 UTF8 bytes. The independent supervisor observes the whole process tree every0.5seconds, reports a **512,000,000-byte RSS target**, and stops at an explicit **1,000,000,000-byte observed RSS threshold**. Sampling cannot prove transient peaks between observations absent. The target is not misrepresented as a hard memory limit.

Both supervisor and worker verify code pins and source SHA256. The supervisor covers archive hashing, parsing, SQLite/family finalization and final verification within the original900second interval. Code uses no network client, model operation, auto retry or continuation after a terminal stop.

The reader streams tar headers and body bytes directly. It validates header checksums, rejects paths/types it cannot safely handle, and never extracts tar paths. Headers, body bytes, padding and trailing bytes all consume the same decoded budget. Normal records are parsed only under4MiB. Oversize records are consumed in64KiB chunks, hashed in their entirety and held without parsing, guessing identities or splicing text. A cap or failure in midrecord produces a partial-prefix hash labelled incomplete. Blank records are excluded explicitly. Exactly reaching a record cap remains partial; it never becomes an EOF claim.

A complete result requires **both terminal tar zero blocks, all members consumed, zero-only trailing tar padding, gzip EOF/CRC verification, every encountered record represented, complete family/block finalization, SQLite integrity and an immutable inventory SHA256**. Unknown schema, duplicate identities, malformed JSON, unexpected tar extension/type or any bound stops closed with partial evidence. No probability sample is taken here.

`extraction_core.py` is a separately pinned copy of v4 extraction with one additional link-metadata export from the same parsed DOM. No second BeautifulSoup/DOM parse is performed. It preserves v4 dependency/navigation/renderer holds and inherits all prior v3 holds for exact matching identities. Original HTML and fulltexts are transient per-record values only; the inventory stores original line/hash/location, IDs/revisions/title/URLs, HTML/wikitext hashes, original license metadata, template/link ancestry, rendered text hashes/character+byte lengths, structural blocks and holds in bounded-cache SQLite. Rendered lengths are **not tokenizer token weights**.

Potential third-party copyright/license notices are retained as up to16 exact span/hash review flags **per source kind**, from rendered text and original wikitext. They are not blanket rights decisions. The existing captured Motorola code notice on page251051 is explicitly checked. Author/quoted/translated content and CC BY-SA3.0/4.0 reconciliation remain outside clearance.

Each record reserves conservative SQLite metadata/index/journal overhead before insertion. Actual files are checked after commits. Cache is4MiB, temporary files remain inside the new output directory, and no later unbounded index construction occurs. A **1MiB terminal reserve** is excluded from working output. Worker/supervisor result files use fixed preallocated384KiB/128KiB slots, overwritten in place without growing at a stop. Terminal metadata is bounded; oversized metadata produces a compact partial receipt rather than a false complete result. Member names in summaries are bounded displays plus exact hashes; full names remain in record provenance.

Preflight conservatively charges **all existing intake files** against the64GB processed ceiling, then reserves the full1GB output allowance. It checks20GiB free floor plus16GB future weights plus output space. The supervisor also observes the combined intake ceiling during execution. These local read-only checks do not mutate the parent global ledger or spend network budget.

`check_synthetic.py` covers30 scenarios, including actual synthetic tar/gzip corruption and full EOF, oversize/cap behavior, unknown schemas, compact identity preservation, overlap finalization, no-growth terminal receipts at a full output cap, notice provenance, known captured Motorola notice, global processed reservation and supervisor time/RSS decisions. The source archive is not scanned by these tests. Only the previously retained95-record discovery evidence is read for the targeted notice regression.

After parent review, an explicit launch would use the existing system `python3` environment containing BeautifulSoup/lxml:

```sh
python3 restart/execution-v1/wikibooks-full-inventory-preparation-v1/supervisor.py --archive restart/execution-v1/m2-intake/wikibooks-rendered-pilot-v1/enwikibooks-NS0-20250320-ENTERPRISE-HTML.json.tar.gz --output restart/execution-v1/m2-intake/wikibooks-full-inventory-v1
```

This command is documented only; it has not been executed. Completed inventory would still require parent review before a frozen source/sample policy, tokenizer weights or admission.
