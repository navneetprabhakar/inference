# Corrected inference-only preflight — complete

**The corrected evaluator passed. Student training remains paused.** Completed in about 4.3 minutes against a 15-minute bound. No student updates, foundation continuation, conversation SFT or tool training occurred. All workers have exited.

## Correctness and resource results

The frozen step-601 checkpoint still has 15,191,712 learned parameters and 78,774,272 retained foundation targets. Its SHA256 remains `194f0d3d0574ce86cddeff9a88e38993bf00837b583c1dea2f6c0f506d8255b2`.

- FP32 master weights and optimizer moments survived exact save/reload comparison. Data cursor remained at 307,712 completed sequences; MLX RNG state was restored for the check.
- BF16 fixed-fixture loss: 2.48624611; independent FP32 reference: 2.48657250. Absolute difference **0.00032640**, within the unchanged **0.02** tolerance.
- The compute-view rebinding fix passed a CPU regression that reproduces the old tracing error, then completed all actual-model scoring and generation without that error.
- Peak supervised process-tree RSS **1.38GiB**; **zero additional system swap**. GPU checks retained their 12GiB cap; this report does not invent an unrecorded GPU peak.
- **871,178** evaluated input positions charged to this correction, under its 8M bound. Original failed-attempt charges **132,107** remain recorded; combined **1,003,285**. Neither clock nor old failure records were erased.

See [integrity verification](integrity-verification.json), [numerical verification](resume-verification.json), and [full report](report.json).

## Frozen development baseline

| Measure | Result |
|---|---:|
| Narrative validation NLL | **2.36733935** over 131,072 targets |
| Grammar choices | **55/100** |
| Grounded passage completions | **28/100**; four choices per case |
| Coherent narrative continuations: primary-agent review | **0/100** |
| Coherent narrative continuations: GPT-6 Luna review | **0/100** |
| Narrow frozen repetition-threshold failures | **0/100** |

All 100 stories generated the capped 96 tokens (9,600 generated tokens total); none emitted EOS. Merely unfinished final sentences were not treated as coherence failures. Widespread topic drift, changing names/entities, contradictory dialogue and nonsensical actions caused failure. The repetition metric is narrow: outputs can avoid exact repeated-sentence/four-gram thresholds while remaining incoherent.

Examples: a lost-puppy prefix changes to helping an unrelated boy; a scarf-in-a-box prefix switches to birds and self-identification as a cat; a biscuit-making prefix repeatedly puts cake on cake. The original outputs are in [baseline/stories.json](baseline/stories.json). No teacher reply replaced any student output.

The primary agent read every original prefix/response and recorded grades before seeing the independent teacher grades. One Codex CLI request explicitly selected `gpt-6-luna`, high reasoning, tools disabled, saved ChatGPT authentication. It completed in 38.61 seconds, with 30,918 input, 5,100 output and 168 reasoning-output tokens, no tool events. The CLI does not report the backend-resolved model identity; the receipt distinguishes the exact requested model from that unknown. See [primary grades](primary-review.json), [teacher grades](teacher-review.json), and [teacher receipt](teacher-receipt.json).

The installed CLI patch was `0.163.0-alpha.11.2`, while the old local startup pin expected `.11`. That guard stopped before any model request. After reviewing the exact installed version and required CLI flags, the single authorized teacher request ran. There was no inference rerun, model substitution, extra teacher request or deadline reset. Startup evidence is preserved in [client review](client-review.json).

## Limits and decision

This is a **development diagnostic**, not the formal English gate. The 100 grammar trials contain only **45 distinct pairs ignoring answer order** (22/45 correct); 100 narrative items cover **20 template families** with five names each. Raw case counts do not imply 100 independent task families or statistical significance above chance. The native TinyStories shard split has unresolved family/near-duplicate leakage; this preflight did not certify a newly deduplicated corpus or use the sealed acceptance set.

**The evaluator repair is validated; the base model has not demonstrated conversation readiness.** The low local next-token loss does not override poor coherence or near-chance comprehension. The first +75M-target foundation stage has not started and requires explicit owner approval. No later foundation stage, full reference run or conversation training is authorized.
