# PMC offline front-matter preparation

`prepare.py` reads **existing local responses only**. It contains no HTTP client, does not download or admit records and does not change the global acquisition ledger. Only synthetic OAI/JATS fixtures have been processed. No actual PMC record schema, license yield or usable-token count is claimed.

The [current PMC OAI documentation](https://pmc.ncbi.nlm.nih.gov/tools/oai/) identifies the endpoint `https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/`, OAI-PMH 2.0 envelopes, JATS Archiving front matter as `pmc_fm`, full text as `pmc`, and the `pmc-open` set. It describes ten-record `ListRecords` pages and cursor continuation. It requires serial requests, at most 3 requests/s, compression support, and off-peak execution for scripts exceeding 100 requests. This preparation chooses a tighter **1 request/s** limit and **1,200 unique articles**. No retired FTP article manifests are used.

The [JATS permissions documentation](https://jats.nlm.nih.gov/publishing/tag-library/1.4/element/permissions.html) distinguishes article permissions from object permissions and free-to-read indicators from reuse licenses. The [related-article documentation](https://jats.nlm.nih.gov/publishing/tag-library/1.4/element/related-article.html) describes correction/update/other relationships. These explain the tags used by this prototype; live OAI records must still pass shape validation before acquisition/extraction expands.

## Local input contract

The manifest is our own explicit schema, not a claimed PMC response schema:

```json
{
  "metadata_prefix": "pmc_fm",
  "scope": {"from": "2026-01-01", "until": "2026-01-03"},
  "responses": [
    {
      "path": "response-0001.xml",
      "sha256": "<exact existing response SHA256>",
      "request_url": "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/?verb=ListRecords&metadataPrefix=pmc_fm&set=pmc-open&from=2026-01-01&until=2026-01-03"
    }
  ]
}
```

Subsequent response URLs must contain only `verb=ListRecords` and the exact previous `resumptionToken`. Every response hash, OAI request attributes, PMCID/header metadata and datestamp scope must agree. A nonempty final cursor, duplicate PMCID, omitted response, unknown shape, entity/DTD declaration or incorrect hash stops preparation. A CLI failure writes a terminal diagnostic when its new output directory exists. Preserve all original response files: serialized XML hashes are explicitly distinct from original response hashes.

Bounds are 2MiB manifest, 8MiB/response, 128MiB aggregate response input, 2,400 responses and 1,200 unique article records. Output is bounded to 256MiB. These are pilot limits, not a full-PMC harvesting mechanism. If a declared datestamp interval exceeds them, shrink/freeze a new explicit interval before acquiring it; do not silently keep a convenient prefix.

## Metadata filtering and families

Only exact unported **CC BY 2.0/2.5/3.0/4.0** or **CC0 1.0** URIs pass this metadata filter. NC, ND, SA, ported, unknown and spoofed-host links do not. Missing permissions, restrictive/conflicting wording, temporal qualification and object/subarticle permissions hold records. Article-level CC BY does not clear quoted or separately attributed objects. Metadata passing is **not full-text license clearance**: full JATS permissions, attributions and exceptions must be rechecked when the frozen sample is fetched.

The frame preserves PMCID/PMID/DOI, OAI datestamp, response hash/date, journal/title/publication dates, authors, article versions/history, all permissions, explicit conflict statements and related-article XML. It joins shared DOI/PMID/PMCID and related DOI/PMCID targets into connected families, conservatively propagating observed correction/retraction risk. Any unresolved related link holds the record. Absent tags are not proof that a paper has never been corrected or retracted: outside-frame status reconciliation remains mandatory.

OAI `from`/`until` select **repository datestamps**, not publication years. A closed cursor chain is a completed bounded harvest, not proof of an immutable repository snapshot. Publication year/journal/field stratification and late status changes still need explicit reconciliation.

## Sampling and future acquisition guard

`sample_frame` requires the completed frame receipt and exact frame hash. It selects `k` eligible article identities by seeded SHA256 order and records `k/N`, frame hash, seed and full-text request URLs. It performs no requests. It is a uniform article sample, not yet token-weighted semantic acceptance or a statistically representative sample of all PMC. It does not override family grouping for final splits.

`SerialRequestGuard` is pure state logic. It denies concurrency, intervals below one second, nonfinite clocks, exhausted requests/article counts, and U.S. Eastern weekday 05:00–21:00 requests when planned requests exceed 100. Restarts require parent-restored counts, article IDs and last UTC start, preserving rate spacing. Every request, including errors/retries, must pass this guard and be charged in the **parent-owned persistent global ledger before I/O**. The guard returns the required `Accept-Encoding: gzip, deflate` header, but does not implement networking, persistence, compressed-byte limits or disk reservations; future acquisition must integrate those existing parent controls. The guard is not an independent permission to acquire data.

Run `python3 restart/execution-v1/pmc-preparation-parallel-v1/check_synthetic.py` for meaningful malformed-license, object-rights, family-status, frame-integrity, XML safety and request-boundary scenarios. No source files outside this directory are modified.
