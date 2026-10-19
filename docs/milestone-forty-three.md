# First-iteration conversation and second-iteration preparation

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

First-iteration training is complete. Its actual eight-turn conversation scores **0/20 points, normalized to 0/100**. Second-iteration data preparation has started; second-iteration neural training has not started.

The first run learned some prose statistics but received only about 1M positions of narrow reference prose and no conversation SFT. Its lower heldout prose loss does not establish conversational understanding. These failures do not isolate parameter capacity, tokenizer, optimizer or architecture as the cause. Increasing data breadth and adding assistant-target dialogue training are the next experiments; changing architecture now would confound that comparison.

## Actual conversation

The owner requested a conversation, delegated scoring and then a second iteration. The protocol was written before interviewing: five dimensions, each 0–4, over the whole conversation. Follow-ups were selected after reading each real answer. Every failed student reply remained in subsequent history; no corrected or ideal assistant response was substituted.

The exact terminal milestone-forty-two checkpoint and tokenizer were used locally on MLX, with raw greedy decoding, eight turns and at most 64 new tokens per turn. The complete prompts, responses, token IDs, timing, identity hashes and turn-specific judgments are in [the assessment receipt](../reports/milestone-forty-three-conversation.json).

| Turn | Task | Observed result |
| --- | --- | --- |
| 1 | Greet Mira in one sentence | Unrelated “first-largest” fragment; no greeting/name |
| 2 | Correct the failure; return exactly Hello Mira. | Ignores correction and exact output |
| 3 | Recall the original name | No name recall |
| 4 | Return only the answer to 2 + 1 | No number or useful answer |
| 5 | Adopt corrected name Tara and current count 2 | Ignores both corrections and exact sentence |
| 6 | Professional request to move 3 PM meeting to 4 PM | Neither time nor a meeting request |
| 7 | Caveman version, at most 12 words | No facts/style; 18 whitespace-delimited words |
| 8 | JSON recap of corrected facts | Invalid JSON, missing all requested facts |

Understanding, relevance, coherence, context/corrections and instruction following each score **0/4** under the declared anchors. All eight tasks fail. English-looking repeated fragments do not meet the coherence criterion. One reply ends at EOS; seven reach the generation ceiling. The score describes this single adaptive, correlated development conversation; it is not a population accuracy estimate, blinded benchmark or readiness percentage. Tool/MCP capability was not exercised.

Independent checks reconstruct all prompt lengths from exact history, decode every saved reply from raw tokens, and verify context budgets plus protocol/script hashes. The conversation is evaluation material, not admitted training data. Preserve its task families when checking later data/teacher contamination.

## Second iteration: work already performed

- Complete pinned OASST2 ready-tree snapshot acquired: **13,854 trees / 135,174 messages**, 54,370,156 compressed bytes and 275,163,382 decoded bytes. Published compressed SHA256 matches; full gzip EOF/CRC and message lineage/role checks pass. The 64 MiB compressed and 512 MiB decoded limits are explicit bounds for this acquisition, not an increase in any training allowance.
- Every complete tree matches the cached pinned official ID/parent/tree projection: **13,162 upstream train / 692 validation trees**. No new partition network transfer. This proves identity/partition membership; it does not prove Parquet text equality or full-file Parquet checksums.
- Raw publisher labels include **64,513 English messages / 5,401 English roots**, 4,376 deleted messages, 3,158 negative reviews and 2,499 missing reviews. Every message in this particular export is labelled synthetic=false with model_name=null; preserve those claims without treating them as independently verified authorship. The source card's broader mixed-content warning remains relevant to other exports.
- Raw data stays ignored outside Git. Acquisition and inventory remain sample-only, with training eligibility false. Downloading a complete source does not approve its complete contents.

Evidence: [acquisition](../reports/milestone-forty-three-acquisition.json), [metadata inventory](../reports/milestone-forty-three-source-inventory.json), [complete partition join](../reports/milestone-forty-three-partitions.json).

## Second iteration: execution order

1. **Build candidate data.** Stream English conversation paths with raw node/rank/review/deletion lineage. Reject deleted or rejected nodes and incomplete paths; treat missing metadata explicitly. Preserve official validation and every previously frozen source/context holdout. Group sibling paths and near duplicates before any local split; do not multiply the same ancestor messages into misleading distinct-token counts.
2. **Review and admit a bounded population.** Use delegated expert review with human attestation false. Read a reproducible stratified sample, including short conversation, long multi-turn, corrections, professional/casual/slang, code and unsafe-content edges. Publish reasons, error estimates with appropriate uncertainty, filtering decisions, source evidence and exact population hashes. Retain rejected/ungraded records separately. No rank-only blanket quality approval. The earlier 49-row release and 1M prose admission do not authorize this broader corpus.
3. **Add broader English foundation text.** Select and pin additional content-licensed prose sources under the existing dataset plan. OASST alone is not a thorough English foundation corpus. Measure distinct prepared positions and source/topic balance; avoid letting repeated roots or one source dominate. FineWeb/UltraChat still need their separate source-specific decisions. No new teacher generation is needed to finish raw-source preparation.
4. **Choose a representative tokenizer.** Compare 16K and 24K BPE on train-only prose/dialogue, styles, quantities and JSON. Report heldout fertility/byte coverage without fitting on heldout text. Freeze IDs and all hashes before a neural run. A vocabulary change starts a new random-initialized chain; never reuse mismatched embeddings. Keep the current 81M architecture initially.
5. **Freeze the local training experiment.** Prepare a bounded 10M-position pilot proposal with at least 5M distinct prepared foundation positions if using at most two passes. Count optimizer screens, rejected attempts and replays separately in physical work; declare cumulative limits before launch. Compare 3e-4 vs 1e-3 at equal exposure on the same tokenizer/data, then use the measured choice. The old 1M research release caps remain unchanged; a new admission/run contract is required. No cloud main-training spending is authorized.
6. **Train conversation explicitly.** After the foundation stage, use assistant-target SFT on admitted multi-turn train paths, with prior turns as context and correct end markers. Compare 1e-5 vs 5e-5 at equal exposure; use 1–3 epochs with heldout deterioration checks. Set actual update/position/wall limits after token counts are measured. Do not over-replay the current 20 approved train examples. Keep style and tool learning as separately measured capabilities; ordinary conversation success cannot substitute for executable tool tests.
7. **Assess before advancing again.** Record frozen prose and dialogue losses, regression probes, raw multi-turn conversations and the same five-dimension rubric. Use fresh adaptive follow-ups as well as fixed development comparisons; distinguish them in reporting. Score the model directly without teacher repair, hidden retrieval or substituted answers. Preserve failures and explicitly report improvement or lack of it. Repeat the train → converse → score → next-iteration loop only after each run has terminal evidence.

Actual MLX/CUDA resumed-quality validation remains required under Option A. This milestone neither waives that gate nor spends the remaining CUDA allowance. Teacher transport remains CLI-only, with existing rights/category and review limitations unchanged.

## Validation and status

- Focused acquisition, snapshot, partition and generation suite: **39 passed / 1 hardware skip**. Initial acquisition-only suite: 20 passed. The previous full suite was 753 passed / 15 skips; it predates this module and is not reported as rerun here.
- Complete actual snapshot, complete official identity join and eight-turn token/history checks passed.
- No new teacher, Platform API, cloud job or neural training. No production admission or useful conversation/tool acceptance. The full project goal remains active and incomplete.

Reproduce acquisition with a fresh output directory:

```sh
.venv/bin/python -m slm.data.tree_snapshot \
  --source-record data/audit-v1/oasst2/source/source.json \
  --output data/iteration-two-oasst2-snapshot-v1
```

The interview script refuses an existing transcript directory; preserve the original evidence rather than overwriting or silently replacing it.
