# English training result — failed acceptance, real fit learning

Ganesh-base by Navneet Prabhakar is not yet a usable English conversation model.
The approved A100 run trained actual weights; qualification alone was not its goal.
The fit stopped at update 30 because seven development regression guards fired.
No automatic continuation or curriculum run is authorized by this result.

## Execution efficiency and accountability

The30logged training-update intervals sum to23.899seconds. That excludes data
collection, development evaluation, checkpointing, uploads, setup, qualification
and assessment. The fit job occupied roughly18minutes, and the VM was allocated
much longer. This was a diagnostic/qualification campaign with very little learning
compute, not a substantial English training campaign. Infrastructure work dominated
the run. Repeating it unchanged would be a poor use of the approved budget. Reuse
valid evidence bound to the unchanged runtime, and spend future GPU time on a
predeclared learning treatment plus behavioral checks; requalify only affected
boundaries when code or numerical behavior changes.

## Complete raw conversation assessment

All 396 English turn records were read, including malformed outputs and blocked
follow-ups. This is a same-agent diagnostic review, not an independent release.
Greedy decoding, original prompt policies and reply budgets were unchanged.

| Checkpoint | Exposed fit turns | Fully passing fit sessions | Unseen development turns | Fully passing development sessions |
|---|---:|---:|---:|---:|
| 0 | 0/72 | 0/24 | 0/36 | 0/12 |
| 16 | 0/72 | 0/24 | Not scheduled | Not scheduled |
| 20, minimum development loss | 0/72 | 0/24 | 0/36 | 0/12 |
| 30, stopped last | 64/72 | 21/24 | 2/36 | 0/12 |

The frozen fit gate requires at least 23/24 semantically passing sessions, complete
valid actions across all turns, full review, and no forbidden tool actions. It fails.
The two passing development turns do not imply any passing conversation. Minor
wording judgments cannot change the decision: most development failures are missing
termination, irrelevant answers, invented facts, or blocked follow-ups.

Evidence: `assessment/scores.json`, exact raw files and hash-bound per-turn reviews
under `assessment/raw/` and `assessment/reviews/`. Checkpoint 30 is diagnostic only.
No serving default changed, and no HTTP endpoint was enabled.

## What this establishes

- Learning is occurring. At update 30 many exact training conversations produce
  correct natural answers, corrections, state changes and clean assistant endings.
  This is exposed-fit evidence, not generalization.
- Minimum development cross-entropy selected a worse generator: checkpoint 20 has
  CE 3.20395 but no valid completed fit conversations. Last CE is 4.07371 and last
  training loss is 0.56719. Loss alone cannot select a conversation model.
- The tiny diagnostic has 24 training sessions and 656 unique supervised token
  positions. The 13,120 target exposures repeat that material; they are not 13,120
  new examples. It is not an adequate broad English curriculum by itself.
- Checkpoint 30 still fails novel preference recall, correction-following, object
  ownership and missing-input clarification. Training-example recall is ahead of
  transferable instruction following and state tracking.
- Repeated advertisement, video, rating and website boilerplate occurs in raw
  continuations. That is evidence of undesirable learned continuation behavior;
  identifying its precise source in pretraining data remains unproven.
- Actual optimizer recovery is now exact with the explicitly selected eager Muon
  path. The earlier compiled mismatch is real, but it does not establish the cause
  of these conversation failures. Fixing replay alone did not fix English.

## Checks against premature conclusions

The assistant-end token is explicitly supervised by the serializer and shifted
training labels. A missing `autocast` wrapper is not by itself a serving defect:
the pinned model performs compute-dtype casts internally in both train and serve.
Teacher-forced endpoint probabilities were measured separately; they do not
replace free-running conversation scores. Baseline assistant-end probability is
roughly 5e-13 on fit reference endings, median rank32721/32768. At20 none of72fit
or36development reference endings rank the end token first. At30,65/72fit and
26/36development endings rank it first. Therefore the best-loss checkpoint had
not learned to stop even on correct reference answers. Last30has materially better
termination but still fails free-running unseen conversation. End-token supervision
is present; learned end-token likelihood is the problem, not a proven missing mask. No outputs are trimmed or rewritten to
manufacture a pass. The failed controller and persistent guard states remain intact.

## Termination diagnosis: a concrete training-design problem

First-epoch seed103 packed evaluation covers all24sessions/656targets, including
72assistant-end positions. It agrees with isolated conversations on end-token
argmax counts:0/72at0and20,65/72at30. Packing is not the explanation for the
observed failure to stop, although this does not prove packing has no other effect.

| Step | Content-token CE | End-token CE | Median raw end logit | Median softcap derivative |
|---|---:|---:|---:|---:|
| 0 | 2.3325 | 28.6148 | -42.0 | 0.0147 |
| 20 | 0.1954 | 10.5406 | -40.5 | 0.0179 |
| 30 | 0.0041 | 3.9751 | -8.4063 | 0.7416 |

These are teacher-forced packed diagnostic values, not reported training losses.
The head uses15*tanh(logit/15). The initially negative end logit sits in a strongly
attenuated-gradient region. This is direct evidence of suppressed conversational
termination and a plausible reason it adapts later than answer words. It is not
proof that changing this alone will solve generalization. At30content is nearly
memorized while stopping remains less confident and novel conversations still fail.

Protected development tools: all0/8turns at0,20and30; no actual tool calls. Last30
acknowledges Mysuru then reverts to stale Nashik. The diagnostic excluded positive
tool training, so these results do not establish that tool ability regressed from
a capable base; all three candidates fail. Raw outputs and reviews are retained.

## Next remediation boundary

Do not spend the remainder of the cap on blind repetition of this stopped fit.
The development-loss stop is a conservative predeclared rule, not proof that
generated conversation degraded: last30generates better than best-loss20on the
observed suites. Changing the rule after seeing this result requires a new
versioned experiment, not silently clearing the guard.

A revised experiment should address termination learning before broad conversation:

1. Predeclare a bounded conversational-control adaptation treatment against the
   untouched base. Consider supervised control-token warmup or explicit loss
   balancing; neither should be selected without comparing content degradation,
   premature stops and end-token rank on independent scenarios. A static decoder
   that truncates or rewrites answers is not a weight improvement.
2. Keep the existing24fit sessions immutable. Distinguish the limited memorization
   feasibility gate from generalization acceptance; do not demand an overfit toy
   task simultaneously prove broad English, and do not treat it as release.
3. Use the reviewed English curriculum with short answers, varied paraphrases,
   natural closings, correction chains and delayed recall. Split scenario families
   before variants, audit every answer, and count unique targets separately from
   repetitions. Preserve tools-enabled/no-call and tools-disabled/no-call coverage.
4. Select candidates with generated development conversations plus content/end
   losses, not aggregate CE alone. Predeclare guard thresholds and maximum updates;
   compare both best and last. Preserve the original failed run and guard history.
5. Stop if the treatment only memorizes prompts, produces premature endings, or
   worsens independent content/state tracking. No automatic epoch/LR/budget increase.
6. Only after development readiness: fresh independent release conversations,
   protected tool checks and local MPS qualification. Neither a small pilot nor
   unused budget guarantees a general English model.

Evidence: `assessment/closeout/packing-diagnosis/`,
`assessment/termination-summary.json`, and the hash-bound raw conversation reviews.
GPU qualification is finished; the remaining blocker is model learning and
curriculum/selection design. Best20andlast30are now fully hash-verified locally under
`runs/ganesh-a100-cap40-v1/local-fit/`. Last30successfully ran the3turn exposed
appointment-state conversation on local MPS with correct answers and termination.
This confirms runtime availability only; default/HTTPremain unchanged. All four retained fit checkpoints, complete remote raw evidence and final review
archive have passed fresh GCS readback. GCP rejected shortening terminationTime on
a running VM. Normal APIstop was requested after joined writers and backups; this
is explicitly not a successful scheduled-stop fault test. That release prerequisite
remains unproven. No additional training is running or queued.


Closeout confirmed: normal STOP at2026-11-17T23:15:10.675UTC, then the dedicated VM
and200GiBboot disk were removed under existing cleanup authority. Fresh project
inventory shows0VMs/0disks. Required backups were verified before shutdown/deletion.
Estimated cumulative compute/disk including priorL4is$10.61, excluding unsettled
storage/network; conservative margin plus reserves is$20.59under the$40cap.
Scheduled-provider STOP remains unproven; normal stop is not relabeled as that test.
