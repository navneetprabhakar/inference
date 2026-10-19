# Small complete-source acquisition

Creator: Navneet Prabhakar

`slm.data.snapshot` acquires one complete root JSONL file only when pinned publisher metadata fits an explicit ceiling no greater than 24 MiB. This is a sample-only acquisition path; it creates no training release or source approval.

```sh
.venv/bin/python -m slm.data.snapshot \
  --source-record /absolute/source/source.json \
  --filename databricks-dolly-15k.jsonl \
  --max-bytes 25165824 --output /absolute/new-acquisition
```

- Source evidence must already be pinned and pass the existing card/license verifier. Excluded sources are refused. The repository ID, revision and root filename determine the public endpoint; no credentials or mutable-main fallback are used.
- Inspect exact-revision file metadata before download. Require published LFS SHA256, matching metadata sizes and a file below the explicit limit. Non-LFS files and multi-file/Parquet/compressed acquisitions are outside this path.
- Stream bytes into a private directory; refuse over-size, incomplete, changed-hash or timed-out payloads. Publish only after copied source evidence also verifies. The download wall limit is checked between reads, while the underlying request has its own timeout/retry behavior; it is not a hard total-time guarantee across connection setup/retries.
- Retain the complete original bytes, published metadata, original input-descriptor byte hash and copied card/license evidence. Copied descriptor serialization may differ, but its pinned `Source` values must match. Reproducibility depends on hashes, not the current contents of a mutable URL.
- Failure removes the temporary publication directory. No partial directory is a valid acquisition, and the path is not a resumable bulk downloader.

`scripts/prepare-complete-dolly-audit.py` is a pinned, source-specific experiment. It counts exact raw-object duplicate occurrences on disk, stages unique raw identities through the existing adapter and lossless grouping rules, carries all prior heldouts, and runs the non-admitting quality audit. Source categories are recorded as upstream metadata; they do not become content/style grades or model text.

`scripts/prepare-complete-source-review.py` packages the selected whole groups into the existing 200-record console capacity, with no group split across parts. A separate master packet remains pending. Rendering is not human review or browser validation, and source/sample decisions do not admit an unsampled population.
