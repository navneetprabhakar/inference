# OpenAssistant upstream-train review — 16 November 2026

**Two useful candidates retained; none admitted to training.** This is a small,
traceable supplement for a future English curriculum, not a complete curriculum
or evidence that Own's current weights have improved.

## Selection and provenance

Source: OpenAssistant/oasst2 at revision
`179dd21fc55192153d94adb0e0ce8f69e222bf75`.
https://huggingface.co/datasets/OpenAssistant/oasst2
https://github.com/LAION-AI/Open-Assistant

The pinned card declares Apache-2.0. Each retained message was matched byte-for-byte
to the pinned training parquet, with tree/message identifiers and text hashes.
The entire source tree must appear exclusively in upstream train; validation trees
are excluded BEFORE review. Both retained trees satisfy this check. Source metadata
marks every path node English, reviewed, not deleted and non-synthetic; assistant
nodes have rank zero. These fields support provenance but do not independently
prove contributors never used AI. No generator-model provenance is asserted.

Source hashes and download URLs remain in:
- reports/english-source-checks-v1/source-receipts.json
- reports/english-source-shortlist-v1/downloads.json
- reports/english-source-shortlist-v1/oasst-card.md

The selector scanned 13,854 tree records, excluded 692 non-train trees and 17
previously exposed train trees, then found 324 eligible short keyword-matched paths.
Selected one path per tree in deterministic hash order. Review expanded in three
batches of 16, stopping after 48 complete conversations / 96 assistant responses.
This adaptive, filtered discovery sample is not a population quality estimate.
All selected text was read; out-of-scope medical/science/code answers were marked
for exclusion without pretending to have independently verified their facts.

## Retained examples

| Key | Lesson | Assistant turns | Supervised targets | Tokens, tools-enabled |
|---|---|---:|---:|---:|
| T12 | Graduation gift suggestions, acknowledgement and closing | 2 | 162 | 567 |
| T44 | Ask for context, then offer measured relationship support | 2 | 130 | 579 |

T12 offers optional ideas rather than claiming purchases, inventory or prices.
Its closing is generic and adds limited state supervision. T44 does not assume
why James is distant or promise an outcome; it encourages discussion and listening.
Both are grammatically usable and relevant as written. Original wording is retained;
no rejected answer was rewritten and labelled human-authored. These are only two-turn
supplements, not substitutes for the planned 3–6-turn correction/memory lessons.
No medical diagnosis, tool execution or relationship outcome guarantee is included.

The full source paths are in shortlist.json, per-response reasons for all 48
conversations are in manual-review.json, and independent machine-verifiable source
membership/content checks are in validation.json. Review was by this Codex agent;
there is no independent semantic reviewer claim.

## Quality findings

46 conversations excluded as-is. Examples include unprovided paid-fee assertions
in an exam email, failure to include a requested company name, grammatical errors,
sycophantic acceptance of a mistaken user correction and excessive verbosity.
A second numerical check corrected an initial review note: T10's first postcard is
98 words and passes its limit; its 182-word continuation still violates the retained
length constraint. The final per-turn record reflects this correction.

Do not promote source ratings into our acceptance gate. Keep full trajectories:
a good final reply does not erase an earlier erroneous answer. No cherry-picking
individual turns out of failed conversations was used here.

## Local checks

- Both candidates pass Own's actual tokenizer, native2K limits, both no-call policy
  modes, shifted assistant-only labels, end-token supervision and train/serve prefix
  equality. 292 unique supervised targets combined, including ending tokens.
- A 384-token maximum reply budget was used for discovery/prospective checks; it
  does not modify the frozen diagnostic or its fixed evaluation budget.
- Compared eight messages against 634 available local JSONL files / 334,000 text
  segments. No exact/near-overlap threshold hits. Generic closing phrases have
  partial overlap, disclosed in overlap.json.
- Same limitations as the prior audit: lexical five-gram heuristics; corpus text
  under eight words omitted; no binary, non-JSONL, remote/deleted or sealed-release
  clearance. No broad decontamination or pristine-evaluation claim.
- All 41 frozen input hashes unchanged. No model, runtime, training code or serving
  default changes. HTTP8765 off. No VM/GCS actions and no fresh VM inventory claim.

## Next gates

Keep both complete trees in TRAIN-CANDIDATE-ONLY; siblings and later variants may
not cross into dev/release. Neither record is training-admitted. Preserve Apache
attribution, revision and message/tree IDs, excluding unnecessary contributor IDs.
Further curriculum work must address corrections, grounded summaries and explicit
state tracking; these two examples do not cover those capabilities.

A new production contract/split/review receipt requires adequate reviewed coverage
and resolved contamination scope. Do not create a tiny nominal production release
merely to mark a checklist complete. Frozen fit learnability remains the first
training gate. No corpus expansion inside the frozen fit packet.

GPU policy remains L4 ONLY, VM off until a new explicit finite L4 cap is approved.
Prior CUDA signal-recovery failure, L4-specific qualification, GCS/provider fault
checks and fresh authentication/resource inventory remain blockers. No automatic
upgrade, retry, extension or fallback to A100.
