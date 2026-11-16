# English source shortlist — 16 November 2026

**Decision: retain three reviewed candidates, admit none.** Both datasets contain
useful material, but neither qualifies for bulk ingestion. The frozen fit experiment
is unchanged and must pass before any expanded English curriculum is trained.
Future GPU work is **L4 only**, with no automatic A100 fallback, and still requires
a new explicit finite cap. No VM/GCS actions or model changes in this task.

## Review coverage and results

- Pinned Smol-SmolTalk revision `f73fe857d519ff6ac5af2ea67c4d3834da7b8bcc`;
  scanned metadata/text structure of the first training shard (115,086 rows),
  not the complete dataset. 67,651 rows belong to smol-magpie-ultra-short;
  41,201 pass the first structure/character-length filter.
- Pinned OASST2 revision `179dd21fc55192153d94adb0e0ce8f69e222bf75`;
  traversed 13,854 ready conversation trees. Eligible paths require English,
  review_result=true, deleted=false, synthetic=false at every node, and rank=0
  assistant responses. These are source metadata claims, not independent proof
  that no contributor used AI. This ready export is not restricted to upstream
  train; upstream split membership must be mapped before admission.
- First hash-selected discovery sample: 12 conversations per source. All 24
  received topic screening; 20 were excluded by scope without full semantic
  review. Four relevant OASST conversations received full review and failed.
- Adaptive focused passes: 12 short English-task Smol conversations and eight
  short English-task OASST conversations; every turn read. Human search allowed
  two-turn lessons because only 42 paths passed the original 3–6-turn length
  screen. This is a disclosed discovery adjustment, not a changed release gate.
- Total: **44 candidates screened; 24 conversations/64 assistant responses fully
  reviewed; three conversations/eight responses shortlisted**. Twenty-one fully
  reviewed conversations excluded as-is. The sample is deliberately filtered,
  adaptive and small; these counts are NOT population quality estimates.
- Review by this Codex agent only. No independent-review claim. No sealed release
  inspected. No sample is labelled a pristine evaluation or admitted training row.

## Candidate shortlist

| Key | Source | Lesson | Assistant turns | Supervised targets | Maximum serialized tokens, tools enabled |
|---|---|---|---:|---:|---:|
| F2 | Smol-SmolTalk | Grammar correction, effects/affects follow-up | 3 | 405 | 1,042 |
| F10 | Smol-SmolTalk | Concise rewriting and a required opening phrase | 3 | 239 | 885 |
| H6 | OASST2 | Polite absence email; remove a request after user correction | 2 | 267 | 685 |

Exact original text, source identifiers, full review notes and checks are in
`shortlist.json` and `manual-review.json`. No answers were silently repaired.
These are useful editing lessons, not broad English coverage. F2 is relatively
verbose; H6 uses conventional email padding and is only two turns. Cap their
curriculum share; do not duplicate them to manufacture volume.

All three pass Own's real tokenizer, 2K serialization, both no-call policy modes,
train/serve prefix equality and assistant-end supervision. A 256-token reply budget
fits every prefix and all original assistant answers (maximum 180 content tokens).
Combined unique supervised target mass is 911, including ending tokens, before any
replay. Exact-message comparison with the frozen local fit set found no overlap;
this is NOT full near-duplicate/decontamination clearance.

## Why examples were rejected

- Smol: wrongly explains an active construction as passive; invents causal
  relationships during editing; changes almost all night into most of the evening;
  removes consistently while missing the remaining time and time again wording.
- OASST: assumes laundry/store proximity, fails schedule constraints, asserts image
  access, changes a clarification request into Hey Buddy you are funny, or contains
  grammatical errors. Source quality ratings alone did not prevent these failures.
- Maths, statistics, coding, historical trivia, medical advice, fantasy and lengthy
  roleplay were deprioritized for the first English curriculum. Scope rejection
  does not establish those examples are factually wrong.

## Provenance and licensing

- Smol-SmolTalk card declares Apache-2.0 and synthetic provenance. Parent SmolTalk
  card says Smol-Magpie-Ultra was generated with Llama-3.1-405B-Instruct and its new
  datasets are Apache-2.0. Do not treat the repository code license as blanket data
  clearance; retain the parent provenance and review applicable generator terms
  before admission. Parent card is independently revision-pinned.
- OASST2 card declares Apache-2.0. Preserve attribution and source tree/message IDs;
  strip unnecessary contributor identifiers when producing a training artifact.
- Cards, metadata and download hashes are stored locally. Bulk source inputs are
  ignored review caches in runs/english-source-shortlist-v1, not training inputs.

Primary links:
- https://github.com/huggingface/smollm
- https://huggingface.co/datasets/HuggingFaceTB/smol-smoltalk
- https://huggingface.co/datasets/HuggingFaceTB/smoltalk
- https://github.com/LAION-AI/Open-Assistant
- https://huggingface.co/datasets/OpenAssistant/oasst2

## Next curriculum and blockers

1. Keep the reviewed 24/12 fit/development packet immutable. Prove frozen fit
   learnability before curriculum expansion or any new training allocation.
2. Expand discovery selectively for everyday conversation, clarification, factual
   state/corrections and grounded summarization. Current shortlist undercovers these.
   No promised quota or mandatory 300-row target; quality controls determine size.
3. Pin every source/version/license; map upstream splits; group entire OASST trees
   and related Smol prompt/template variants before splitting. Deduplicate across
   both sources and the historical local corpus. Never use sibling branches in
   separate partitions or silently treat public upstream test data as fresh release.
4. Full per-turn semantic review, tokenizer/masking checks, contamination screening
   and a new production contract are mandatory before admission. New Codex examples
   may fill demonstrated gaps only after the fit gate; label them generated.
5. CUDA signal recovery, real GCS upload/provider-stop checks and fresh GCP
   authentication remain unresolved. New runtime must qualify on L4; prior A100
   evidence does not establish L4 correctness or throughput. No new cap approved.

The earlier local-readiness receipt remains historical evidence for commit
1dcbd9b. Its bound handoff/AGENTS/next-steps snapshots have now been superseded;
its tested code/data and results are not rewritten by this source review.
