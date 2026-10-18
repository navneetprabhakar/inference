# Bounded source audit and curation foundation

Creator: Navneet Prabhakar

Date: 18 October 2026

## Result

A working local audit pipeline now acquires small pinned public samples, normalizes records, reconstructs complete conversation trees, redacts selected identifiers, groups duplicates before splitting, protects prior held-out snapshots and publishes deterministic JSONL shards with checksums. **It is an audit foundation, not a production data release.**

- Tests: **57 passed, 2 CUDA checks skipped locally**.
- Four sources pinned with source revision, card hash, canonical license-text hash, upstream references and `sample_only` status in `configs/source-audit-v1.json`.
- 200 records from each source: 800 input records, including 200 complete OASST ready-tree exports. These expand to 903 candidate examples and 901 retained examples.
- Per successful audit: 3,189,558 sample-response bytes, plus small cards/license files. Verification repeated small reads; this is not aggregate session bandwidth. No corpus-scale download, paid teacher call or cloud job.
- Combined snapshot: 822 train candidates, 47 validation candidates, 32 test candidates. These are curation partitions, not evidence of model quality.
- One malformed-encoding example and one credential-pattern example were rejected. Twelve email occurrences were redacted. Redaction is an incomplete privacy check.
- OASST contributes 303 English paths. Shared message exposure is capped at eight paths per tree; exposure is not a count of unique training tokens.
- All 901 retained examples have unreviewed content labels; 398 have unknown language labels. Declared English is also not a language-classifier result. No example is cleared for training by this audit.
- Byte-identical independent rebuilds passed with fixed inputs and implementation. Machine-readable evidence: `reports/milestone-four-tests.xml` and `reports/milestone-four-data-audit.json`.

## Sources and observed schema

| Source | Probe | Adapter and restrictions |
| --- | --- | --- |
| [FineWeb-Edu](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu) | First 200 rows, sample-10BT/train | Prose; preserve upstream URL outside model input; ODC-BY recorded |
| [UltraChat 200K](https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k) | First 200 train_sft rows | Explicit message roles; synthetic upstream provenance retained; MIT recorded |
| [Dolly 15K](https://huggingface.co/datasets/databricks/databricks-dolly-15k) | First 200 train rows | Instruction plus supplied context, then response; CC BY-SA 3.0 recorded |
| [OASST2](https://huggingface.co/datasets/OpenAssistant/oasst2) | First 200 complete ready-tree JSON records | English branches, ranked leaves, full root-to-leaf context; Apache-2.0 recorded |

These first-row/tree probes establish schema compatibility and expose local defects. They are not stratified quality estimates. License registration records evidence and obligations for later review; it does not clear underlying material or synthetic-generation terms.

Viewer samples must report `X-Revision` matching the registered commit and must not contain partial or truncated cells. OASST flat row slices are refused: a slice can contain all parents yet still omit descendants. Instead, a bounded gzip-prefix reader accepts complete nested JSON lines from the pinned ready-tree export. Explicit child lists, parent/root identities, duplicate IDs, role ordering and cycles are validated. Filtering a language/deleted turn discards its descendant branch rather than removing context from the middle.

## Curation and leakage controls

- NFC text normalization preserves meaningful punctuation, slang, quantities, negation and internal whitespace. Bad encodings, control characters, empty/incomplete conversations, repeated-line boilerplate and credential-like patterns are rejected.
- Exact hashes encode message boundaries and preserve code indentation. Text containing apparent role markers cannot forge a different message sequence for exact deduplication.
- Email and contextual phone patterns are redacted. IPs, names, addresses, contextual identifiers and other secrets require broader detection and review. Identifying source-specific message metadata is omitted.
- Exact duplicates are removed. Jaccard similarity of word/punctuation shingles groups near duplicates across complete content and prompts. Near matches remain separate: changed numbers, negation, code or answers may matter. The observed 598 grouped pairs include shared OASST prompts; this is not a count of duplicate examples removed.
- Conversation roots, exact/near matches, prompt variants and explicit global `family:` identifiers form connected groups before split assignment. Official held-out rows dominate train candidates. Upstream train pools may be subdivided into local validation/test.
- A prior frozen snapshot imports held-out reference examples into duplicate checks. This catches a new source copying an old evaluation item with a different ID. Removed duplicate families remain protected, and frozen examples cannot silently change content.
- `heldout-groups.json` alone protects known family IDs; use **`--frozen-dataset` for extensions** so cross-source exact/near contamination is also checked. Frozen references remain outside training and tokenizer input.
- Shards, source records, report and held-out group map are published through a temporary directory and rename. Existing outputs are refused. Manifests include input-content hashes, implementation hashes, Python/Unicode versions and output checksums. This is atomic publication, not a power-loss durability guarantee.

## Reproduce

From the repository root and the existing environment:

```sh
.venv/bin/python scripts/audit-data.py --output data/audit-reproduction
.venv/bin/python -m pytest -q
```

To reuse verified acquisitions without further downloads, run `scripts/audit-data.py --cached-input data/audit-reproduction --output data/audit-replay` with the same Python environment. Cached evidence and row hashes must match; modified caches fail before output publication.

The first command uses the pinned registry, explicit public downloads capped at 500 records per source, at most 4 MiB per ordinary response and 4 MiB of compressed OASST prefix. It freezes evaluation from the three non-tree sources before importing OASST, then checks an independent rebuild. Use a fresh output directory. Revision/header/card mismatches fail; inspect them rather than editing expected hashes to force a pass.

For a custom local import, supply a JSON spec list:

```json
[{"source_record":"data/source/source.json","path":"data/sample/rows.jsonl","adapter":"messages","official_split":"train"}]
```

```sh
.venv/bin/python -m slm.data.build --spec data/spec.json --output data/extended --frozen-dataset data/audit-reproduction/curated
```

Adapters: `messages`, `prose`, `dolly`, `oasst`. Source evidence files are required and their bytes checked. Official split names must be explicitly mapped to `train`, `validation` or `test`; the raw upstream split is retained in acquisition evidence. Run `slm.data.build.verify(path)` before consuming a snapshot. Raw/curated content is ignored by Git; source pins, code and compact aggregate reports are committed.

## Remaining gates

- Broader English identification and quality filters calibrated on informal language, with false-rejection audits.
- Privacy detection beyond patterns and human review of accepted samples; content labels and allowed mature-category scope.
- Complete upstream origins/terms review; OASST ready-tree IDs mapped to upstream official partitions before training admission.
- Reviewed canonical-example ingestion and review-evidence records. The current CLI creates unreviewed audit examples; `--training-release` correctly refuses them.
- Scalable corpus deduplication and storage: the reference curator is capped at 10,000 examples and 32 MiB per local audit input. Its inverted shingle index can become quadratic for repetitive corpora.
- Stratified source samples, remaining planned adapters, source-mixture/token inventories, production tokenizer and tokenized shards.
- Tokenizer training, teacher augmentation and model training must consume only approved training partitions. No production consumer is implemented yet; the manifest release flag must be enforced when those consumers are added.
