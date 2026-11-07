# Compute and method reassessment

Research date: 2026-11-08. Primary sources inspected; no model or dataset downloads, training, or benchmark activation.

## Local evidence

The selected 124,439,808-parameter parent has 122,454,016 lineage pretraining targets (2,457,600 inherited + 99,999,744 foundation + 19,996,672 selected continuation), about 0.984 targets per total parameter. Optimizer comparison arms are alternatives, not additive tokens in this parent. The 50,257 × 768 tied token embedding uses 38,597,376 parameters, 31.0% of total. This is not proof that a smaller vocabulary would improve usable language per wall hour: token fragmentation and retraining costs must be measured.

Two assistant-only SFT experiments failed joint conversational/tool development. The second regressed sharply. The 99-frame transfer audit found exact training chat reproduction but failed held-out composition and substantial numeric-copy errors. More template exposure alone is not a supported response. A 30M-token story tranche increases language exposure modestly and narrows distribution; it must not be portrayed as the likely final fix.

At the earlier planning throughput of 1,425 targets/s, excluding evaluations, saving, cooling and downtime:

| Additional targets | Active training days |
|---|---:|
| 30M | 0.24 |
| 300M | 2.44 |
| 1B | 8.12 |
| 2B | 16.24 |
| 10B | 81.22 |

These are arithmetic scenarios, not newly measured throughput or success ETAs. MLX and alternative architectures require actual sustained measurement.

## What nanochat does and does not establish

The [official repository](https://github.com/karpathy/nanochat) provides an end-to-end random-init pipeline, but its advertised current GPT-2-capability speedrun uses an 8×H100 node. It is not evidence of equivalent training time on a fanless local laptop, or of meeting our parameter cap and joint session gate.

The [original 2025 walkthrough](https://github.com/karpathy/nanochat/discussions/1) used conversational midtraining with approximately 460K SmolTalk rows, 100K auxiliary multiple-choice rows and 8K GSM8K rows, including calculator exposure. Midtraining adapts to conversation tokens/distribution before subsequent posttraining. Its early GSM8K result was only 2.5%; a chat interface and tool syntax do not themselves establish robust behavior.

The [current SFT code](https://github.com/karpathy/nanochat/blob/master/scripts/chat_sft.py) still combines conversations and task datasets, with explicit task repetition and optional optimizer warm start. Do not conflate current code with the historical walkthrough or copy its benchmark-test selection into our protected evaluation process.

The [current base training code](https://github.com/karpathy/nanochat/blob/master/scripts/base_train.py) defaults to a data-to-scaling-parameter ratio of 12; its scaling parameter definition is transformer matrices plus output head, not blindly total model parameters. The setting is an engineering result for its recipe, not a conversational capability threshold or a prescription for our AdamW/GPT-2 implementation.

## Repetition and staged training

[Scaling Data-Constrained Language Models](https://arxiv.org/abs/2305.16264) finds diminishing returns from repeated data, with up to four epochs having little loss disadvantage versus unique data in studied conditions. It supports considering explicitly budgeted repetition rather than treating one pass as a scientific law. It does not show that repeating a narrow instruction template distribution fixes our generalization failures, or that loss equivalence means conversation equivalence. Existing frozen no-repeat experiments stay immutable; any future repetition would need a new explicit experiment and separate unique/processed-token accounting.

[CLASS-IT](https://aclanthology.org/2025.babylm-main.30/) studies 100M/140M decoder models and finds modest instruction-tuning benefits for fine-tuned tasks, inconsistent zero-shot transfer, and an advantage for sequential over merged curricula in its setting. This is directly relevant to our scale but not proof of useful autonomous conversation/tool calls.

## Provisional implications for the combined review

1. Choose a finite compute envelope before selecting model size and token horizon. A model fitting RAM is not necessarily an efficient training choice.
2. Reopen corpus composition: educational prose plus diverse simple dialogue/grounded tasks is more aligned than story-only continuation. Exact proportions remain hypotheses requiring comparison.
3. Consider conversational midtraining separately from assistant-only SFT. Evaluate factual conditioning and copying on unseen wording and unseen values separately, then joint sessions.
4. Retain the current own base as a control. A new compact architecture/tokenizer is justified only by measured learning per wall hour including restart cost; no automatic architecture rewrite.
5. Freeze one informative comparison, then run it long enough to change the decision. Backend engineering and repeated tiny diagnostics cannot substitute for sufficient language learning.

The full objective and private acceptance gates remain unchanged. No source establishes that the current local budget guarantees success.

## Smaller-budget counterchecks

- [GPT22M-chat's own card](https://huggingface.co/Mieaz/gpt22m-chat) reports 600M processed tokens over a 300M-token stories/UltraChat corpus, 16K vocabulary and 256-token context. Its published outputs are irrelevant even for greetings and names. Parameter accounting is ambiguous (23.1M versus 21.5M trainable). This is a useful negative control: low held-out story loss and a chat model label do not demonstrate usable conversation. Do not adopt its recipe as a proven shortcut.
- [TinyBrain-100M-Instruct](https://huggingface.co/exnivo/tinybrain-100m-instruct) documents a 103.4M model, 24K vocabulary and simple User/Assistant formatting, but explicitly disclaims reliable general-assistant behavior. Its example decoding adds a repetition penalty and no-repeat constraint. Such served behavior is not directly comparable with our unchanged raw-greedy evaluation.
- [Multi-task pretraining with LLM-designed study plans](https://aclanthology.org/2025.babylm-main.33.pdf) uses synthetic labels and masked-language-model/classification/tagging losses, evaluated on SuperGLUE and BLiMP. It motivates task diversity, but is not evidence for a causal conversational model trained on 1M words. Do not confuse word budgets, processed BPE targets, encoder task scores and autonomous assistant performance.

## Our filtering deserves reassessment too

Local `reports/sft-readiness-v3/QUALITY_REVIEW.md` retained 774 everyday-conversation training histories but zero validation histories after existing custody/splitting. Its eight sampled everyday examples had four retain/four review/zero hold. V4 later had four retain/two review/two hold. V5 then deferred the entire everyday, constraints and summarize-5k cohorts. The first SFT therefore did not use the full conversational mixture recommended by the source authors. This does not prove those deferrals caused failure, but it invalidates treating the run as a faithful reproduction of that recipe.

A prospective data design should distinguish demonstrably incorrect answers, unsupported specialist assertions, harmless fictional content, weak prose and actual evaluation contamination. Small subjective samples cannot justify claiming that a whole source is unusable or that all remaining rows are clean. Reconsider whole-cohort removal and split granularity without altering frozen evidence or exposing private acceptance. The previously acquired Everyday-Conversations source should be inventoried first; a fresh download is not the missing intervention.
