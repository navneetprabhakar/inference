# Canonical Wikibooks DOM rendering shards — prepared, not launched

The frozen canonical manifest contains89,758 candidates from89,951 source occurrences. It preserves all occurrence mappings and historical alias/root edges. This stage renders those exact selected records; it does not select new versions or relabel licenses.

Four fixed source-ordinal ranges cover the complete frame once:

| Shard | Source ordinals | Expected canonical candidates |
|---|---|---:|
|1|1–22,488|22,458|
|2|22,489–44,976|22,461|
|3|44,977–67,464|22,476|
|4|67,465–89,951|22,363|

Each worker reads the immutable archive sequentially to its range end, rendering only canonical source ordinals assigned to that range. Selected record hashes/locations, page/revision/title/URL, original HTML and wikitext hashes and original license metadata must match the pinned canonical manifest. The existing fixed v3 cleanup and DOM renderer are retained, including the nested-navigation fix, formula/table/superscript/dependency holds, exact code whitespace and all prior holds. Candidate family IDs inherit the complete historical-alias graph.

`rendered.sqlite3` stores rendered text once plus compact provenance and block hashes/character offsets; it does not rewrite original HTML or wikitext. Commits batch at100 candidates or2MB serialized payload. Four shards avoid a unique-page-ID collision from valid historical versions because the parent-reviewed canonical manifest already resolves them.

Per-shard fixed limits remain900seconds,1GB aggregate output,1GB observed process-tree RSS stop threshold (512MB target),12GB actual decoded bytes and4MiB parsed records. The original independent supervisor, fixed terminal slots, output/disk checks and shared `CLOCK_MONOTONIC` binding remain. The durable locked aggregate ledger reserves900seconds per shard, at most four unique attempts and3600seconds total; completed/failed reservations are not refunded. Combined disk preflight conservatively reserves all four1GB outputs plus20GiB free floor and16GB weights, and accounts existing intake against64GB.

These are **four independent supervisor entrypoints**, with serialized durable reservations. No multiworker launch driver or combined4GB RSS observer has been added. The parent can choose sequential execution or provide a joint process-tree observer before launching concurrently. Individual observed1GB thresholds alone do not prove absence of simultaneous transient4GB peaks. No real shard has been launched.

For shard1 the documented command is:

```sh
python3 restart/execution-v1/wikibooks-sharded-render-preparation-v2/supervisor.py --archive restart/execution-v1/m2-intake/wikibooks-rendered-pilot-v1/enwikibooks-NS0-20250320-ENTERPRISE-HTML.json.tar.gz --shard 1 --output restart/execution-v1/m2-intake/wikibooks-sharded-render-v2/shard-1
```

Change only shard ID/output suffix for2–4. Output paths are fixed under the aggregate root; no retries are permitted. Parent review/dispatch is still required.

A complete shard receipt requires exact expected candidate membership, integrity and output hash. Shards1–3 are explicitly bounded prefixes against the already verified complete identity frame, and do not claim whole-archive EOF. Shard4 verifies archive EOF/CRC. A global complete-render claim requires all four supervised complete receipts and the exact89,758-identity union.

**Every shard remains provisional.** Global cross-shard block/family reconciliation is still required, followed by language, exact/near/family/protected deduplication, rights/attribution, factual/semantic review and frozen sampling gates. There is no per-shard global dedup/ownership assertion. Rendered byte/character lengths remain distinct from pinned-tokenizer content-token weights; the eventual200 token-proportional draws require the latter. No data admission, split assignment or training occurs here.

Checks:12 shard/ledger fixtures,30 renderer cases and7 real child-process clock checks pass. Canonical rule checks and complete-frame independent verification are saved separately. Full-source attempts v1–v3 and prior discovery outputs remain unchanged.


New v2 adds crash-durable aggregate updates (file fsync, replace, directory fsync) and durable worker-group ownership registration. Rendering worker/core/renderer are byte-for-byte unchanged from frozen v1. The isolated joint launcher at `wikibooks-joint-render-launcher-v1` now provides the four-worker driver and joint4GB RSS/930second observer described in its own README. No actual shard has been launched.
