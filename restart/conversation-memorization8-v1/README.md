# Eight-conversation memorization test — passed

**Passed at update 25 and stopped early.** All eight training conversations exactly reproduce all ten assistant answers, including both correction follow-ups, and all ten assistant turns emit EOS. Baseline: zero exact conversations, zero exact assistant turns and zero EOS endings.

This is a deliberate training-set memorization check. It establishes that this model/trainer/format can fit these examples and learn stopping under the guardrail. It does not measure unseen generalization, independent conversation quality, or internal/MCP tool use.

## Measured results

| Metric | Before | Update 25 |
|---|---:|---:|
| Exact full conversations | 0/8 | 8/8 |
| Exact assistant turns | 0/10 | 10/10 |
| EOS-ending turns | 0/10 | 10/10 |
| Teacher-forced correct target tokens | 8/44 | 44/44 |
| Training assistant/EOS NLL | 6.289027 | 1.354348 |
| Fixed foundation narrative NLL | 1.343035 | 1.386570 (+3.24%) |

Consumed: 25 updates, 1,100 assistant/EOS target exposures, 330,828 student positions including correctness/evaluations, 12.48 seconds of execution. Peak reported MLX memory 1.40 GiB. Original bounds were 15 minutes, 200 updates, 2M positions, 40k supervised targets, checkpoint/evaluation every 25 updates. Success ended execution at the first checkpoint.

## Training and safeguards

Source: unchanged own foundation checkpoint at `restart/foundation-resolution-v1/B/checkpoint.pt`, SHA256 `bf45241501cee600bd618677dc1a3ae666e6f50d9c628e29e7326ee9c87d338d`. Architecture remains 15,191,712 parameters and the native 32k tokenizer is unchanged. The earlier failed SFT child was not used.

Eight directly reviewed self-authored training examples cover direct answers, a greeting, corrections, clarification and uncertainty; see `examples.json`. Ten assistant turns contain 44 supervised targets, including ten EOS targets, per update. No new teacher calls or downloads.

Uses the prior verified segmented chat format and assistant/EOS-only loss. Fresh AdamW state, BF16 compute with FP32 parameters/moments, LR5e-5 with five-update warmup, batch8, context256 and gradient clipping1. Hard stops: narrative NLL >5% above baseline, nonfinite quantities, gradient norm above100, zero first parameter update, resource or work limits. No guardrail was relaxed.

Independent Torch FP32 versus native BF16 preflight: masked NLL difference 0.002201, relative gradient L2 0.018212, gradient cosine 0.9998354. Changing masked target labels or right-padding inputs changed loss by zero. First-update parameter L2 change was 0.033277; final change from the source was 2.603171.

Free generation uses full-vocabulary greedy decoding with max24 new tokens and only BOS/EOS stopping. Previous turns in the correction conversations use generated responses. Expected answers are used only for scoring; no gold answer is inserted into the next-turn history. The primary assistant directly inspected all ten final outputs.

## Artifacts and next decision

Research child checkpoint: `epoch-25.pt`; its optimizer step is25 and its SFT exposure count is1,100. The source checkpoint remains unchanged and no child was promoted. All workers have exited; training is paused.

Complete local response evidence is in `private/step-000-responses.json` and `private/step-025-responses.json`. Checkpoint weights, optimizer state and encoded arrays remain local. Code, the intentionally public eight-example training set, counts, hashes and aggregate decisions are versioned.

Next scientific question: whether a short-answer-first curriculum transfers to fresh held-out conversations. This test changed example complexity, repetitions per example and EOS frequency relative to the previous 62-conversation run; it does not isolate which factor explains the difference. Larger SFT and foundation recovery were not resumed.
