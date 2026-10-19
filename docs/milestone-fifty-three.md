# Actual conversation framing and conditioning diagnosis

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

No source-to-inference framing mismatch was found in the completed second-iteration data. Assistant content already represents **73.4%** of selected-chain targets, so the failed interview cannot be explained as an absence of assistant supervision. Fixed-window packing removes the complete preceding user message from **21.7%** of assistant-content targets. This is a measured limitation, not proof that it caused the 0/8 conversation result or that assistant-only SFT will solve it.

Next prepare a separately reviewed whole-dialogue SFT experiment and an explicit checkpoint transition policy. Preserve the completed baseline and evaluation families; no new student updates occurred here.

## Actual diagnostic

`slm.eval.foundation_conditioning` verifies the checked release and tokenizer, reconstructs each source dialogue from roles/content, checks the serializer, and compares every actual prepared input/next-token/mask batch. It also compares each user/tool-ended assistant prefix against the inference prompt builder. This is a data-format audit, not an independent tokenizer implementation or neural/cache parity test.

- Actual train rows: **25,339** (12,460 OASST2 / 12,879 Dolly).
- All **34,603** applicable assistant prefixes match inference framing exactly.
- All **7,614** prepared batches match reconstructed source tokens, next-token alignment and all-one foundation masks. Full final partial batch included.
- Both preparation and the selected schedule retain their original manifest hashes; the selected schedule covers **10,223,491** positions. Discarded optimizer-screen exposure is excluded from the following selected-chain counts.
- Actual data-only runtime: **77.30 seconds**. No neural updates, generation, teacher/API/cloud actions or spending.

| Target/context measure | One prepared pass | Selected training chain |
| --- | ---: | ---: |
| Assistant content | 5,719,481 | 7,503,191 |
| User content | 1,888,041 | 2,471,281 |
| Structural targets | 189,089 | 249,019 |
| Total prediction positions | 7,796,611 | 10,223,491 |
| Assistant content with complete preceding user in window | 78.29% | 78.32% |
| Assistant content with complete document prefix in window | 69.10% | 69.28% |
| Assistant content with its assistant role token in window | 82.49% | 82.53% |
| Cross-document EOS → BOS prediction targets | 25,338 | 33,410 |

No system/tool content appears in this source pool. All assistant messages have some preceding user in their original document, but window boundaries remove that context for many targets. Specifically **1,626,482 selected-chain assistant-content targets** lack the full last user message in their input window. Full last-user availability does not guarantee prior-turn history, task understanding, factual quality or useful attention.

Counts use the actual 1,024-position independent training-window start for each target: a target at global position q sees input beginning at `floor((q-1)/1024)*1024`. The preceding user role must be at or after that start to count its complete message as present. Full-document availability additionally requires the original document BOS. Structural targets are excluded from assistant-content denominators. Cross-document attention remains active; this diagnostic does not alter it.

**24,540 / 25,339 dialogues (96.85%)** fit whole within 1,024 prediction positions. Their hypothetical assistant masks contain **4,945,341 targets**, including assistant message endings/EOS. These are serialized path counts, including repeated branches; they are neither unique-token counts nor SFT-approved examples. The 799 longer paths were counted, not silently truncated or removed from existing training.

Evidence: [actual diagnostic](../reports/iteration-two-conditioning-diagnostic.json). Release, tokenizer, prepared data, schedule and diagnostic implementation hashes are included.

## Checks and limitations

**38 focused checks passed / one CUDA skip** (NVIDIA device unavailable). Seven new checks cover independent literal framing/role counts, a window cutting away a user while retaining the assistant role, the later-user-at-window-start case, cross-document BOS prediction, missing prior user, and corruption rejection. Existing tokenizer/shard checks cover the adjacent path. An initial fixture accidentally retained its terminal EOS as an extra input in the final partial batch; it failed accounting and was corrected. Production data and training code were unchanged.

This is not a causal ablation. Generic/repetitive replies may reflect limited/diverse exposure, objective/optimization, data quality or other modeling factors. The audit does not isolate those causes or certify that the model attended to available context. The 10M-position pilot and source loss do not establish broad English competence; the actual conversation remains **5/100, 0/8 tasks**.

## Next concrete work

1. Select and read a source-balanced, group-aware packet of whole dialogues for explicit SFT judgments. Reuse verified local sources and retain prior exclusions/heldouts. Do not promote the foundation-only research release to SFT by changing a flag.
2. Admit only reviewed eligible rows or adopt a separately evidenced corpus policy under the existing review delegation. A tiny overfit control may diagnose mechanics, but cannot substitute for the requested broad conversation model.
3. Implement and verify an explicit foundation-checkpoint → SFT transition: unchanged model/tokenizer identity, declared optimizer preservation/reset policy, old/new data-plan lineage and separate exposure counters. The current trainer intentionally rejects a changed-plan resume; do not bypass its binding or silently reset state.
4. Freeze local training exposure, learning rate/selection, context handling, validation/regressions and terminal-conversation protocol before starting the next iteration. Avoid this development interview and protected evaluation-family variants in training.

Full scope remains open: useful conversation/styles/content settings, required reviewed teacher workflow, learned tools/MCP, actual MLX/CUDA resumed-training quality, production selection/quantization and later ESCI. No new budget authorization is inferred.
