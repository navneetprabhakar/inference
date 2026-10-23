# Why this experiment has not produced a conversational foundation model

CPU-only audit of the saved checkpoint, training/evaluation code, tokenizer, logs and existing grader outputs. Zero model forward passes, optimizer updates, new weights, teacher requests or downloads. Frozen experiment sources and saved model hashes are unchanged. Training remains paused.

## Assessment

The strongest explanation is an early, narrow-domain model evaluated through a flawed measurement process. We have not completed the configured reference training run, and we have not demonstrated that its architecture or the under100M ceiling is the cause of failure. The current artifacts also do not establish that simply adding more exposure will solve it. My earlier conclusion that response quality had not improved was too categorical: continuous scores show modest improvement, while readiness remains poor.

### 1. A long-run recipe was used inside short experiments

| Quantity | Measured/configured |
|---|---:|
| Completed optimizer updates | 2,889 |
| Configured training horizon | 100,000 updates |
| Completed targets / configured targets | 378.67M / 13.1072B |
| Fraction of configured run completed | 2.889% |
| Approximate native corpus passes | 0.377 |
| Warmup | 1,000 updates / 131.072M targets |
| Warmup as fraction of completed updates | 34.6% |
| Final learning rate / peak | 0.000499551 / 0.0005 = 99.91% |

The stages preserve weights, optimizer moments, scheduler and exact data cursor. Checkpointing does not erase learning and warmup did not restart. The problem is that the resulting trajectory is an early prefix of the long schedule, without a meaningful decay/consolidation phase. It is neither a completed reproduction nor a separately validated short-run recipe. I selected the experiment budgets without resolving that mismatch. Completed exposure is24.9targets per parameter; that ratio alone does not establish convergence or semantic readiness.

The pinned upstream train.py really uses a100,000-update horizon and1,000-update warmup. This is a **configured default**, not proof that the published15M checkpoint required exactly that many updates or that we must spend13.1B targets. We should not turn a default into a minimum necessary budget. Its README reports a15M model with the same shape and validation loss1.072; our1.401 uses our fixed validation subset, so that loss comparison is indicative, not a controlled replication result.

At the latest sustained10,499targets/sec, another1B targets requires26.5training hours before overhead. The remaining configured horizon would take14.0days before overhead. A few-hour expectation was incompatible with reproducing that entire configuration on this Mac. Native MLX improved speed; it does not eliminate required learning work.

### 2. The grammar/grounding scorer changes every candidate's text

The scorer encodes prefix and completion independently. The Llama2 SentencePiece tokenizer's dummy prefix combines with the completion's existing leading space, inserting token29871. Example:

```text
Intended: ...The color of the cup was red.
Scored:   ...The color of the cup was  red.
```

Reproduction: all200grammar alternatives and400grounding alternatives differ from tokenizing the intended full string; all contain exactly one extra token and the double space. Tokenizing complete strings preserves every prefix and equal candidate lengths in this packet. This is a concrete implementation defect, reproduced without running the model.

The extra whitespace term itself is common to options and cancels in ranking. However, it changes the context used to predict each answer word. Its effect on accuracy cannot be quantified from saved logits; those logits were calculated under the altered context. **The published75→78grammar and42→30grounding results are historical outputs of this flawed scorer, not clean measures of normal-text capability.** Do not assert that correcting the bug will improve them. Corrected scoring of the same saved checkpoints is required, under a separately approved read-only correction scope.

On the flawed current grounding inputs, all20color cases prefer blue, all20location cases prefer box, all20negation cases prefer box, and all20correction cases prefer blue, irrespective of the stated answer. This is consistent with lexical priors dominating passage facts in that input condition. It is not yet proof of the same failure rate under corrected text.

This scoring defect does not touch the separate story-generation path. Eating an oven and bringing a kitten to itself remain actual generated errors.

### 3. Binary grading obscures progress and lacks calibration

| Paired Sol measure | Previous | Current |
|---|---:|---:|
| Mean five-dimension total, /10 | 4.45 | 5.06 |
| Grammar mean, /2 | 1.52 | 1.70 |
| Topic mean, /2 | 0.86 | 0.95 |
| Reference mean, /2 | 1.16 | 1.28 |
| Causal/temporal mean, /2 | 0.43 | 0.49 |
| Local coherence mean, /2 | 0.48 | 0.64 |
| Incoherent-sentence flags | 54 | 41 |
| Conservative binary passes | 4 | 4 |

These judgments suggest modest improvement, not convergence. Causal and local coherence remain weak. A threshold requiring total>=8, no zeros and no flagged sentence can stay flat while subthreshold cases improve.

Current primary23passes and teacher5passes overlap on4cases:80%raw agreement, **Cohen's kappa0.222**. The apparent agreement is dominated by mutual failures. The same previous checkpoint scored14/100 in the earlier Sol review and4/100 in this paired regrade. The instruction prefix, requested model, client and rubric are the same; companion cases and positions in the200-case batches differ. This is evidence that this review method is not calibrated/repeatable, not an exact-same-prompt stochastic-repeat experiment.

Several disagreements also confuse coherent narrative development with completing an implied task in a particular way: unused collar number, drawing without explicitly retrieving crayons, or a mother helping instead of a sister. These can be weaknesses without necessarily being nonsensical stories. Real entity/causal errors are common, but four strict passes must not be advertised as a calibrated4%natural-English competence estimate.

The100grammar trials reduce to45distinct pairs; the weighted rendered score rose75→78while distinct correct pairs fell37→36. Grounding has5families and stories20families, with repeated names/conditions. Results do not have100independent task families. No formal acceptance set or two-human acceptance gate has passed. Future measurement should include continuous scores, explicit anchor judgments, grader agreement, family-level uncertainty and a calibrated hard gate; thresholds cannot be changed retroactively.

### 4. Surface prediction improves before reliable semantic state tracking

Stage-three first100mean batch loss1.5099→last100mean1.3957; fixed validation1.5271→1.4007. All logged losses/norms are finite; none of the1144stage-three gradient norms exceeds clipping threshold1. Earlier reference checks found near-identical MLX/PyTorch FP32 gradients and compatible BF16 gradients/updates, and step1745saved-checkpoint parity passed.

This supports a functioning learning process and gives no observed evidence of numerical divergence. It does not prove every implementation path correct: the latest independent FP32 check is unverified. Next-token validation supplies correct previous tokens and averages easy frequent words with sparse meaning-critical decisions. Free generation conditions on its own errors. Improving average local prediction can coexist with bad referents, object identities and causality. That explanation fits the artifacts but has not been isolated through a causal ablation.

We also froze a256-token context. The current prompts plus96generated tokens fit it; overflow does not explain these short failures. It remains an inadequate tested context budget for the eventual multi-turn/tool goal. No current conversation-format training has occurred, so this base model's chat-template behavior cannot be treated as a completed conversation experiment.

### 5. The data and architecture are a prototype for a different scope

The native corpus is synthetic children's narrative, not a broad conversation/tool curriculum. Plain story training never directly teaches our role serialization, instruction/response convention, argument schemas or using tool results. The older500-conversation pilot belongs to a different5.1Mstudent lineage; its accepted train split contained382conversations and16,317assistant targets under a different tokenizer. It was a pilot, not sufficient evidence of a production conversation curriculum. No such SFT entered this15Mlineage.

The native1.004Bcorpus positions must be kept separate from the older admitted broad-release14.566Mcontent tokens under theM1BPE. That older release has only197,084human tokens (1.35%) and does not meet its planned mixture. Provisional PressBooks counts are unadmitted. The limited source sample does not demonstrate a corrupted native corpus as the cause, and deduplication/leakage limitations still affect validation confidence.

The current32Kvocabulary consumes9,216,000parameters, **60.7%**of the total, leaving5,975,712in transformer blocks/norms. That is inefficient for a narrow story domain and makes the headline15Msize misleading as a measure of contextual processing capacity. It is a future design hypothesis, not proof this shape cannot work: the published same-shape reference is a counterexample. Increasing to60M/100Mnow would change the experiment before resolving measurement and budget fit. Changing vocabulary would create a new lineage rather than an exact checkpoint continuation.

TinyStories demonstrates restricted coherent narrative and limited instruction variants; it does not prove robust adult conversation and arbitrary MCP tool use below100M. I overextended that evidence when implying all end goals were assured within the cap.

### 6. Engineering controls did not adequately test the interfaces that matter

The post-run verifier requests `stage3_deadline_epoch`, while the active clock supplies `authorized_stage_deadline_epoch`. Its single attempt failed before inference. This is an orchestration/schema bug that preparation should have caught, not an observed parity mismatch and not a cause of learned incoherence.

We tested authorization paths extensively but missed both actual scorer token sequences and the verifier's clock interface. Multiple copied stage scripts with slightly different schemas amplified this risk. Resource guards were useful and worked; they cannot substitute for tokenizer-boundary tests and an end-to-end dry run of every phase contract. Hashing a buggy program only preserves the bug reliably.

## What the evidence supports

- **Confirmed:** malformed option text, unstable grading, incomplete long schedule, no conversation/tool SFT, narrow data, finite improving losses, verifier schema failure.
- **Strong hypotheses:** insufficient useful training/consolidation for this schedule; lexical prediction improving ahead of reference/causal tracking; poor experiment fit to the time budget.
- **Not established:** the extra-space bug caused the entire grounding decline; more training alone will fix coherence; bad corpus quality is the main cause; MLX corrupts learning; more parameters are necessary; the under100Mgoal is impossible.

## Recommended order, not execution approval

1. Repair and verify evaluation in a new version: exact intended token sequences, valid clock schema, and separately approved inference-only comparison of the two saved checkpoints. Retain all historical scores and failed attempts. Do not train merely to see whether a buggy score rises.
2. Calibrate the narrative rubric on clear good/bad/borderline anchors and report continuous paired scores and agreement. Compare to a same-size known reference using published evidence or an explicitly separate diagnostic control, without importing reference weights into our student.
3. Choose a decisive budget-aligned experiment: a genuinely completed reproducible schedule, or an explicitly experimental shorter schedule with proportionate warmup/decay. A shorter schedule is a new hypothesis, not a proven shortcut. Measure actual compute before promising turnaround.
4. Once foundation behavior is adequate, use a separately frozen conversation curriculum and heldouts, then tool use. Do not use another blind+150Mextension, a larger architecture, more web data or teacher rewrites as an untested cure.

All execution remains paused. No historical gate is waived and no future capability is promised. The audit's answer is that our experimental design, measurement and expectations were not aligned with the requested outcome; it is not evidence that training a small foundation model is an unsolved task.

## Evidence

- [Reproducible CPU audit](audit.py), [machine-readable findings](audit.json).
- [Frozen worker/scorer](../foundation-stage3-v1/worker.py), [learning-rate function](../foundation-stage3-v1/engine_support.py), [saved run report](../foundation-stage3-v1/report.json), [verifier failure](../foundation-stage3-v1/verifier-failure.json).
- [Pinned upstream training defaults](https://github.com/karpathy/llama2.c/blob/350e04fe35433e6d2941dce5a1f53308f87058eb/train.py).
- [Pinned upstream model results and narrow-domain scope](https://github.com/karpathy/llama2.c/blob/350e04fe35433e6d2941dce5a1f53308f87058eb/README.md).
- [TinyStories paper: dataset scope, learning curves and evaluation](https://arxiv.org/html/2305.07759v2).
