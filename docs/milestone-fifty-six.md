# SFT expansion: measured limits and a pinned short-conversation source

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

Do not treat stricter filtering of the current small source pool as a sufficient route to broad SFT data. The new literal-extraction screen yields only **174 train candidates / 4,717 assistant targets**. Keep that diagnostic and its pending sample, but prioritize a broader short-conversation source from the original plan.

A pinned **200-row train-prefix audit of Smol-SmolTalk** confirms usable message schemas and measures context sizing: **113 fit 1,024 positions, 198 fit 2,048** with the current tokenizer. This is source/schema evidence, not a quality-rate estimate or training approval. No new student updates or teacher generations occurred; the completed foundation baseline remains 5/100 / 0-of-8.

## Literal extraction candidate experiment

`slm.data.extractive_candidates` examines the checked foundation release's existing Dolly rows. It requires a closed-QA/extraction category, a 20–600-word supplied context, a 3–80-word answer that is an exact case-sensitive contiguous span after NFC/whitespace normalization, at most 1,024 prediction positions, and an answer no larger than 80% of normalized context characters. Original messages are never rewritten.

Scope/identity/privacy/structural attention and time-sensitive/advice questions are excluded. Previously non-admitted explicit-review groups are excluded as whole groups. Preserve source splits, retain one candidate per group, and select a pending 64-row train-only review packet across length buckets. These are membership rules, not semantic or factual certification.

Actual results:

| Measure | Train | Validation | Test |
| --- | ---: | ---: | ---: |
| Parent Dolly rows examined | 12,879 | 144 | 164 |
| Group-distinct candidates | 174 | 5 | 11 |
| Prediction positions | 45,257 | 1,291 | 3,952 |
| Hypothetical assistant targets | 4,717 | 116 | 512 |

The raw source contains 15,011 records / 15,003 distinct full-record digests, including eight exact duplicates. The initial attempt rejected duplicate raw identities before creating output. It was corrected to collapse identical raw records for lookup while reporting their count; canonical example IDs/text/splits are unchanged and no duplicate training example is added.

All 190 candidates retain distinct groups; independent checks find no previously non-admitted group and confirm that the pending sample is train-only. The actual training reader refuses the sample-only candidate artifact. None of the 64 pending sample rows has been content-graded here, and no candidate is SFT-admitted. Exclusion-reason counts overlap; they are not factual-error counts.

**12 focused checks pass / zero skips**, including an explicit counterexample where an exact context span answers the wrong question. That passing mechanical candidate remains `semantic_relevance_verified:false`. Exact spans are therefore insufficient to justify source-wide admission; the small yield also fails the intended scale. Do not weaken the rule merely to manufacture a training-size target.

Evidence: [candidate measurement](../reports/milestone-fifty-six-extractive-candidates.json). Private artifact: `data/extractive-sft-candidates-v1/`.

## Broader source inspection

Register the [pinned Smol-SmolTalk source card](https://huggingface.co/datasets/HuggingFaceTB/smol-smoltalk/blob/f73fe857d519ff6ac5af2ea67c4d3834da7b8bcc/README.md), revision `f73fe857d519ff6ac5af2ea67c4d3834da7b8bcc`. It describes short conversations intended for smaller models and lists Apache-2.0; that declaration is retained as source evidence, not a warranty for every constituent or synthetic-generation term.

Existing bounded acquisition retrieves only the **first 200 official train rows**, in two 100-row pages. Both response revision headers match the pinned revision; no partial/truncated cells are accepted. Actual row-response bytes: **810,725**. No test row, full Parquet shard, model weight or bulk corpus was downloaded.

Actual current-tokenizer sizing:

- 200 message arrays serialize; no unsupported shape/role issue observed.
- Role shapes: 115 six-message user/assistant dialogues, 54 single exchanges, 30 system-prefixed exchanges and one system-prefixed six-message dialogue.
- Whole dialogues fitting 512 / 1,024 / 2,048 positions: **67 / 113 / 198**. No truncation or new tokenizer fitting.
- Aggregate hypothetical positions: **181,386 prediction / 135,306 assistant targets**. These are sample sizing counts, not admitted training exposure or unique-token claims.
- Nine retained source labels, including 115 `smol-magpie-ultra-short`, 26 `self-oss-instruct` and 24 `openhermes-50k` rows. Preserve original spellings and per-row constituent identity.
- Prefix selection is neither random nor representative. Do not project its context-fit proportions, quality or source mix to the complete dataset. Full content reviews remain zero at this boundary.

The [pinned upstream composition card](https://huggingface.co/datasets/HuggingFaceTB/smoltalk/blob/5feaf2fd3ffca7c237fc38d1861bc30365d48ffa/README.md) identifies the core generator as Llama-3.1-405B-Instruct. It describes new components as Apache-2.0 and directs existing components to their own licenses. The retained [generator-license snapshot](https://raw.githubusercontent.com/meta-llama/llama-models/1f0feb795a4130697ced243fb53051670d591653/models/llama3_1/LICENSE) contains conditions concerning model naming/use when applicable models are distributed or made available. Applicability to this downstream dataset and eventual model release remains a source-specific question; this audit grants no automatic approval or agreement acceptance. It does not require changing the project's creator credit.

Evidence: [pinned source/schema/sizing and provenance receipt](../reports/milestone-fifty-six-smol-source-inspection.json). Source card, license, raw rows, acquisition pages, upstream card and generator-license bytes/hashes are retained under `data/smol-smoltalk-audit-v1/`. The public source page was inaccessible through the search browser; bounded direct public HTTP retrieval and revision checks succeeded. No credentials were used.

## Reproduction

```sh
.venv/bin/python -m slm.data.extractive_candidates \
  --parent data/iteration-two-foundation-research-v1 \
  --raw data/dolly-complete-v1/rows.jsonl \
  --acquisition data/dolly-complete-v1/acquisition.json \
  --prior-review data/iteration-three-sft-review-v2/decisions.json \
  --tokenizer data/iteration-two-foundation-tokenizers-v1/vocab-16384 \
  --output data/extractive-sft-candidates-v1
.venv/bin/python scripts/inspect-smol-smoltalk.py
.venv/bin/python scripts/check-smol-source-provenance.py
```

Initial output directories are already present and are not silently replaced. The provenance checker can recheck the pinned evidence against the saved inspection; it does not approve rows. Source/profile revisions and hashes must remain explicit on future acquisition.

## Next concrete work

1. Read a group-aware content sample of the short-conversation source, retaining per-constituent relevance, factuality, style, privacy and instruction-following judgments. Do not confuse these 200 schema checks with 200 expert content reviews.
2. Resolve constituent-specific admission for a bounded private research slice; preserve official test rows and establish grouping/deduplication before any bulk preparation. The top-level license label alone is insufficient evidence for the mixed source.
3. Measure 1,024 versus 2,048 training-context memory/throughput on the actual target backend before choosing a whole-dialogue context limit. A 1,024 cut discards many rows in this prefix; silently truncating away conversation context would repeat an observed limitation.
4. Freeze sufficient SFT data, controlled exposure/replay, optimizer settings and new-stage terminal diagnostics/conversation binding before meaningful new student training. A 174-row extraction slice or 12-row approved control cannot substitute for the planned broad conversation model.

All 26 original training references remain unchanged. No new model update, teacher/model API call, cloud job, paid training or budget change. Public dataset HTTP acquisition is separate from the CLI-only teacher. Broad English/styles, SFW/mature settings, reviewed teacher, learned tools/MCP, actual MLX/CUDA resumed-training quality, deployment optimization and later ESCI remain required. Full project goal active/incomplete.
