# Human-rated conversation SFT candidate measurement

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

Prioritize direct review of a **989-train-dialogue OASST2 candidate pool**, using existing human ratings and top-ranked replies. The pool contains **372,746 hypothetical assistant targets**, substantially more than the 14,065 targets in the preceding considered short-conversation sample. It is a candidate for a finite research SFT experiment; no training admission or launch occurs here.

The initial 50K-conversation plan remains a broad-training hypothesis, not a reason to prohibit every smaller controlled experiment. If content review supports a bounded research policy, test whether assistant-target SFT improves this actual foundation checkpoint before scaling. Do not call a small pilot broad readiness or infer that ratings certify correctness.

## Frozen selection rule

The new separate `slm.data.oasst_sft_screen` starts from the existing, transitively verified foundation research population. Its foundation approval does **not** transfer into SFT approval. Only OASST2 rows are examined; no new download, source mixture, tokenizer, model or teacher generation is introduced.

- Retain complete existing canonical paths and existing splits/groups; no truncation or text rewriting.
- Every raw node must retain publisher English, positive review, non-deleted, non-synthetic origin and no generating-model name.
- Every assistant reply must have integer **rank zero**, quality **at least 0.75** and helpfulness **at least 0.75**, each with at least two ratings.
- Require observed zero-valued spam, language-mismatch, PII, inappropriate, hate-speech and sexual-content labels, each with at least one rating. Assistant nodes additionally require a zero-valued task-failure label. Missing/invalid labels fail the screen. These are subjective publisher observations, not privacy/content certification.
- Require at least 16 assistant targets and at most 2,048 prediction positions with the frozen tokenizer. Shorter conversations retain their actual lengths.
- Exclude whole groups with nonapproval in the newer explicit 64-row SFT review. Older exclusions remain inherited from the checked foundation population.
- Keep **one path per existing split group**, preferring more assistant turns, then higher minimum assistant quality, then a seeded digest. A rejected alternative branch does not automatically reject every other branch, except for the declared known group nonapprovals.
- Freeze a seeded, group-distinct **64-train-dialogue pending review packet**. It is a subset of the screened population, not a representative whole-source sample. No per-row quality decision is assigned automatically.

The module's recorded rule and implementation hashes bind these choices before its successful measurement. No threshold was relaxed after seeing the yield.

## Actual result

Examine **14,585 canonical OASST2 paths**, bound to 29,280 distinct raw nodes in the previously acquired complete ready-tree snapshot. The selected candidate output has **1,176 distinct groups**:

| Existing split | Candidate dialogues | Prediction positions | Assistant targets |
| --- | ---: | ---: | ---: |
| Train | 989 | 415,863 | 372,746 |
| Validation | 109 | 50,201 | 45,396 |
| Test | 78 | 33,897 | 30,815 |

Train turn counts: **675 single exchanges, 311 two-exchange conversations and three three-exchange conversations**. Validation/test remain outside the train review packet and any training inventory. Counts are hypothetical sizing, not new unique knowledge, admitted exposure or completed learning.

Overlapping exclusion signals include 11,064 paths containing a non-top-ranked assistant, 9,659 with low assistant ratings, 6,601 with nonzero flagged labels, 1,227 lacking sufficient assistant ratings and 754 lacking flagged-label evidence. There are 116 paths in prior nonapproved groups, 136 below the assistant-target floor and 35 above context. These counts overlap, apply to paths and are not semantic error rates. A low rating or missing annotation is not a factual-failure judgment.

## Verification and retained attempts

**57 focused checks pass / zero skips**, comprising 25 new rating/boundary checks plus existing candidate/language controls. Coverage includes malformed/nonfinite/boolean scores, missing labels, insufficient raters, nonzero task-failure flags despite good quality, rank/type boundaries, origin eligibility, raw metadata immutability and output-overwrite refusal. See [test receipt](../reports/milestone-fifty-nine-tests.xml).

The actual independent checker reopens every candidate's complete raw path and rating metadata, recomputes masks/counts, checks original parent record equality and all original partitions, proves unique candidate groups, confirms prior nonapproval groups absent and verifies pending-packet membership. The training reader actually refuses the sample-only artifact. Original **26 training runtime hashes remain unchanged**. These controls bind the data mechanically; they do not certify response meaning.

The first measurement attempt fails before output: it compares the acquisition's original descriptor-file hash to the snapshot's relocated descriptor copy. Inspection confirms acquisition hashes the original source file, while the snapshot rewrites relative evidence-file paths. Corrected code verifies the original file hash, independently validates both evidence bundles and compares their source semantics. Initial source/failure and the explicit correction to its preliminary diagnosis are retained under `data/oasst-rated-sft-attempts-v1/`.

The first independent receipt checked splits against screen receipts. The final **v2 receipt** strengthens this to exact equality against every original parent record and partition. Its earlier checker/receipt is retained locally; no measurement, threshold, candidate or source data changes.

Evidence: [final candidate and actual-control receipt](../reports/milestone-fifty-nine-oasst-rated-sft-v2.json). Private artifacts: `data/oasst-rated-sft-candidates-v1/{candidates.jsonl,screening.jsonl,sample.jsonl,report.json,manifest.json}`. All candidate records retain their original research-foundation metadata; neither that metadata nor a sample-only manifest can authorize SFT.

## Reproduction

```sh
.venv/bin/python -m slm.data.oasst_sft_screen \
  --parent data/iteration-two-foundation-research-v1 \
  --snapshot data/iteration-two-oasst2-snapshot-v1 \
  --source-record data/audit-v1/oasst2/source/source.json \
  --prior-review data/iteration-three-sft-review-v2/decisions.json \
  --tokenizer data/iteration-two-foundation-tokenizers-v1/vocab-16384 \
  --output data/oasst-rated-sft-candidates-v1
.venv/bin/python scripts/check-oasst-rated-sft.py
.venv/bin/python -m pytest -q tests/test_oasst_sft_screen.py \
  tests/test_dialogue_candidates.py tests/test_dialogue_language.py
```

The measured output already exists and refuses replacement; the checker can reopen identical retained evidence. Reading/decision recording remains separate. No unreviewed row is silently called an individually approved example.

## Next action

Read and record direct judgments for the frozen 64 complete train dialogues. Distinguish material defects from scope/verification uncertainty and preserve the entire multi-turn path's failures. Decide whether the resulting evidence supports a separately measured bounded SFT research policy; otherwise revise the data strategy without weakening annotations to manufacture yield.

Any subsequent launch still needs checked SFT release/reader support, finite exposure and optimizer settings, a new-plan terminal assessment binding and a complete-step resource preflight. A meaningful completed run must receive its actual raw conversation and direct score before another iteration. Current model remains **5/100 / 0-of-8**. Reviewed teacher, broad English/styles/content settings, learned tools/MCP, actual MLX/CUDA resumed quality and ESCI remain required. No paid activity or budget change; full goal active/incomplete.
