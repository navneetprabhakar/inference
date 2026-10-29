# Inference-only binding diagnosis — 29 October 2026

**Result: simpler context and explicit copying do not broadly rescue supplied-fact accuracy. No training or promotion.**

Executed 1,024 responses from the fixed diverse/replay arm-1 endpoint: four task families, 32 previously exposed D scenarios each, eight matched conditions. All 128 original-condition responses exactly reproduced earlier outputs, scores and termination flags. Changed fact scope (full versus one relevant fact), representation (key/value versus sentence), and query (original versus explicit copy). Answers and target order were preserved.

Correct responses out of 32:

| Fact scope / format / instruction | Name | Time | Location | Color with distractor |
|---|---:|---:|---:|---:|
| Full / KV / original | 9 | 28 | 4 | 2 |
| Full / KV / copy | 10 | 28 | 4 | 4 |
| Full / sentence / original | 5 | 25 | 1 | 0 |
| Full / sentence / copy | 5 | 32 | 0 | 0 |
| Single / KV / original | 7 | 29 | 3 | 2 |
| Single / KV / copy | 8 | 29 | 1 | 3 |
| Single / sentence / original | 7 | 23 | 7 | 2 |
| Single / sentence / copy | 9 | 23 | 1 | 2 |

Scores require the correct content, EOS, no BOS and no context overflow. These are short structured retrieval probes, not acceptable-conversation measurements. See [assessment.json](assessment.json) for paired gains/losses and [result.json](result.json) for execution accounting.

## Interpretation and limits

- A simple distractor-overload explanation is insufficient: single-fact name, location and color answers remain weak. Extra copy instructions are not a general fix.
- Time reaches 32/32 in one condition, while other formats regress. This is sensitivity on reused examples, not a new generalization result.
- The earlier association errors plus these failures justify testing broader entity/value coverage and paired fact changes. They do not establish an internal mechanism, capacity ceiling, optimal loss, or that the proposed curriculum will work.
- Only one checkpoint and 32 underlying scenarios per family; eight conditions reuse them. Scope changes both fact count and length. Sentence conversion changes wording and length. Explicit copy uses one query per family. No causal claim isolates those factors fully.

## Integrity

Zero optimizer applications; optimizer application was forbidden during execution. Parameter digest before/after: `1b552a9a28fe36ef33d98540971e03f5e154109fa8d38edf74bf78b8c7769dae`. Separate inference ledger charged 282,800 input positions and 17.462956 seconds. No final test used. Historical training allowances remain closed: 4,612 cumulative updates; unused time is not permission for more updates.

## Reassessment before further training

The next step is a controlled fit test of the [revised candidate](../contrastive-curriculum-2026-10-29/DATACARD.md), after semantic review and a separately approved, frozen budget. Do not launch another full four-arm screen yet.

1. Review the new packet for ambiguous prompts, label correctness, missingness, correction semantics and shortcut correlations; resolve review findings before training.
2. Implement a matched order control: identical records, target tokens, presentations, replay, initialization and update count; paired-adjacent versus independently shuffled order. This isolates pairing order, not the entire new curriculum. A comparison against the old screen would confound size, coverage and presentation changes.
3. Predeclare a small fit subset and measurements: both members correct, answer changes with the fact, unchanged-answer rate, complete state trajectories, unfamiliar full-name copying, and native NLL. Select fit hyperparameters using training-only evidence. The old LR is a starting hypothesis, not newly validated here.
4. Prepare successor accounting carrying all prior calibration/screen usage plus this inference usage separately. Include replay, evaluation, checkpoint and startup costs; do not reuse or reset exhausted ledgers. No updates are authorized by this document.
5. If fitting fails, inspect per-target loss, gradients and decoding on the fixed subset before expanding scale. If fitting succeeds but new-entity/value transfer fails, revise compositional coverage. Only after both improve should natural conversation development and broader retention assessment resume. The source behavior floor remains inconclusive; native NLL alone cannot certify preservation.

Current decision: candidate prepared for review and experiment design; no acceptable conversational model and no evidence yet that additional training will solve the bottleneck.
