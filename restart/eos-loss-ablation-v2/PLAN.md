# EOS loss ablation — bounded training study

Authorization: “ok lets continue next steps of training”. New study; all previous stops and budgets remain intact.

Question: does reducing supervised EOS loss fix premature stopping on the same 32 seen fit records? This is a training-fit diagnostic, not a generalization or teacher-data comparison.

Two matched arms start independently from original B weights with fresh Adam/RNG, identical batches/replay, BF16 compute with validated deterministic embedding backward, FP32 masters/moments, clip 1 and LR 2e-5 with five-update warmup. Control keeps assistant-content/EOS loss unchanged. Treatment multiplies only supervised EOS cross entropy by 0.25. Both divide by the original count of supervised targets, so content-token coefficient is unchanged; treatment's total SFT weight is consequently lower. Narrative coefficient remains 0.5 and supervised coefficient 0.5. No EOS modification to narrative loss or decoding. Do not interpret this as constant-total-weight redistribution.

Freeze code/data before model work. First inspect teacher-forced EOS-vs-gold margins on B and the previous fit-200 child, and measure B's free-generation fit baseline. Validate the weighted loss/gradient against independent FP32 PyTorch, plus unchanged content coefficients and zero masked-token contribution, without optimizer updates.

Train alternating control/treatment blocks of 50 updates to 200 each. Do not early-select a successful checkpoint. Every block checks 512-sequence narrative NLL and 32 free-generation fit cases. If either narrative loss exceeds original 1.3430354408919811 ×1.05, gradients become nonfinite/exceed 100, resources exceed limits, or implementation checks fail, stop both arms. No automatic retry. At 200, require ≥15/16 exact complete names and ≥15/16 literal HH:MM times, EOS termination and no overflow. Report intermediate trajectories but compare matched 200-update endpoints. Both endpoints receive read-only EOS/content diagnosis.

Hard cap: 400 new optimizer updates, 5M model input positions (including all diagnostic/reference work), 30,000 supervised target exposures, 1M narrative target exposures, 10 minutes active model time, 5 GiB new artifacts, 12 GiB process/GPU memory, ≥60 GiB free disk. No teacher calls/downloads. The 214 prior invocations remain historical, separately reported; this is not a restart of their ledgers.

No model promotion, no main teacher/control study or fresh final test access under this diagnostic. Completion returns evidence and a concrete next training decision; additional treatment values/longer runs are not silently added. One seed/schedule, primary-authored seen examples, 12 distinct name values across 16 name prompts; results cannot establish general copying or isolate all prior-training causes.

## Reference-harness correction before training

Revision 1 performed zero optimizer updates and stopped because the independent PyTorch forward omitted targets, yielding only last-position logits. Revision 2 passes targets to obtain full-sequence logits, matching the existing verified reference convention. Loss formula, thresholds and training scope are unchanged. The original failure/code remain frozen; this revision carries every consumed ledger charge forward. No model-gate failure was retried.
