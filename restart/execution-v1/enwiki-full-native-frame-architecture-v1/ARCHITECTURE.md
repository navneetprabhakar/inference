# Full native XML metadata frame — architecture proposal only

**A complete occurrence frame is feasible within a 4 GB metadata budget using packed records and sorted identity maps. Runtime and full decoded size remain unmeasured. Do not raise the current Framer's caps and reuse it unchanged. No producer or source operation is authorized by this document.**

## Scope and authority

The completed, publisher-verified index contains **25,792,234 rows / 257,960 offset groups**. These are not proven unique pages, articles, English documents or usable prose. The native prefix measured 1,600 page occurrences / 66,627,771 decoded bytes in 3.0705 seconds. It did not validate the whole XML document or prove global identity uniqueness.

Execution requires a later parent-reviewed full-source profile: actual COMPLETE virtual-archive manifest, worker and independent supervisor receipt SHA256 pins, exact ordered components/stat custody, publisher 26,668,484,995 bytes/MD5/SHA1 and matching independent full local SHA256. Reuse the audited VirtualArchive helper; never instantiate it against a live/candidate/failed publication. The helper opens source components read-only with NOFOLLOW and validates descriptor/path/stat identities. Its stored component digests are provenance, not newly rehashed by every guard.

No concatenate-to-new-27-GB-file, network request, model, tokenizer, rendered corpus or admission. Existing full-download and prefix profiles stay immutable.

## Recommended storage

Use a tiny SQLite job/checkpoint database, **packed all-page occurrence records plus persistent sorted page-ID/revision-ID maps** for the large frame. A full SQLite identity/frame design remains a reasonable alternative, but its actual row/index/journal footprint must first be measured with its exact schema. No claim that SQLite necessarily fails the budget; its capacity is currently unproven. The packed design has an explicit byte bound and preserves duplicate occurrences rather than aborting on UNIQUE constraints.

- `pages.metadata.bin`: fixed 84 bytes per index occurrence, seekable by `(ordinal-1)*84 + fixed header`.
- Fields: uint64 page ID; uint64 first source revision ID (0 if missing); int32 namespace; uint32 flags/model-intern ID; uint32 revision count; uint64 single-supported-main text UTF8 length (explicit sentinel if unavailable/ambiguous); uint64 decoded page start within source group; uint64 raw page XML length; 32-byte raw page XML SHA256. First revision is a locator, **not a canonical-version choice**. Multiple revisions retain all IDs separately and hold body-selection ambiguity.
- `groups.metadata.bin`: fixed 96-byte records including original compressed header group, compressed start/length/SHA256, decoded group base/length, first index ordinal/count, member count/validation flags. Ordered contiguous ranges cover every compressed source byte, including the actual final root closing bytes.
- `ns0-nonredirect.ordinals.bin`: uint32 ordinals of **all** namespace-0 nonredirect occurrences, including deleted/missing/unsupported/oversized/multiple-revision/identity-held cases with their flags. This is a seekable source frame, not an eligible-body or English frame.
- Persistent page and revision maps: packed `(uint64 native ID, uint32 source ordinal)` pairs, externally sorted by `(ID, ordinal)`. All occurrences retained. Adjacent equal IDs yield exact duplicate-group/unique-ID counts; no highest-revision or first-occurrence selection. Duplicate memberships remain discoverable from the maps without materializing unbounded JSON reports.
- Extra-revision span file, exception/model dictionaries, actual source header/siteinfo, counters, checksums, bounded diagnostics and local checkpoint state. Full titles, wikitext, author names, comments and source body strings are **not duplicated for 26 million occurrences**. They remain recoverable from immutable index ordinal and original page/group locator+hash. Contributor/attribution and every revision remain in the unchanged source page; last-editor fields are not full contributor history or rights clearance.

All-page identity and role records come before any model/text-presence filtering. Unknown model/format/schema, missing/deleted text, large text and ambiguous revisions remain explicit. Redirect presence is exact; redirect-target family resolution is a later source-bound step, not silently certified here. A later unit reader must recover complete native page attribution/redirect/context and verify its page hash before rendering or admission.

### Capacity arithmetic

At 25,792,234 rows, 84-byte records cost **2,166,547,656 B**. Header+257,960 group records cost 24,764,256 B. Worst-case namespace vector costs 103,168,936 B. The completed page map costs 309,506,808 B. A revision cap of 30,000,000 gives 360,000,000 B per revision-map copy.

External sort runs are built and merged **one map at a time**, in 500,000-pair RAM batches. During revision-map merge, retain page map + revision runs + revision final. With 128 MB extra-revision spans, 128 MB exceptions and 64 MB state/receipts, peak planned disk is **3,643,987,656 B**, leaving 356,012,344 B below the 4,000,000,000 B hard limit. This assumes the stated packed schema; implementation must prove record sizes and worst-stage file accounting synthetically before launch. Finished sort inputs are removed only after fsynced final-map/checkpoint publication. Sources/prior evidence are never deleted. No duplicate full frame or unconstrained SQLite/temp sort outside the profile output.

Use fixed-size output structures/length checks, prewrite total accounting, terminal reserve, bounded cache, and all temp/journal/sort files inside the same cap. Source/input/index remain existing files. Do not spool the 1.226 GB decoded index. At the parent's planning footprint (~42 GB existing + ~9 GB future tail + <=4 GB new metadata), nominal combined intake is ~55 GB; launch must measure real allocated/current bytes and enforce 64 GB combined intake plus **53,474,836,480 B** weights/scratch/free reservation. These are estimates, not a fresh disk observation.

## One continuous source pass

1. Verify the actual completed virtual publication/triple pins and index completion/publisher/local hashes. Freeze code/runtime/limits. Read one index group ahead with bounded UTF8/raw-line buffering; retain exact raw index-line hashes and ordinals. Existing measured maximum is 100 rows / 12,165 raw bytes per group, but implementation uses explicit bounded line/group guards and must finish all 25,792,234 rows.
2. Read original compressed header then every index-delimited group sequentially via VirtualArchive, up to 1 MiB compressed reads. Stream each complete BZ2 member with <=64 KiB decoded delivery; require CRC/EOF and no trailing junk in every group. Accumulate full compressed MD5/SHA1/SHA256 during this same pass and compare against the completed publication at EOF: no second 27 GB source pass solely for guard hashes.
3. Maintain a single namespace-aware Expat parser over the **actual continuous XML document**. DTD/entities/external references forbidden as in the tested parser. Original root/siteinfo/namespaces/header retained. At end require actual root closure and final `Parse(b'', True)`; no invented header, namespace or closing tag. Group boundaries must fall outside active pages and match every index row's numeric page ID/title/order exactly.
4. Replace the tree/list retention with one active-page SAX state machine. Hash decoded text incrementally and compare byte counts/native text SHA1 and, where unambiguous, sibling revision SHA1. Track direct IDs/contributor/revision/slots/schema flags without retaining body strings or whole page trees. Current `pages`, `ids`, `revids` global sets disappear.
5. Hash raw XML incrementally using Expat byte boundaries and a bounded unconsumed-byte window. At complete closing-page callback, record exact page span/SHA256. Each feed hashes consumed raw bytes and discards them; retain only an incomplete lexical-token tail. An 8+ MB page of normal escaped text therefore does not require an 8+ MB buffer or abort by page size.
6. Validate a whole group's page/index coverage before durable group commit. Emit fixed metadata records and namespace ordinals; update counts by namespace, redirect, model/format, text presence/deletion, revision multiplicity, supported SHA comparisons and review-hold class. Flush bounded batches and clear every emitted page/group object.
7. After native/index EOF, build sorted identity maps from metadata only. Preserve/report duplicates instead of failing or discarding history. Independently reconcile record sizes/counts, ordinal coverage, map sorting/membership, model/namespace counters, source/index EOF and all artifact hashes before COMPLETE publication. Final metadata verification reads outputs/index metadata, not a second full native-body parse.

## Oversized and malformed records

Normal oversized article/text: continue streaming raw/text hashes, roles and byte counts; retain the exact page locator/hash and a large-body diagnostic. Do not drop it or call it usable. A later bounded renderer may hold its entire body; no truncation to force eligibility.

Oversized scalar metadata: compare title directly against the bounded expected index title; hash/spans retained for comments/other nonidentity fields without storing full values, with explicit metadata/schema hold. Unexpected valid subtrees are hashed/located and held, not deleted or expanded. Exact names/model-count dictionaries and exception storage are finite; hitting their limits produces a PARTIAL inventory, not unreported coalescing or lost pages.

Unsupported/ambiguous native identity cannot be skipped while claiming index coverage. uint64 overflow, irreconcilable title/page/index mismatch, invalid XML, DTD/entity, CRC/truncation, pathological >1 MiB incomplete XML token, source mutation or exhausted decoded/time/RSS/output bound stops PARTIAL with last durable group and explicit unresolved coverage. Do not regex-search for `</page>` to skip an unsafe region. Ordinary large text is distinct from an unbounded lexical token/attribute.

## Proposed finite bounds, not authority

Full source: exact 26,668,484,995 compressed bytes; **256,000,000,000 decoded XML bytes**, exact 25,792,234 index-row/page occurrences and 257,960 groups, <=30,000,000 revisions; 1 GB observed owned-tree RSS (512 MB target); 4 GB output including journals/temps; **55,800 worker / 57,600 external seconds** including sort/finalization/preflight; serial parser worker plus supervisor. Deadline/RSS snapshots fail closed; source publication/stat pins rechecked. Partial results preserve counts/last durable group, never become a complete/frozen sample frame. No automatic resume or cap extension.

These are deliberately finite proposed ceilings, not observed full XML size or ETA. Prefix-ratio extrapolation suggests ~99 GB decoded / ~4,562 seconds. Per-page extrapolation suggests ~49,497 seconds. They disagree because the first 16 groups are not a representative cost sample; the new engine's per-row cost and disk maps remain unmeasured. No namespace/English/quality ratios are extrapolated.

Before freezing production time, an optional separately bounded **128 complete index-group engineering calibration** (<=12,800 rows, <=256 MB compressed / 2 GB decoded / 570 worker +600 external seconds /64 MB output /1 GB RSS) can validate streaming memory/oversized-page handling and actual metadata/sort cost. Its exact index endpoint must be frozen from metadata first; no automatic continuation into the full run. It remains a prefix feasibility test, not a source-quality sample. Parent may adjust the full proposed budget only before dispatch, based on evidence.

## Implementation sequence after architecture review

- Choose packed maps versus measured compact SQLite. Do not implement a full producer before parent architecture decision.
- Build isolated SAX/raw-hash stream core plus synthetic boundary/oversize/unknown-schema/revision tests; source frame/multimap formats and finite-budget supervisor. Prove fixed-record sizes, sort peak, duplicate preservation and no text retention.
- Pin actual completed virtual publication and helper triple metadata only after completion. Root/independent review before any retained-source operation.
- Optional bounded calibration; freeze final one-run profile. Run/verify complete occurrence inventory; then design native body extraction, language/token counts, quality, component rights, redirect/family/leakage and split work separately. **No foundational-model size/training decision from namespace counts.**
