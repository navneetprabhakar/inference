# Tiny name/time copying — fit passes; transfer fails

**The model can fit this tiny isolated copying packet. It does not reliably copy unseen values.** All four arms completed128 updates within the approved512-update/15-minute/6M-position envelope. No promotion or additional training.

## Frozen fit outcomes

| Task | LR | Correct at64 | Correct at128 | Endpoint fit loss | Native NLL/source |
|---|---:|---:|---:|---:|---:|
| Name |0.0001|28/32|32/32|0.04524|1.0622×|
| Time |0.0001|32/32|32/32|0.00675|1.0634×|
| Name |0.0005|32/32|32/32|0.00132|1.3992×|
| Time |0.0005|4/32|32/32|0.00264|1.4119×|

Every endpoint meets8/8 complete pairs in **each** simple/distractor context, with normal EOS. Teacher-forced endpoint top1 accuracy is perfect for every answer token and EOS in all four arms. Source scores0/32 on both fit tasks. The high-LR time arm's4/32 at64 and32/32 at128 also shows why a short intermediate evaluation alone would have misdiagnosed inability to fit.

The frozen training-only rule selected common **LR0.0005** by the smaller worst-task source-normalized endpoint loss. Selection was recorded before either selected checkpoint's transfer evaluation. All four fit results are reported; no unselected endpoint was substituted after seeing transfer.

## Selected-endpoint transfer

Each row below contains16 responses, or8 matched before/after pairs. Transfer requires at least7/8 complete pairs in every cell, with normal termination throughout.

| Task / value stratum | Simple: responses; pairs | Distractor: responses; pairs |
|---|---:|---:|
| Name, familiar-field recombination |8/16;3/8|8/16;3/8|
| Name, new fields |0/16;0/8|0/16;0/8|
| Time, familiar-field recombination |2/16;0/8|1/16;0/8|
| Time, new fields |4/16;0/8|2/16;0/8|

**Zero of eight transfer cells passed.** Name total16/64; time9/64. All128 selected transfer responses terminated normally. This is an answer-content failure, not an EOS failure. Removing the distractor does not resolve it. These are paired synthetic diagnostics using the same fixed wording/entities; neither prompt novelty nor long context is needed to expose failure.

[Error audit](transfer-error-audit.json): all16 wrong familiar-field name responses reproduce a complete training name. Of32 wrong new-field name responses,29 reproduce a training name. Examples: Alicia Conrad→Alicia Abbott; Inez Iverson→Derek Easton. For time,26 of55 wrong responses reproduce a complete fit value; others form wrong values such as15:00→15:40. This supports a memorization/limited-composition interpretation, without proving an internal mechanism or excluding every alternative.

## What changes in the assessment

1. **Basic acquisition is feasible on a tiny isolated task with replay0.5.** No evidence here supports declaring an unavoidable optimizer failure or capacity ceiling. Perfect fit is compatible with memorization; it is not evidence of a general copying algorithm.
2. **Unseen-value generalization is the immediate unresolved issue for the selected endpoints.** Fit success did not carry to familiar-field recombinations, much less new name components. “New field” means absent from this supervised packet, not absent from pretraining/tokenizer vocabulary.
3. **We have not established multi-task interference.** This differs from the previous study in task count, dataset size, prompt complexity and repetition. There is no matched joint-task arm. Do not attribute the improvement solely to task isolation.
4. **The LR selection objective has a practical weakness.** Lower LR already achieves perfect fit and approximately6.2–6.3% native-NLL degradation; selected higher LR lowers fit loss further while degrading NLL approximately40–41%. The preregistered rule was followed, but minimizing confidence loss after exact fit is achieved is not demonstrably the right future selection policy. No transfer conclusion is available for the low-LR endpoints because the protocol excluded it.
5. Both selected endpoints pass the permissive1.65× native-NLL research guard. This is not acceptable behavioral preservation; the source behavioral floor remains unresolved. No conversational acceptance measurement occurred.

## Recommended next step

**Do not train again yet.** First propose a small inference-only comparison of the two saved low-LR endpoints on this same transfer packet. Report it as posthoc diagnostic reuse, not fresh validation. It would determine whether the lower-retention-cost endpoints also transfer better, without another optimizer update. Keep the current result and selection receipt immutable.

Then revise the next training proposal around value/compositional coverage and a new prespecified selection rule that considers exact fit and retention, rather than merely driving tiny-set loss lower. Freeze new transfer pairs before such training. A joint-task interference experiment becomes useful only after the copying-generalization question is better characterized; simply adding tasks now would mix unresolved causes.

This next step is a recommendation only. No extra inference or optimizer work beyond the approved protocol was run.

## Execution and accounting

- Exactly512 new updates: four arms×128,12,544 assistant/EOS targets,1,048,576 replay targets. Fresh foundation parameters/RNG matched across arms; optimizer state matched within LR.
- Exactly576 generated responses: source192, four arms' fit evaluations256, selected transfer128. Teacher-forced fit diagnostics used320 presentations. Five native-NLL evaluations used512 blocks each. No unselected transfer evaluation, seed sweep or retry.
- New input positions2,254,325 of6M; new active time140.0975 seconds (**2.33 minutes**) of15 minutes. Active time includes startup/model/checkpoint work, not orchestration wall time. Earlier conservative bounds assumed full32-token responses.
- Prior successor ledger imported once, including its existing calibration/screen/diagnosis history. Final successor totals: **5,636 updates,24,847,840 positions,1,732.4593 seconds (28.87 active minutes)**. Older campaigns remain separately recorded. Historical ledgers and frozen inputs unchanged.
- Four checkpoints and outputs occupy approximately730MB, below1GiB. [Audit](audit.json) confirms caps, counts, hashes, initialization, selected-only transfer and carry-forward. [Result](result.json) retains exact accounting; [assessment](assessment.json) retains token and pair metrics.
- The512-update allowance is exhausted. Unused minutes/positions are not permission for more work. No final test or model promotion.
