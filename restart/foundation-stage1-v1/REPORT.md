# First +75M foundation stage — completed and paused

**The approved stage finished. Loss and grammar improved; context-grounded behavior remains weak. No next stage or conversation training has started.** Completed 23 October 2026, approximately 08:07 IST. See [machine-readable report](report.json).

## Before and after

| Frozen development measure | Before | After |
|---|---:|---:|
| Validation NLL, same 131,072 targets | 2.36733935 | **1.71034621** |
| Grammar, 100 rendered trials | 55/100 | **71/100** |
| Distinct grammar pairs ignoring answer order | 22/45 | **33/45** |
| Grounded comprehension, four choices | 28/100 | **27/100** |
| Story coherence, primary-agent review | 0/100 | **9/100** |
| Story coherence, GPT-6 Luna review | 0/100 | **1/100** |
| Conservative coherence: both reviewers pass | 0/100 | **1/100** |
| Narrow frozen repetition-threshold failures | 0/100 | **1/100** |

Validation loss fell **0.656993 nats/target (27.75%)**. The first/last 25 training-update mean losses were 2.33318 and 1.71526; these are different training batches, not an additional heldout comparison. The narrative graders disagreed on eight cases, retained as failures under the frozen conservative rule. These results support learning local English patterns and grammar. They do not demonstrate reliable passage use, coherent discourse or conversation readiness.

A successful continuation stays with Lily and her parent baking and eating biscuits, with minor wording errors. A common failure: a lost-puppy prefix turns into searching for a toy, forgetting the puppy and its owner. Many responses now contain plausible sentences while changing actors, objects or causal relationships. All original outputs are preserved in [stage1-evaluation/stories.json](stage1-evaluation/stories.json); no teacher answer replaced student output.

## Exactly what ran

- Resumed **our own 15,191,712-parameter checkpoint**, step601, SHA256 `194f0d3d0574ce86cddeff9a88e38993bf00837b583c1dea2f6c0f506d8255b2`. No public model weights or new student initialization used as a training origin.
- **572 additional optimizer updates / 74,973,184 applied targets**, ending at **step1173 / 153,747,456 total retained training targets**. Native MLX BF16 compute with FP32 master weights/moments, context256, microbatch16, accumulation32, effective batch131,072 targets. Existing AdamW state, schedule and deterministic stream continued; original warmup completed without resetting it.
- Unchanged prepared native TinyStories training shards and tokenizer. All50 token-shard hashes verified before launch. No new downloads, teacher-generated training examples, conversation SFT or tool training.
- Recoverable saves verified every100 updates. The final checkpoint was saved **before** response evaluation. Training stopped at its target cap; evaluation and audit work performed no optimizer updates.

Final checkpoint: local `restart/foundation-stage1-v1/stage1-checkpoint.pt`, SHA256 **`d0cd9a769de016cad73b358e5fe82a630c72ccc966d1045911bc187f54fe8c9c`**. Full FP32 master/optimizer state, scheduler, data cursor and MLX RNG are retained. CPU save/reload comparisons passed exactly. Next sequence position is600,576 completed sequences. [Checkpoint receipt](stage1-checkpoint.json).

## Correctness, time and resources

- Independent FP32/PyTorch inference from the **new saved checkpoint** gave NLL1.71024580 on the same validation targets. Difference from native BF16: **0.00010041**, within the unchanged .02 tolerance. [Reference verification](serialized-reference.json).
- Every logged loss/gradient norm and every checked master-weight/optimizer-state tensor remained finite. Launch-pinned training source bytes and the original checkpoint were unchanged. [Source verification](training-source-verification.json).
- Training updates took **110.4 minutes**; full reporting evaluation sequence approximately **118.6 minutes from this approval**. Mean training throughput **11,319 targets/sec**; final30-minute throughput **10,809 targets/sec**. The latter is below the earlier short benchmark estimate: future ETA calculations must use sustained measurements. At this rate,300M targets plus20% overhead would take about9.25hours; the proposed8-hour ceiling still takes precedence over any token target.
- Peak supervised process-tree RSS **1.48GiB**, additional global swap **0**. GPU/memory checks retained their12GiB caps; no unrecorded GPU peak is claimed. Original382.75MiB swap baseline and earlier failed-attempt records were preserved.
- This stage charged **76,702,570 processed positions**, including all loss/scoring/generation work, independent FP32 verification and the boundary audit. Previous preflight charges1,003,285 remain intact: combined **77,705,855**, below the original320M continuation-experiment ceiling. Prior benchmark records remain separate and unchanged.
- All workers are reaped. A completed-stage review hold blocks further work in this stage directory. No automatic retry, next-stage launch or expanded training approval.

## Evaluation limits and document-boundary audit

The packet, seeds, scoring and loss sample were frozen before training and match the corrected preflight baseline. This is reused **development** material, not an independent final acceptance set. The100 grammar trials contain45 distinct pairs, and100 story cases cover20 templates with five names each. Native TinyStories shard splitting has unresolved family/near-duplicate leakage; this stage did not certify broad-data quality or deduplication. No formal English or conversation gate passed.

Training text uses BOS at document starts without EOS endings. The frozen generator stopped on EOS or96 tokens, so absence of generated EOS is not a model failure. A separate, read-only token audit replayed **all100 frozen stories with the same seeds** and reproduced **100/100 original decoded outputs exactly**. It found **9 outputs with hidden generated BOS document markers**. Continuing beyond them can introduce another document and lower full-window narrative grades. [Audit with token IDs and first-document text](boundary-audit.json).

The original full-window outputs and scores were **not replaced, shortened, rerolled or retroactively relaxed**. Even treating all nine boundary-affected outputs as additional passes gives at most10/100 conservative passes, far below the proposed80/100 narrative milestone. The overall lack of demonstrated conversation readiness is therefore unchanged. Before another evaluation protocol is frozen, generation should respect the trained document-boundary convention; grammar coverage also needs more independent pairs.

The primary agent read all100 raw prefixes/continuations and recorded grades before seeing teacher grades. One tools-disabled Codex CLI request explicitly selected `gpt-6-luna`, high reasoning, saved ChatGPT authentication:49.46seconds,30,924 input,5,584 output and371 reasoning-output tokens. No tools/actions; no training examples generated. Resolved backend identity is unavailable and left unknown in the receipt. [Primary grades](primary-review.json), [teacher grades](teacher-review.json), [teacher receipt](teacher-receipt.json).

## Decision

**Keep all training paused for owner review.** This completed stage demonstrates lower next-token loss and better grammar, with little demonstrated improvement in grounded comprehension or reliable narrative coherence. It does not justify conversation SFT. Any next foundation stage needs explicit approval, an ETA reflecting the measured sustained rate, and a transparent treatment of the document-boundary evaluation limitation. Existing formal English-gate thresholds remain unchanged.
