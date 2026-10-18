# Full-depth FP32 numerical policy v1

Creator: Navneet Prabhakar

**Status: rejected as an acceptance policy by the independent full-size tests.** The failed results are retained; this policy has not been widened to pass them. It remains an explicit diagnostic option, not a production portability certificate.

This policy is fixed before independent validation with batch seed 137 and initialization seed 73. Calibration used seeds 91/42 and remains diagnostic evidence, including failed prototype pointwise comparisons. Do not retune this policy using the independent validation result.

## Basis and checks

The tiny prototype's pointwise 1e-6 gradient floor and 1e-5 logit floor were debugging bounds. At 24 layers/width 512, the FP64 diagnostic shows both FP32 implementations deviating from the higher-precision trajectory: after two updates, maximum logit errors were 2.27e-5 (MLX) and 2.73e-5 (CPU), with maximum per-tensor relative gradient L2 errors 8.71e-6 and 1.17e-5. Gradient sign disagreements concentrate near zero. Adam's response near zero is sensitive to its epsilon. A 1e-6 epsilon ablation reduced but did not eliminate prototype pointwise failures; it is not selected as a fix or a production hyperparameter.

For full-depth logits, cached logits and gradients, require **both**:

- Relative tensor L2 error at most `B = L * sqrt(d) * u = 3.2369e-5`, with FP32 unit roundoff `u = 2^-24`, L=24 and d=512.
- Maximum absolute error at most `B * max(1, max_abs(reference))`.

This is an engineering accuracy target informed by depth/width-scaled roundoff and checked against FP64. It is **not a rigorous worst-case floating-point error theorem**, especially through Adam or long training trajectories. Zero reference tensors retain the original absolute floor rather than dividing by zero. State transfer does not become exact arithmetic under this policy.

Loss, per-layer states, parameters and both optimizer moments retain their original pointwise bounds: gradients/moments use 1e-6 absolute plus 1e-4 relative; other tensors use 1e-5 absolute plus 1e-4 relative. The gradient exception above adds strict tensor-relative and maximum-error checks while replacing the unstable near-zero pointwise criterion. The tiny policy remains unchanged. The full-depth policy is restricted to the documented 24-layer, width-512, FFN-1536, 8/2-head architecture with 16K/24K vocabulary candidates.

The fixture records the policy before execution, under its checksum manifest. Verification takes the policy from the immutable fixture; it has no command-line tolerance override. Reports retain violations of the prototype pointwise gradient/logit check, even when the full-depth criterion passes. A coherent tensor distortion that fits a tiny absolute floor can fail the full-depth relative-L2 check.

## Acceptance scope

Require independent-seed MLX/CPU continuation and return transfer, whole-parameter/gradient/moment checks, and context-boundary tests. Actual NVIDIA full-depth validation and longer-run drift must be measured separately. No public-data learning quality, mixed precision or trained-model behavior is established by this policy.

The FP64 reference uses independent complex-valued RoPE, native cross entropy and native AdamW, starting from identical FP32 checkpoint values. Gradients and updated parameters/moments are projected to FP32 at update boundaries. It is a high-precision diagnostic for implementation/rounding analysis, not a second production training backend. Its rotary gradient has a finite-difference check.

## Independent validation outcome

The default-epsilon fresh-seed run failed the maximum-logit bound. Two further fresh-seed epsilon-1e-6 runs passed their CPU outbound phase, then failed the unchanged per-layer pointwise check on return to MLX (layers 10 and 6). Full-size training round-trip acceptance remains open. No tolerance changes followed these failures. See `reports/milestone-six-fullsize.json` and the milestone report.
