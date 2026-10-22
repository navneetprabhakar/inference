# Conversation readiness diagnostic

**Decision: not ready for conversation fine-tuning. No student updates performed. Full foundation training remains paused.**

The latest own-from-scratch 15,191,712-parameter checkpoint (step 601; 78,774,272 applied foundation target exposures) was evaluated read-only. Its SHA256 is `194f0d3d0574ce86cddeff9a88e38993bf00837b583c1dea2f6c0f506d8255b2`. The checkpoint hash remained unchanged after generation.

## What was checked

Eight fresh story prefixes generated 64 tokens each at temperature 0.7/top-40. Twelve simple conversation scenarios used greedy generation with two text formats, up to 48 tokens each. The context-reference case had the same prompt in both variants, so there are 23 distinct rendered chat prompts, not 24 independent tests. The entire diagnostic generated 1,664 tokens in 17.74 seconds; no EOS was produced. Truncated final sentences were not themselves counted as coherence failures. This was FP32 PyTorch/MPS inference from the saved FP32 master weights, not a claim about BF16 decoding parity.

The primary agent read all outputs. GPT-6 Luna independently graded the same outputs through the Codex CLI, without seeing the primary agent's grades. Both reviews found all eight story continuations contextually incoherent and all 24 chat outputs incorrect. Readable local phrases do not establish coherent English. The formal English acceptance gate was not run or passed. Neither these diagnostics nor the eight future probe prompts constitute a sealed independent acceptance set.

| Diagnostic | Count | Readable English | Coherent / follows request |
|---|---:|---:|---:|
| Story continuation | 8 | 8 | 0 |
| Chat-format outputs | 24 across 12 scenarios | 24 | 0 |

Examples: the seed-planted-in-a-pot story changes Sara to Sue and moves to a park. Asked for the user's name, the model produces repeated apologies to “Mom.” Asked about a blue cup, it changes the object to a box. These original outputs remain unchanged in [responses.json](responses.json); teacher responses were never substituted into student scores. Failure on untrained chat templates alone is inconclusive; the story continuation failures provide separate evidence of weak base coherence.

## Teacher corrections prepared

One request explicitly selected `gpt-6-luna` with high reasoning, saved ChatGPT authentication, tools disabled, and a 240-second deadline; it completed in 25.94 seconds with no tool events. The CLI returned no resolved backend model identity, so the receipt reports the exact requested model and leaves resolved identity unknown. Usage: 18,027 input, 2,690 output, 878 reasoning-output tokens. The command/schema approach follows [official Codex structured review guidance](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex).

All 16 new correction examples were manually reviewed for correctness, names, arithmetic, negation, exact formatting, clarification, and unperformed-action honesty. They fit the current 256-token window without truncation. Using the current Llama SentencePiece tokenizer and the documented prompt/assistant serialization, they contain **217 supervised assistant targets including EOS**, and **520 total prompt plus target tokens**. No examples were rejected. This is a small pattern seed, not enough data to teach conversation. Eight additional future probes were frozen before the teacher request, excluded from that request, and remain unevaluated; they are development material, not a formal final holdout.

See [reviewed-corrections.json](reviewed-corrections.json), [teacher receipt](teacher-receipt.json), and [assessment.json](assessment.json). No student SFT, new foundation continuation, or tool training was started. Existing gate criteria remain unchanged. The next learning experiment needs bounded foundation continuation and a predeclared development assessment before conversation SFT becomes eligible; the full reference run remains unapproved.

## Validation and repository contents

Read-only generation passed checkpoint-integrity and finite-logit checks. The focused restart/teacher suite passed **787/787 tests** in 32.96 seconds. The broader restart/teacher/backend test invocation produced **788 passed, 2 skipped, 37 blocked failures**. Every failed case was a legacy accumulation/Torch test attempting initialization through the intentionally disabled legacy runtime. These are recorded failures, not passing tests; no launch guard was weakened to make them pass. See [validation.json](validation.json). The native benchmark's previously completed numerical and checkpoint verification remains recorded separately.

Code, selected receipts and diagnostics are versioned. Corpus payloads, local checkpoints/optimizer state, virtual environments and raw CLI events stay on the laptop.
