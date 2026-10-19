# Bounded Parquet row-group intake

Creator: Navneet Prabhakar

Date: 19 October 2026

## Result

The new range reader extracts **1,000 complete FineWeb-Edu source documents** from the pinned first Parquet row group, using **6,060,554 successful response-body bytes** instead of downloading the **2,152,819,114-byte shard**. All **200 existing viewer-prefix records match exactly** and all **18 ancestral heldout assignments remain preserved**. The extracted documents contain **1,176,756 actual student-BPE content tokens**.

This is an acquisition milestone. No row is admitted for training, no split is reassigned, and no student gradients, teacher calls or cloud resources occur. All 1,000 documents are from the 2013 crawl; this prefix is not representative of the broader source. The prior four-crawl audit and its exclusions/deferrals remain authoritative for those reviewed rows.

## Implementation

Separate `slm.data.parquet_ranges` leaves historical readers, numerical runtime and training entry points unchanged. Each request precharges a finite request/body allowance, including one byte for excessive-body detection. HTTP 206, exact content range, strong pinned entity tag, identity encoding and response length are checked. An ignored range is refused before reading the body. Transport errors are sanitized to avoid temporary signed redirect URLs; no automatic retry or whole-file fallback occurs.

Header, trailer and bounded footer requests establish metadata. For a selected row group, validate row count, declared uncompressed sizes, internal column offsets and compressed span before fetching its payload. External column files are refused. A seekable retained-interval view permits PyArrow to read only acquired bytes; a gap fails instead of creating another request. Decode one group without read threads or prebuffering, then check actual Arrow table bytes and row count. Repeated extraction of a completed group is refused by the reader instance.

PyArrow's footer deserialization limits are set through `ParquetFile`. They are metadata limits, not a general decompression sandbox. See [official ParquetFile API](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html). Declared uncompressed sizes are checked before decode, but actual table-size checks happen afterwards: this implementation **does not impose a hard process-memory or hostile-codec bound**. Do not claim otherwise or use it for arbitrary untrusted uploads. Process isolation/resource enforcement remains necessary if that threat model is introduced.

The reusable transport's budgets are per instance. The actual acquisition wrapper additionally creates its output directory exclusively and publishes the finite plan before network access, refusing an implicit second execution at the same location. A future multi-group publication job still needs durable overall work accounting, checkpoint/recovery and retained lineage; this one-group probe is not that publisher.

## Actual execution

`scripts/probe-prose-rowgroup.py` binds the pinned inventory, revision, source implementation, script, original heldouts and selected group before access. It snapshots the executed reader and limits this invocation to **four requests /8 MiB body allowance**, one 1,000-row group and a 16 MiB serialized-output cap.

| Observation | Actual value |
| --- | ---: |
| Header/trailer/footer/payload requests | 4 |
| Successful body bytes | 6,060,554 |
| Reserved body bytes including overread allowance | 6,060,558 |
| Row-group payload interval | 3,034,185 bytes |
| Actual decoded Arrow table | 5,242,415 bytes |
| Retained JSONL bytes | 5,633,631 |
| Full probe including comparison/token counts | 5.96 seconds |
| Process lifetime peak RSS | 180,109,312 bytes |

RSS is macOS process lifetime high-water memory, not incremental reader memory. Network body counters exclude redirect/protocol overhead. No whole-shard hash is independently recomputed. Successful range hashes are original execution receipts; the offline check does not replay HTTP responses or independently authenticate the whole source.

Private exact source rows, executed-source snapshot and plan/results live in `data/fineweb-parquet-rowgroup-audit-v1`. Raw articles are excluded from Git. `reports/milestone-sixty-eight-rowgroup.json` contains compact execution evidence and hashes.

## Validation and next step

**13 focused tests pass.** They cover real fixture extraction, forbidden gaps, repeated groups, ignored-range refusal before body access, changed entity/range/encoding/length, short/excess bodies, finite byte/request allowances, declared and actual decoded-size refusals, and sanitized no-retry transport failure. The initial development run had three failures because `read_metadata` does not accept the selected deserialization keywords; using the documented `ParquetFile` constructor fixes that API error before the live probe. Original failed receipt remains under ignored `data/`; the final receipt is committed. The actual live probe succeeds once without replay.

A separate offline actual-data check reopens every retained row, reconstructs source-group/raw-record hashes, verifies all original heldout assignments and exact 200-row viewer equality, recomputes student-BPE counts, and binds code/plan/test/report bytes. It passes. These checks establish acquisition fidelity, not document truth, privacy clearance or training approval.

Next: apply content/language/privacy/boilerplate screening and existing exact/near-duplicate grouping to a finite pinned intake; isolate protected requests and preserve all ancestral heldouts; make an explicit bounded research-admission decision before a training release. Preserve known exclusions and deferrals across intake. Do not convert raw prose into artificial assistant examples or label unread rows individually verified.

The latest fitting-control branch remains **10/100, zero of eight conversation tasks**, with its failed fitting criterion preserved. The prior SFT branch remains separately 5/100. Accepted useful MLX/CUDA resumed-learning comparison remains open. The main-training budget question is pending, existing CUDA-validation money remains separate, and no new spending is inferred. After the next completed training iteration, conduct and directly score the actual raw-history conversation before advancing. Full original project goal remains active/incomplete.
