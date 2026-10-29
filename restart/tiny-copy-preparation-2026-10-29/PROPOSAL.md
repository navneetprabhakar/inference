# Tiny controlled copying test — prepared, not authorized to train

## Purpose and decision

Determine whether the own15.2M-parameter foundation can fit a tiny exact-copying task when names and times are trained **separately**. Previous paired/shuffled training failed both, even on training examples. This test isolates tasks and varies only learning rate within each task; it is not another broad conversation run.

No model execution occurred during preparation. The schedule, value pools, scorer, LR-selection rule and budget are frozen. No training launcher is included. Primary-author semantic checking is complete; no separate-agent or human review is claimed for this new packet.

## Dataset

| Partition | Names | Times |
|---|---|---|
| Fit values |16 full names built from8 first names and8 surnames |16 valid HH:MM values spanning8 hours and16 minutes |
| Familiar-field recombination |16 unseen combinations of the same first/surname fields |16 unseen combinations of fitted hour/minute fields |
| New fields |16 names using disjoint first/surname fields |16 times using disjoint hour/minute fields |

Each task/partition contains8 matched before/after pairs. Both name components or both time fields change within a pair. Every pair appears in two contexts: one target fact alone, and the same fact with one irrelevant fact. The distractor stays fixed within the pair, always differs from either target answer, and occurs before/after the target equally often. This scope intervention also changes prompt length; it does not isolate attention independently of length.

Fit:32 presentations/task,64 total. Transfer:64 presentations/task,128 total, split evenly across the two value-novelty strata. There is one fixed query per task, the same query in both contexts, fixed target entities (parcel owner/meeting time), and one fact representation. This deliberately removes paraphrase and entity novelty. Passing would show narrow copying feasibility, not natural conversation, broad instruction following, or robust retrieval.

All target values and exact user sequences are disjoint between fit and transfer. Novelty is relative to this supervised packet, **not** the foundation pretraining corpus or tokenizer vocabulary. Familiar/new fields do not necessarily mean familiar/new token sequences. Token lengths and segmentation must be reported alongside results. Context including32-token response allowance is at most78 of256 tokens. Every reference fits32 tokens including EOS.

[Review packet](REVIEW_PACKET.md) shows representative paired examples. CPU checks independently extract rendered target fields, validate references/serialization/masks, ensure pair interventions preserve other text, and verify schedule coverage. No names or times were chosen using new model outputs.

## Four fixed arms

| Arm | Task | Learning rate | Updates |
|---|---|---:|---:|
| N-low |Name only|0.0001|128|
| T-low |Time only|0.0001|128|
| N-high |Name only|0.0005|128|
| T-high |Time only|0.0005|128|

All start independently from `restart/foundation-resolution-v1/B/checkpoint.pt`, SHA256 `bf45241501cee600bd618677dc1a3ae666e6f50d9c628e29e7326ee9c87d338d`, with identical fresh optimizer/RNG. Do not continue previous trained endpoints. Retain the validated AdamW configuration, clipping, BF16 compute/FP32 master parameters, assistant/EOS masking and native serialization.

Each update contains four conversations from one task, one from each context×pair-side cell. Every presentation appears16 times across128 updates. Both LRs use exactly the same task-specific schedule. There is no deliberate partner adjacency. Assistant loss is the mean of the four per-conversation target-token means. Replay stays fixed at0.5 with the same existing eight257-token narrative blocks at each update across all arms. This tests feasibility **with replay**; failure cannot rule out replay interference. There is no joint name+time arm, so this does not causally establish multi-task interference relative to the earlier larger run.

## Frozen measurement and selection policy

1. Source: generate all64 fit and128 transfer presentations; teacher-force all64 fit presentations; evaluate512 native narrative blocks. Baseline transfer outputs cannot change this protocol.
2. Each arm: at update64 and128, generate its32 fit presentations and collect per-conversation teacher-forced loss. At128, also evaluate512 native narrative blocks and save the sole endpoint checkpoint. No mid-run checkpoint selection or early stopping based on scores.
3. During the already-budgeted teacher-forced forward passes, collect per-target-token NLL, top1 correctness and first-error position, separated into answer tokens and EOS. This adds no forwards or backward passes. Training logs retain loss and gradient norm. Do not add gradient-probing work outside the cap.
4. Choose **one common LR**, using only endpoint teacher-forced fit losses: for each LR, compute the worse of name/time loss divided by that task's source loss; select the smaller worst-task ratio. Tie goes to0.0001. Do not select a different LR per task or use transfer scores, native NLL, or generated fit scores to change this rule. Report both LRs' fit outcomes even if the selected LR is not the greedy-fit winner.
5. Lock the selection receipt, then generate each selected task endpoint's64 transfer presentations once. The unselected endpoints receive no transfer evaluation. No retraining follows selection.

Generation uses native greedy decoding, normal EOS and32-token cap. The [scorer](metrics.py) requires exact full name or zero-padded HH:MM, allowing only outer whitespace. Wrong case, punctuation additions, partial names, correct content without EOS, BOS and overflow all fail. This deliberately strict copying contract differs from the earlier broader task scorer; cross-experiment score comparisons are descriptive only.

## Acceptance criteria

**Fit gate at update128, per arm:** all8/8 complete before/after pairs correct in **each** context; therefore16/16 individual responses per context,32/32 overall, with correct termination throughout. No averaging across tasks or contexts. Update64 is a learning-curve observation, never an alternative endpoint.

**Selected-LR copying acquisition passes only if both selected task arms pass fit.** Unselected-arm successes are reported as evidence of LR sensitivity, not substituted after seeing outcomes.

**Transfer gate, per selected task, per novelty stratum, per context:** at least7/8 complete pairs correct and all16/16 responses terminate normally. All eight task×novelty×context cells must pass for a narrow transfer pass. Report raw denominators, unchanged-answer errors and distractor-copy errors. The threshold is an engineering screen with small samples, not statistical certification; the two contexts reuse values.

**Research retention guard:** selected endpoints each have native NLL≤1.65×source. Report this separately from fit/transfer. This intentionally permissive guard is not acceptable preservation. The source behavioral floor remains unresolved; no promotion or conversation-quality claim is allowed even if every copying gate passes.

## Outcome branches

- Neither LR fits a task: inspect already-collected token-level fit errors and loss curves before proposing more training. A failure after128 updates under these two LRs/replay0.5 is not a capacity impossibility result.
- Simple fits but distractor fails: investigate competing-fact selection; prompt length is a confound. Do not respond by expanding the conversation curriculum.
- Fit succeeds, familiar-field recombination fails: suspect memorization of whole values rather than copying/composition, as a hypothesis.
- Recombination succeeds, new fields fail: inspect token segmentation and arbitrary-string copying. “New field” is not “unknown token.”
- Both isolated tasks transfer: prepare a matched joint-task follow-up to test interference. The current comparison with the previous broad curriculum cannot establish it.
- Fit/transfer succeeds but retention guard fails: the acquisition/retention tradeoff remains unresolved. No automatic deployment or further updates.

## Proposed bounded budget

| New-work cap | Limit |
|---|---:|
| Optimizer updates |512 total;128 per arm |
| Active model/checkpoint time |15 minutes |
| Input positions |6,000,000 |
| Assistant/EOS training targets |12,544 |
| Narrative training targets |1,048,576 |
| New artifacts |1GiB |

Stop at the first cap. No retries, extra LR values, seeds, updates, full-curriculum training or implicit resume. Save only four endpoint checkpoints; a partial arm is incomplete and cannot be compared as a full endpoint. Unused time never authorizes extra updates.

CPU-derived maximum planned positions are approximately2.83M, including training, all scheduled generated evaluations, teacher-forced diagnostics and five native-NLL evaluations. Conservative historical-latency projection is715.3 seconds (**11.9 minutes**), including120 seconds for startup/checkpoints plus25% reserve. This uses an eight-row historical training p95 for the smaller four-row assistant batches; it is an estimate, not a guarantee. Early EOS can substantially reduce actual use. Active time is distinct from elapsed wall time; count startup, all model work and checkpoint I/O.

Carry forward only the completed paired-fit successor ledger once:5,124 updates,22,593,515 positions and1,592.3618 active seconds. It already includes the earlier calibration/screen/diagnosis chain. Proposed aggregate ceilings: **5,636 updates,28,593,515 positions and41.54 active minutes**. Do not reimport ancestors or reset their budgets; older campaigns remain separately recorded. The new training-target ceilings are training-only; evaluation labels are counted in forward input positions.

[budget.json](budget.json) remains `authorized:false`. After explicit user approval, implement the bounded launcher with the verified adapter, verify source/optimizer/RNG equality and the carry-forward hash, reserve costs before each operation, and keep old ledgers read-only. Changes to this protocol must be versioned before execution. This preparation authorizes no training.
