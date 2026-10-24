# Deep audit before the next training recommendation

The broader checkpoint has learned useful behavior. The immediate bottlenecks are **underfit new skills, low-diversity task data, an unbalanced preservation objective, and a gap between our conversation-data plan and the actual checkpoint lineage**. Neither a blanket rejection nor a promise that another 200 formatting updates will solve conversation is supported.

This audit used forward passes, teacher-forced likelihoods, sampled gradient calculations, checkpoint metadata and dataset inspection. **No optimizer updates, weight changes, training continuation or checkpoint promotion occurred.**

## 1. The current weights did not inherit the 1,000-conversation teacher batch

The current lineage is:

1. Own TinyStories-stream foundation, 412,221,440 retained foundation target exposures.
2. Controlled factual drill child: 400 updates and 9,600 assistant/EOS target exposures.
3. Broader deterministic drill child: another 100 updates and 4,699 target exposures.

That is **500 post-training updates and 14,299 assistant/EOS exposures**, with 1,024,000 additional narrative replay exposures. The earlier general Sol SFT and matched-transfer branches are not ancestors of these weights. The later branch deliberately returned to the original foundation for diagnostics. The 1,000-conversation Sol batch was generated and screened, but is not conversation SFT inherited by this candidate. There is no imported pretrained-model weight in this lineage.

This is the main project deviation: controlled drills became the active model-development branch, while generated teacher conversation data was mistaken for progress already incorporated into that branch. The drills are useful diagnostics; they do not constitute the planned conversational curriculum.

I checked the teacher training split using the now-authoritative segmented serialization: **757 of 759 screened training candidates fit**, two exceed context, and none failed structural serialization. The fitting subset contains **44,241 assistant content tokens / 45,792 assistant+EOS targets**. This differs from the older plain-format diagnostic count of 756. These are **format-eligible candidates, not newly admitted training data**; quality and leakage admission still apply. No development/test teacher payload was read in this readiness count.

## 2. There is real learning below the exact-answer threshold

The matched comparison remains 25/152 to 56/152 exact answers and 33/152 to 66/152 content/task-correct responses. Additional conditional diagnostics show why some visibly improved answers still fail exact scoring:

| Matched copying family | Short-answer child: content-token argmax accuracy | Broader candidate |
| --- | ---: | ---: |
| Complete locations | 10.8% | **82.4%** |
| Full names | 12.1% | **43.9%** |
| Times | 5.2% | **44.8%** |

These are **next-token diagnostics supplied with the correct preceding answer tokens**, not free-generation accuracy. They establish learning of parts of the task, not successful full answers.

Timestamp structure explains much of the visible gain. The tokenizer encodes a time as a word-boundary piece, four digit pieces and a colon. The candidate correctly predicts **29/32 boundary/colon positions (90.6%)**, but only **14/64 digit positions (21.9%)**, versus 4/32 and 1/64 before. It has learned much more of the output shape than the actual numeric content. Repeated clock-shaped answers are therefore progress in structure, but not reliable time extraction.

Early EOS also contributes: under correct answer prefixes, the name task still chooses EOS at 17/66 content positions. On the actual matched generations, six candidate answers ended on a proper but incomplete reference prefix. However, clocks usually fail by choosing wrong digits, rather than merely ending early. Suppressing EOS or increasing max output length is not a general fix.

## 3. The new tasks are not even fitted on seen examples yet

A supplementary training-fit check selected 16 consumed full-name examples and 16 consumed time examples, covering all 12 training labels in each family. Exact original training questions were reused deliberately; this is a fit check, not a generalization test.

| Seen-example fit | Short-answer child | Broader candidate |
| --- | ---: | ---: |
| Full names | 0/16 | **1/16** |
| Exact times | 0/16 | **0/16** |

The broader run saw only **67 time examples and 77 name examples** before stopping. Across the whole new bank it consumed 600 presentations covering 538 distinct conversations: **20.8% of the 2,592 prepared examples**, approximately 0.23 of one pass by presentations. Zero full-name/time accuracy cannot yet be diagnosed solely as poor generalization: those tasks remain underfit on sampled training records.

The earlier eight-example memorization test covered much shorter responses. It did not establish learnability of complete names, six-token times or multi-turn tracking. A bounded multi-token fit test is the missing intermediate check.

## 4. Old examples remain learned; their paraphrase behavior regressed

On the old training bank, both checkpoints had **480/480 assistant reference paths with every target, including EOS, at argmax**. Teacher-forced target NLL improved from **0.0700 to 0.0432**. On the exposed retention bank, NLL instead worsened from **0.1469 to 0.3644**, while strict replies fell 77/80 to 64/80.

This is not evidence that the old training examples were erased. It points to instruction/format generalization changing outside their exact wording. At eight affected turns (four duplicated initial prompts across color/correction cases), the average first-token log-odds of the correct color versus starting with The flipped from **+9.25 to -1.31**. The new caption-like reply mode now wins on those phrasings.

Eight strict failures still conveyed the correct color in a full sentence. Adding those back yields 72/80 factual-content replies, versus 64/80 full instruction-compliant replies. The remaining failures include fragments, stale updates and a wrong attribute. Formatting is important, particularly for future tool arguments, but it must not be conflated with every aspect of factual learning.

Simply replaying more identical old training examples is insufficient evidence of preserving behavior across paraphrases. Rehearsal must cover varied instructions and paired output formats, with holdouts excluded from that training.

## 5. The objective did not give the intended protection

The implemented loss was 0.5 narrative CE plus 0.5 target-normalized SFT CE. Two old examples and six new examples were placed in each SFT batch. Because the old answers were short, their average coefficients were:

| Group | Mean coefficient in total data loss |
| --- | ---: |
| Narrative replay | 50.0% |
| New-task SFT | 43.7% |
| Old-skill SFT | **6.3%** |

Old rehearsal was 25% of examples, but 581/4,699 (12.36%) of supervised targets. The old-bank labels themselves contain **41.7% EOS targets**, appropriate to that word-answer diagnostic but weak preparation for longer continuations. EOS should remain trained; answer lengths and content coverage must broaden.

Four deterministic historical batches were differentiated independently at the short-answer checkpoint. Weighted new-task gradient norms were **264–441 times** the old-task components. Old/new gradient cosine was mildly negative on all four, with a negative old-loss directional dot for the historical combined objective. Replacing the joint SFT term analytically with equal separately normalized old/new coefficients left that dot negative on **three of four** samples.

This is why my previous normalize-the-loss suggestion was incomplete. Equal coefficients do not imply comparable gradient effects, especially when old training loss is already near zero and new tasks are difficult. A new-task coefficient ramp, fresh paraphrased rehearsal and a measured preservation constraint deserve testing together with separate normalization.

Important limits: these are **four batches evaluated at fixed checkpoint weights**, not stored gradients along the actual 100-step trajectory. A negative dot predicts an infinitesimal SGD direction, not the actual AdamW update. It is evidence of a potential conflict, not a causal reconstruction or a reason to install gradient surgery without an ablation. [Gradient Surgery for Multi-Task Learning](https://arxiv.org/abs/2001.06782) establishes this class of problem; it does not validate any particular remedy for this model.

## 6. The generated curriculum permits shortcuts

The 2,592-record bank has eight families, but its semantic diversity is much smaller:

- Only **12 full-name strings, 12 time strings, 12 location strings and four clarification replies**.
- In all 324 answerability examples, the supplied color **perfectly predicts whether an owner is present**. Owner presence was coupled to the same value-index parity used for colors.
- Every initial location has exactly one successor: only **12 location transitions out of 132 possible nonidentity pairs**.
- Target/distractor sentence order is deterministic from the target value index.

These correlations let a model solve parts of the curriculum without learning the intended variable binding. They do **not** prove the model exploited every shortcut: the matched reassessment already breaks some old mappings and still measures genuine gains. They do establish that the training generator must be repaired before scaling it.

The repair must independently randomize identities, values, target order, missingness, corrections, unrelated facts and requested format. Names should include known components in unseen combinations as well as genuinely new strings. Times should cover many hour/minute combinations. Same initial states must have multiple possible updates. Both present/absent variants must occur for the same entities and colors.

## 7. There are three separate project gates

1. **Implementation:** masking, shifted targets, precision, save/reload and finite computation. Existing independent FP32 checks, exact tiny-set fitting and continued loss reduction make a gross engine failure less likely. No new implementation defect was demonstrated by this audit.
2. **Skill learning:** short replies, multi-token copying, question selection, uncertainty and state tracking. Measurable progress exists, but the new tasks need actual fitting, diversity and consolidation.
3. **Broad foundation:** the retained foundation stream is TinyStories, and the attempted broad-corpus D0 admission remains failed; R1/R2 did not start. A low story loss or a successful drill does not establish broad English conversation or knowledge coverage.

[TinyStories](https://arxiv.org/abs/2305.07759) demonstrates fluent story generation at very small scales. My inference is that it supports our narrow language-learning feasibility, not the whole conversation/tool goal. As a different-scale comparison, the official [SmolLM2-135M card](https://huggingface.co/HuggingFaceTB/SmolLM2-135M) reports 2T diverse pretraining tokens and a separate SFT stage; this is not a minimum token budget for this project or a model-size recommendation. It illustrates why our 412M narrative exposures cannot be treated as a reproduced broad-assistant recipe.

The 15.19M model also spends 9.216M parameters (~61%) on its tied 32k embedding, leaving about 5.98M elsewhere. That is an architectural constraint worth measuring later, not proof that current failures require more parameters. Keep 15M as the cheap diagnostic model; leave the final architecture open within the user's 100M ceiling until data and learnability are tested properly.

## Recommendation

Keep both checkpoints and the measured gains. Replace another format-only patch with **one bounded teacher-data bridge and consolidation study**. First admit the existing teacher training candidates and repair the oracle curriculum; then prove multi-token fit; then compare the current objective against a separately normalized, gradually introduced objective on identical corrected data. See [proposed study](PROPOSED_STUDY.md). No part of that future training study has been executed or approved by this audit.

Broad-corpus admission remains a separate prerequisite to claiming a broad English foundation. These skill experiments must not silently substitute for it. Tool-call syntax alone will likewise be insufficient while extracted values and state remain unreliable.

## Accounting and limitations

- Main diagnostics: 760 conditional examples/checkpoint, four gradient triplets/checkpoint, **42.54 seconds / 487,424 analysis positions**. Gradients were calculated, but there were **zero optimizer updates**.
- Seen-example fit supplement: 64 total generations; **7,349 additional positions**, giving **494,773 aggregate**. It completed 246.55 seconds after the original audit start, including preparation/review intervals; this is not all GPU time. Peak main-run RSS 1,277,165,568 bytes (~1.19 GiB); engine peak ~1.33 GiB.
- Bounds: 15 minutes, 2M analysis positions, 12 GiB RSS/GPU, 1 GiB artifacts, 60 GiB disk floor. Source weights and earlier terminal training stops are unchanged.
- A relative/absolute preparation-path mismatch prevented initial freeze creation. The subsequent missing-freeze exception reserved **zero model positions and zero updates**. The setup failure is preserved; repair occurred before model work under the original audit clock. No scientific or training stop was retried or reset.
- Conditional scores are not free-generation successes. Reused development/test diagnostics are not fresh acceptance data. Gradient samples are small and not an AdamW trajectory analysis. Generator correlations show available shortcuts, not established mechanisms of every failure. No model is newly promoted or rejected.
- Private raw forwards, fit responses and teacher payload remain local. Public evidence contains aggregates, hashes and code, without held-out plaintext.

Evidence: [lineage](lineage.json), [exposure inventory](inventory.json), [shortcut audit](shortcut-audit.json), [forward/gradient summary](summary.json), [digit/format split](time-token-analysis.json), [seen-example fit](training-fit.json), [teacher-format readiness](teacher-bank-readiness.json), [resource/result ledger](result.json).
