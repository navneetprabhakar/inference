# Extended corpus readiness

**A 2.5M-target local trial fits the reviewed corpus.** A fresh student can consume up to 640 distinct-position updates at the feasibility pilot’s mixture, or 2,621,440 targets. Wikipedia is the limiting source. A 100M-target proposal would require a materially larger admitted source pool or explicitly declared repetition. This corpus measures next-token learning in two genres. Its contents provide little direct evidence about conversational transfer.

| Final v3 shard | Documents | GPT-2 positions including EOT |
|---|---:|---:|
| Encyclopedia training | 10,538 | 1,476,586 |
| Encyclopedia validation | 565 | 79,927 |
| Narrative training | 18,309 | 3,413,324 |
| Narrative validation | 980 | 181,823 |

- **Artifact.** The four little-endian uint16 shards and per-document attribution index are under `data/extended-trial-v3`. Manifest SHA-256 is `e3b7f3ed6ef0e42fe61f3e4e35179cdf177324de86f90d2df01d41d37d8f50fe`. Its manifest records raw, shard and attribution-index hashes, revision IDs, split salt, guard-set hashes and filter counts. The document index records source transformations. Together the training shards contain 4,889,910 positions from distinct accepted documents. The 9/7 mixture uses only 2.62M of these before its Wikipedia stream runs out.
- **History.** The older whole-article Wikipedia extraction found 19 readable documents in its first 30 quality reviews. This trial starts over from the verified raw file hash, extracts continuous English lead paragraphs, preserves original article URLs and full raw-text hashes, and excludes notices and contact indicators found anywhere in each raw article. Pilot families, previously sampled source IDs and protected exact/near matches are excluded. A provisional 6.78M-position v1 extraction failed sample review on a health/addiction biography and visibly missing quantities. V2 removed biographical and sensitive cues. The v2 sample exposed a missing wingspan and broken parenthesis. V3 removes those patterns and preserves the other 22 Wikipedia review records.
- **Review.** An assistant read the complete final 24 sampled encyclopedia leads and 12 fictional stories. All 24 leads supplied readable exposition with several awkward or promotional phrases. Eleven stories supplied coherent narrative. In the twelfth, whispering resolves a character's inability to hear. This sample was used to repair the Wikipedia filter and is a development-quality check. It provides no independent factual certification. See `REVIEW_PROTOCOL.md` and `review.json` for criterion, evidence and limitations.
- **Overlap.** No exact document, normalized duplicate or canonicalized group crosses final splits. Every offset, EOT boundary and shard hash was verified independently. The eight-word scan automatically rejected overlap with authored conversation turns/rubrics. The near-match screen conservatively drops documents sharing four out of 16 bottom-hash five-word shingles with a previously seen document. The 100,000 records in old story shard zero are protected against exact matches. These tests can miss paraphrases or story-template families. The style concentration, repeated openings, stale facts and synthetic narrative logic warrant per-source metrics and actual completions.

## Source disposition

**Wikipedia.** The 20231101.en parquet has SHA-256 `79ee06627f4ba2fec056fcd23c077a29238bbcbacc3187e8d1a0b47e663e9c7a`. It retains Wikimedia URL and page ID per article. The pinned dataset card lists CC BY-SA 3.0/GFDL. The local reconciliation records the June 2023 transition to 4.0 and article-specific exceptions. Raw records, selected page URLs, transformation notes and source hashes remain available for attribution. Treat this as a limited local research admission. Imported notices can be absent from a cleaned snapshot. No redistribution or model-license conclusion was made. [Pinned Wikipedia dataset](https://huggingface.co/datasets/wikimedia/wikipedia/tree/b04c8d1ceb2f5cd4588862100d08de323dccfbaa) · [Wikimedia license transition](https://diff.wikimedia.org/2023/06/29/stepping-into-the-future-wikimedia-projects-transition-to-creative-commons-4-0-license/) · [Wikimedia terms](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use)

**TinyStories.** The pinned card specifies CDLA-Sharing 1.0. The build verifies both extracted JSON file hashes against the previously verified archive metadata. It selects only rows 2500–22499 of `data01.json`, preserving the story field verbatim. Source shard zero is reserved. The final narrative streams are reproducible from the two sources and their document indexes. [Pinned TinyStories dataset](https://huggingface.co/datasets/roneneldan/TinyStories/tree/f54c09fd23315a6f9c86f9dc80f725de7d8f9c64)

**Other available material.** The 19 historically admitted Gutenberg and Wikibooks units pass their individual file hashes and sum to 130,786 GPT-2 target positions. Their previous custody is train-only and mostly literary narrative. They are excluded from this trial. The broader Gutenberg 300-book raw intake has incomplete unit admission. The local Cosmopedia candidate intake previously counted 39.3M positions under a different tokenizer and retained uncertain seed-source provenance and factual quality. Raw volume was excluded from the proposed budget. See `legacy-admitted-counts.json` for the independently recounted units. [Cosmopedia source card](https://huggingface.co/datasets/HuggingFaceTB/smollm-corpus/blob/3ba9d605774198c5868892d7a8deda78031a781f/README.md)

## Reproduce on this workspace

Use a fresh output path for each build. The scripts run offline and require the verified tokenizer assets, the pilot document index and the local validation/confirmation metadata created in this run. The corpus process reads protected cases solely for overlap filtering. Training should consume named shards only. The native-source grouping and substring filters do not establish semantic independence from every historical benchmark.

```sh
.venv/bin/python reports/corpus-readiness/build.py data/check-extended-base
.venv/bin/python reports/corpus-readiness/refine.py data/check-extended-base data/check-extended-final --tighten
.venv/bin/python reports/corpus-readiness/audit.py data/check-extended-final --salt audit-20261105-trial-v2
```
