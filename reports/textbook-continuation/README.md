# New-position English prose continuation

**The frozen local corpus contains 5,057,858 train positions and 301,703 validation positions.** OpenStax and Wikipedia together contribute 48.6% of training positions. Synthetic children's stories make up the other 51.4%. Each position count includes one end-of-document token per excerpt. Each included source document is unique against the named previous feasibility and extended corpora. This measures source novelty for the current run; exposure by separate older models is unknown.

| Source | Train positions | Validation positions | Train excerpts |
|---|---:|---:|---:|
| OpenStax textbooks | 1,260,491 | 91,970 | 11,022 |
| Wikipedia | 1,197,219 | 59,683 | 11,767 |
| TinyStories | 2,600,148 | 150,050 | 14,176 |

The six little-endian uint16 shards, source-attributed document offsets and manifest live under data/balanced-continuation-v1. Manifest SHA-256 is 97ceba8dddcb6f8c289506f54c50dd06e223988b0efa6e85eaf542b6e5f7c48f. Verification reread 39,174 individual documents, checked end markers and decoded text hashes, established disjoint source groups across splits and found zero source-identity or normalized-text matches against 49,071 previously indexed documents. At 1,000 processed positions per second, one full training pass takes about 84 minutes before validation or checkpoint overhead. This source addresses next-token language modeling; conversation accuracy is unmeasured.

## Source decisions

- **OpenStax.** The intake read text, metadata and license files from 24 pinned publisher repositories. The acquisition ledger records 101,603,516 received or conservatively reserved bytes, comfortably below 160 MiB. Title-level collection XML, README disclosures and repository license headers were reconciled. Conflicting evidence excluded Introduction to Business 2e. Only self-contained body paragraphs were eligible. Captions, media, tables, quotes, credit blocks, references, footnotes, code, math markup, outside-source notices and third-party excerpts were excluded. Superscripts and subscripts were dropped at whole-paragraph level after a preliminary sample exposed a flattened exponent. Writing Guide was withheld after an unmarked first-person literary passage appeared amongst ordinary body paragraphs; alternate overlapping editions and Python fragments relying on omitted code were also withheld. Training is limited to local noncommercial use. Exception detection cannot prove every paragraph's authorship. [Per-title rights and attribution](title-dispositions.md)
- **Wikipedia.** The verified local November 2023 English parquet is SHA-256 79ee06627f4ba2fec056fcd23c077a29238bbcbacc3187e8d1a0b47e663e9c7a. Whole source-article families from earlier corpora, prior review samples, public SQuAD eligible training articles and public QuAC train articles were excluded. The extractor selected complete, independently readable paragraphs and preserved each article URL, raw text hash and paragraph offset. Raw rights/contact indicators blocked an entire article; the second review added filters for stale current facts, polarizing claims and missing template values. Preserve article-specific rights and attribution in any separate review. [Pinned source](https://huggingface.co/datasets/wikimedia/wikipedia/tree/b04c8d1ceb2f5cd4588862100d08de323dccfbaa) · [Publisher licensing history](https://diff.wikimedia.org/2023/06/29/stepping-into-the-future-wikimedia-projects-transition-to-creative-commons-4-0-license/)
- **TinyStories.** The previous campaign used data00 and data01 rows below 22,500. The new slice comes from later rows of SHA-verified data01.json; no accepted story duplicates an earlier indexed document or an exact text in data00. The source is CDLA-Sharing 1.0. Document-group separation and five-word near-match screening reduce duplication; many stories nonetheless share recurring characters, opening phrases and tidy resolutions. These are synthetic fictional stories. [Pinned source and license](https://huggingface.co/datasets/roneneldan/TinyStories/tree/f54c09fd23315a6f9c86f9dc80f725de7d8f9c64)

## Quality and limitations

Two hash-selected training paragraphs were inspected from each of 28 candidate textbook titles, plus eight training pieces each from the final Wikipedia and story candidates. Review detected a literary rights exception, stale present-tense economic data, passages on clinical risks, political positioning, duplicated editions and format-dependent answers. These cases or their source were withheld. Samples supply a screening signal; they cannot establish factual accuracy or bound the remaining defect rate. Some passages assume preceding context, and style/domain coverage is uneven. Adult-source prose accounts for 2.46M train positions. This corpus does not meet a 10M-target premise without another source or disclosed repetition.

Chapter groups were assigned to splits before paragraph selection. Wikipedia split by canonical article family; TinyStories split by normalized story. Exact documents and five-word signatures with four shared bottom-16 hashes were conservatively deduplicated; validation candidates receive priority. The source extractor opened no protected project cases. The independent custodian was given the frozen manifest for protected-overlap screening.

## Reproduction

    .venv/bin/python reports/textbook-continuation/intake.py
    RAYON_NUM_THREADS=1 .venv/bin/python reports/textbook-continuation/local.py
    RAYON_NUM_THREADS=1 .venv/bin/python reports/textbook-continuation/books.py
    RAYON_NUM_THREADS=1 .venv/bin/python reports/textbook-continuation/freeze.py --output data/balanced-continuation-check
    RAYON_NUM_THREADS=1 .venv/bin/python reports/textbook-continuation/verify.py data/balanced-continuation-check

The intake caches verified official blobs and hard-stops before the body budget. The included manifest contains source revision IDs, individual shard hashes, provenance index hash, corpus limitations and explicit admission-decision hashes. No GPU was used.
