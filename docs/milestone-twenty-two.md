# Numerical drift localization

Creator: Navneet Prabhakar

Date: 19 October 2026

Status: scoped localization complete; acceptance policy unchanged and pending review.

## Findings

The repeated-token diagnostic is sensitive to small arithmetic changes even within one backend. Changing one FP32 embedding coordinate by one representable step in a PyTorch-only run causes the existing trajectory gate to fail at update **67**. The untouched CPU reference and perturbed run share the same code, batches, optimizer and hyperparameters. The initialization is deliberately different; this is a sensitivity intervention, not a same-checkpoint portability test.

The fresh dense MLX/CPU baseline fails its first-moment gate at update **65**, preserving the prior negative result. Neither tolerances nor model/optimizer implementations were changed.

| Intervention, 100 updates | First original-bound failure | Maximum final weight difference |
| --- | --- | --- |
| Dense MLX vs PyTorch CPU baseline | 65 | 0.0085233152 |
| CPU only, one embedding coordinate moved one ULP | 67 | 0.0031356687 |
| CPU only, every initial weight moved one ULP | 65 | 0.0125047136 |
| CPU gradients with MLX optimizer arithmetic | 67 | 0.0044301260 |
| MLX gradients with CPU optimizer arithmetic | 64 | 0.0138724353 |

The hybrid runs transfer FP32 values at each update; they deliberately change where arithmetic runs. Both can diverge, so replacing just the loss or optimizer is not established as a remedy. These are training-fixture losses, not held-out quality comparisons.

The one-coordinate intervention changes `embedding[1,0]` from -0.010244854725897312 to -0.010244853794574738: **9.313225746e-10**. A no-intervention CPU hybrid adapter remains exactly identical to its direct CPU reference over all 100 updates, including metrics, weights and moments. The original 100-update dense MLX/CPU golden control passes its original bounds.

## Common-state controls

At steps 0, 49, 59, 62, 63, 64, 69, 79 and 99, load the exact same weights/moments from each saved CPU and MLX trajectory into both backends. Across these **18 common-state anchors**, both isolated common-gradient optimizer updates and complete own-gradient single updates pass the original weight/moment bounds. Maximum complete-update weight difference: **2.7381e-7**.

At nine CPU anchors, MLX and PyTorch gradients are compared to the existing independent FP64 complex-RoPE/native-CE reference. Observed global relative L2 gradient errors range from approximately **1.4e-7 to 2.5e-6**. These fixed-state checks isolate arithmetic error from subsequent accumulation; passing them does not make the separate 100-update trajectories pass.

The final reproducible audit evaluates FP64 gradients at all 18 CPU/MLX anchors; maximum global relative L2 error is **2.58e-6**. Eight centered finite-difference checks at the initial and step-99 states validate selected `layers.0.v` derivatives with two step sizes; maximum absolute discrepancy **6.92e-10**. This checks the oracle's local derivative consistency, not a complete mathematical proof of the model or full trajectory.

## Full-size fixed-state check

The **80,765,440-parameter** original full-model checkpoint after two updates is compared on one retained fixture batch. Its retained model, optimizer, state and batch files are verified against the historical retired-bundle manifest. The retired multi-step expected probes are not restored or represented as validated here.

Independent FP64 loss: **6.7528373735**. Default-loss gradient global relative L2 errors: **1.58e-6 PyTorch CPU**, **4.91e-7 MLX GPU**; maximum absolute errors **6.25e-7** and **3.05e-7** respectively. The existing opt-in stable-loss formulation yields similar errors on this batch. It is not selected as a production fix and no full-size multi-update claim follows from this one checkpoint.

## Interpretation and limits

The results support accumulation/amplification of small numerical differences as a contributor to the repeated-token failure. They do not prove the absence of implementation defects, explain every full-size trajectory, establish comparable held-out quality or resolve native MLX lookup nondeterminism. The diagnostic dense embedding mode is deliberate; native remains default.

Original strict bounds remain weight `atol=1e-5, rtol=1e-4` and moment `atol=1e-6, rtol=1e-4`. Failed historical and fresh trajectory checks remain failed. No gradient rounding/clamping, larger epsilon, tolerance change, default loss change, production recipe selection, cloud job or teacher call is introduced.

The [portability acceptance proposal](portability-acceptance-proposal.md) distinguishes exact state/inference plus measured quality from tight multi-update trajectory matching. New evidence informs that pending decision; it does not approve either policy automatically. Data/tokenizer/teacher/suite review and real language pilots remain open.

## Reproduction and evidence

`scripts/audit-drift-sensitivity.py` is a local MLX/CPU diagnostic. It fixes seed 42, four CPU threads, 100 updates per trajectory, the documented repeated-ID data and unchanged default epsilon/loss. Dense embeddings isolate the known native-lookup confound. The experiment has 14 tiny trajectories (1,400 optimizer updates), 18 shared-state anchors and four separate full-model gradient probes; it is not a language-training pilot. Runtime: MLX 0.32.4 GPU and PyTorch 2.14.1 CPU on the M4, Python 3.12.11. No new dependencies, teacher calls or cloud jobs.

```sh
python scripts/audit-drift-sensitivity.py --output REPORT.json --artifacts FRESH_PRIVATE_DIR --full-fixture checkpoints/fullsize-origin --require-trajectory-pass
```

This invocation intentionally exits **1** because the trajectory gate fails, while its report states `audit_completed: true` and `trajectory_gate_passed: false`. Without the gate flag, successful diagnostic execution can exit zero; it still reports the failed criterion. Fresh destinations are required. For a retired fixture, only retained checkpoint/batch files are verified against its historical manifest; missing probes are not treated as verified.

Evidence: `reports/milestone-twenty-two-sensitivity.json`, source and raw artifact hashes, and ignored arrays/histories under `data/drift-sensitivity-v2/`. The first reproducible wrapper stopped on a missing metadata-helper argument before publishing a result; its log is retained and hashed separately. The corrected wrapper reproduces the negative criterion with all positive/oracle controls intact. Numerical model and optimizer files are unchanged.

A renewed app question presents the two policy choices with this new evidence. No selection or approval is inferred from elapsed time. CUDA validation allowances remain **USD 7 of USD 10**, settled charges unknown; this milestone adds no paid work or source approval.
