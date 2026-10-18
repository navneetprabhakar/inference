# Non-admitting quality signals and group sampling

Creator: Navneet Prabhakar

## Purpose and invocation

`slm.data.quality_audit` measures a frozen canonical snapshot and selects whole split groups for review. It does not rewrite records, reject individual rows, certify English/privacy/content quality or produce a training release. All output is sample-only and the checked training reader refuses it.

```sh
.venv/bin/python scripts/setup-language-audit.py --output /absolute/new-detector-directory
.venv/bin/python -m slm.data.quality_audit \
  --spec /absolute/audit-spec.json --output /absolute/new-audit-directory
```

The specification contains `dataset`, `descriptor`, `limits`, `seed`, `groups_per_stratum` and `window_characters`. Dataset/descriptor paths resolve relative to the specification. Current example specifications are saved with the private run artifacts. Limits explicitly cover input/row bytes, record/window/stratum/sample counts, main database pages, detector output bytes and process time. Oversized selected groups abort the sample; the command never cuts a family to fit a budget. SQLite journals, sort spill and output files require additional disk. Process output/time enforcement polls and may overshoot between observations; it is not a total machine resource guarantee.

## Offline detector and evidence

The optional dependency is the official fastText v0.9.2 C++ CLI, pinned to commit `5b5943c118b0ec5fb9cd8d20587de2b2d3966dfe`, with the compact `lid.176.ftz` model. The [publisher documents 176 languages, the compressed model and CC BY-SA 3.0 model license](https://fasttext.cc/docs/en/language-identification.html). Code licensing is separately [MIT](https://github.com/facebookresearch/fastText/blob/v0.9.2/LICENSE). The setup retains hashed source/model/card/license evidence and compiler/binary provenance under the chosen local directory. Full license text comes from the [Creative Commons official repository](https://github.com/creativecommons/cc-legal-tools-data/blob/a0dac18d1a773b4cdb7d8dd5d9bf4efab7901030/legacy/legalcode/by-sa_3.0.html).

Research references: [Bag of Tricks for Efficient Text Classification](https://arxiv.org/abs/1607.01759) and [FastText.zip: Compressing text classification models](https://arxiv.org/abs/1612.03651).

- This pretrained model is an offline audit dependency. The student still initializes randomly; student training/inference has no fastText dependency.
- Setup performs explicit bounded public downloads and a local C++ build. Auditing itself only executes the pinned local binary/model and has no network fallback. Separate binary hashes are expected after compilation on different platforms; an Apple audit is not Linux binary validation.
- Every original message is covered by contiguous character windows, including short or code-containing messages. Newline/carriage-return characters become spaces only in detector input. No prefix-only sampling or silently truncated tails are claimed as whole-record detection.
- Windows without alphabetic content are explicitly unscored. The CLI can return fewer labels than requested; zero/one results remain visible as missing/incomplete evidence. Prediction-line coverage is still exact. Invalid labels, scores, extra/missing lines, crashes, timeout or artifact changes abort publication.
- Raw scores are retained without treating them as calibrated confidence. Small upstream numerical overshoot above one is recorded, not clamped; the parser rejects nonfinite values and values outside its explicit numerical bound. No acceptance threshold is selected.

## Privacy and quality measurements

Privacy candidates cover email, contextual/international phone patterns, credential/bearer/private-key patterns, identity/address contexts and validated IPv4 literal syntax. Reports retain counts and bounded positional offsets, not matched values. All occurrences are counted; only the first twenty locations per pattern are retained. Names, physical addresses, IPv6, national identifiers and many other sensitive forms remain unresolved. IP literals can be technical examples rather than personal information. Pattern presence and absence are both insufficient for privacy clearance.

Quality measurements include character/UTF-8 size, alphabetic/control/replacement characters, word diversity/frequency, repeated lines, URLs, markup candidates, code fences and structural/cleaner attention. These are features, not coherence, correctness, style or mature-content grades. Profanity and slang are not automatically removed. Existing text and labels remain unchanged; language/privacy/quality/content assessments remain unverified for every record.

## Sampling design

1. Use the frozen `split_group` as the cluster. All records of a cluster must share their assigned partition; inconsistent cross-partition groups abort.
2. Assign each group one stratum using source, task, content label, partition and maximum member character-length bucket (0–255, 256–2,047, 2,048+). Mixed source/task/category groups receive explicit mixed tags. These descriptive buckets are not quality thresholds.
3. Rank groups by SHA256 of the explicit seed and group identity, with identity tie-breaking. Select the first `min(k, N)` groups in each stratum. Under the pseudorandom-hash sampling assumption, group inclusion probability is `min(k, N) / N`; record inclusion probability is that of its group.
4. Include every retained row in a selected group. Report group populations/sample counts, record counts, per-source coverage and probabilities. Rows are clustered and are not independent uniformly sampled observations. Mixed-source groups can belong to multiple per-source coverage counts; group-stratum counts remain disjoint.

The input population must be frozen before selecting a seed/sample. Reproducibility does not prove representative upstream acquisition. The current four-source input was acquired first-N; sampling its 674 groups is conditional on that snapshot and cannot estimate errors across the full upstream corpora. No quality rates, confidence intervals or corpus-admission decisions are computed. A future accepted policy must address coverage, family weighting, rare slices, error definitions and uncertainty explicitly.

## Artifacts and remaining work

The flat checked manifest binds parent snapshot, detector descriptor and implementation to `signals.jsonl`, `sample.jsonl`, source metadata and the report. Samples include original record hashes, selection details and null judgments; they are distinct from the existing forty-example review packet. Source/input/code stamps are checked through publication. Failure removes the private working directory; a host crash can leave an unpublished directory. There is no resumable scan or persistent trusted cache.

Actual human adjudication, source rights, detector calibration on representative conversational text, broader privacy coverage, quality/content classifiers and accepted population admission remain open. Follow the [proposed admission contract](corpus-admission-proposal.md); these measurements cannot bypass it.
