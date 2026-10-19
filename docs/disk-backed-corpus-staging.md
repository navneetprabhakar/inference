# Disk-backed corpus staging

Creator: Navneet Prabhakar

Status: sample-only engineering foundation. Corpus admission, representative quality review and production training remain separate requirements.

## Command and contract

Run `.venv/bin/python -m slm.data.staging --spec /absolute/staging.json --output /absolute/new-directory`. Input paths resolve relative to the specification. The output must not already exist.

```json
{
  "inputs": [{
    "path": "canonical.jsonl",
    "sha256": "<actual file SHA256>",
    "source_record": "source/source.json",
    "adapter": "canonical"
  }],
  "limits": {
    "max_input_bytes": 67108864,
    "max_records": 12000,
    "max_record_bytes": 65536,
    "max_shingles": 4096,
    "max_pair_checks": 2000000,
    "max_db_bytes": 1073741824
  },
  "seed": "slm-splits-v1",
  "shard_size": 1000
}
```

- Supply actual pinned source descriptors and matching local card/license evidence. Existing JSONL adapters support canonical records, prose, message conversations, Dolly and reconstructed OASST trees. This command does not fetch data or read arbitrary Parquet/gzip inputs.
- OASST trees require the existing verified official partition projection, supplied through `partition_map` and `partition_map_sha256`. Canonical OASST records retain the existing per-tree proof checks. Teacher bridge records retain provenance checks; staging never grants output-use permission.
- Optional `frozen_dataset` imports prior validation/test records and held-out family constraints. Every frozen source needs explicitly supplied matching evidence. Existing frozen identities cannot change content or provenance, disappear through cleaning, or override stronger held-out partitions. Repeated incoming identities abort, including rejected rows.
- Original train labels may be subdivided. Prior locally assigned validation/test labels and protected evaluation contexts remain held out. Exact protected-context checks do not prove semantic decontamination. Restaging retained canonical rows can change group digests or move additional train rows into held-out splits because the original removed duplicate identities are unavailable.

## Grouping and publication

- SQLite holds records, union-find components, feature postings, candidate pairs and exposure counts. Current storage interns each complete 32-byte SHA256 shingle once; posting/prefix rows use integer IDs. Separate full-text/prompt frequency counters preserve type-specific global ordering. Per-record scratch tables batch dictionary/member insertion with explicit selective join order. Python retains one bounded record/signature at a time plus explicitly bounded source/frozen metadata and counters.
- Normalize and redact with the existing reference cleaner. Group by family, exact normalized message fingerprint, normalized first-user prompt, or full/prompt five-token-shingle Jaccard at least 0.85. Near variants remain distinct records. Exact duplicates retain the frozen representative first, then the strongest official partition, then lexical example identity, matching the reference curator.
- Feature ordering uses global document frequency and digest tie-breaking. A set of size `n` contributes its first `n - ceil(0.85*n) + 1` features to candidate lookup. The selective current-record lookup precedes posting expansion through an explicit cross-join order; writes commit in batches of 256 records, with no crash-resume claim. Length bounds filter impossible pairs; full set intersection verifies every candidate with integer arithmetic. This implements basic lossless prefix filtering described in [Efficient Similarity Joins for Near Duplicate Detection](https://cgi.cse.unsw.edu.au/~lxue/WWW08.pdf), not the paper's complete optimized algorithm. SHA256 feature/fingerprint collision resistance is assumed; grouping is syntactic, not semantic.
- Hard record, byte, signature, candidate-comparison and main-database page limits abort the entire publication. `max_input_bytes` sums explicit JSONL input files; imported frozen rows additionally consume the shared record/signature/database limits, and each frozen line has the same byte limit. No sampled comparisons, truncated records or partial corpus are released. Metadata is limited to 16 MiB per metadata file, 2 MiB per source evidence file, 1,024 input bindings/content labels, 128 bytes per content label and 10,000 shards per split. The database limit excludes the separately reported per-record scratch database, SQLite journals, sort spill files, output shards and total process memory; provision additional free disk. Wall time and peak RSS are observations, not hard limits.
- Input/evidence file stamps are checked through publication. Output shards, source evidence, held-out families and reports receive a checked manifest; the new output directory appears through a final rename. Failure removes the private working directory. Host crashes can leave a hidden working directory; its presence is not a valid release.
- Every output is `sample_only`, `training_eligible: false`, and `source_rights_approved: false`. The reviewed-train reader refuses it. Output manifests include physical input paths; this staging artifact does not promise path-independent manifest identity.

## Remaining work

Representative source/quality admission, broad privacy and English detection, semantic contamination analysis, resumable ingestion, direct columnar/compressed streaming and representative natural-corpus performance remain unimplemented. Review and tokenizer readers still use bootstrap materialization. Do not substitute a synthetic staging result for a production corpus or a learned language pilot.
