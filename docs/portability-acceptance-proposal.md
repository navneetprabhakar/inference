# Portability acceptance decision

Creator: Navneet Prabhakar

Status: **Option A accepted by Navneet Prabhakar on 19 October 2026.** Versioned decision: `configs/portability-acceptance-v1.json`.

The recorded user response is “A: Exact state transfer, inference parity and measured resumed-training quality (Recommended)”. This supersedes the previous request for an A/B decision. Exact state transfer, same-checkpoint inference and measured resumed-training quality now govern portability acceptance. Existing trajectory failures remain failed diagnostics; existing inference tolerances are unchanged. The resumed-training quality gate has not yet been demonstrated. This decision authorizes neither new spending nor blanket dataset admission.

## Question resolved

Does seamless MLX/CUDA portability require tightly matching multi-update training trajectories, or portable state plus verified inference and measured quality after resumed training?

## Evidence already available

- Tiny FP32 MLX/CUDA round-trip continuation and 100 CPU/CUDA updates passed.
- Full-size MLX/CPU training-state imports preserve all 242,296,320 weight/moment values and counters exactly.
- Full-size fixed-checkpoint inference and 2,048-token context checks pass locally, including the checkpoint after 100 synthetic updates.
- Full-size training trajectories fail the declared comparison gates. The scalar-loss accuracy candidate does not close them and also regresses the tiny first-moment criterion.
- Short synthetic memorization is not a conversation-quality evaluation. No reviewed public-data release or language-trained checkpoint exists yet.

## Additional evidence from numerical localization

[Milestone twenty-two](milestone-twenty-two.md) reproduces the dense repeated-token failure at update 65. A deliberately one-ULP-perturbed embedding coordinate also causes a PyTorch-only trajectory to fail the original bounds at update 67. Across 18 fixed common-state anchors, isolated optimizer and complete one-update comparisons still pass the original bounds. A separate 81M common-state FP64 check shows small gradient errors on its one tested batch. These results support numerical sensitivity as a contributor; they do not establish general model correctness or comparable learned quality. At the time of those experiments, no criterion had been waived. The subsequent Option A decision changes the role of trajectory comparisons to diagnostics while retaining every failure.

The accepted choice below changes whether tight long-run trajectory agreement blocks subsequent functional portability work. It does not mark those failed comparisons as passing, authorize paid training, approve datasets or accept an unreviewed quality suite.

## Option A: state, inference and quality portability

Use three separate release gates:

1. Exact checkpoint schema/content transfer, optimizer moments, counters, tokenizer/data identity and versioned numerical recipe. Test same-backend resume exactly and verify imported values on each destination.
2. Same-checkpoint logits, layers, causal/cache behavior and deterministic generation under declared, independently validated precision-specific tolerances. Validate on actual MLX and CUDA hardware. Preserve existing fixed-checkpoint bounds; do not loosen them through this proposal.
3. Finite, useful resumed training and comparable held-out quality across separately continued runs. Before new runs, specify held-out tasks, confidence intervals/effect-size thresholds, seeds, token exposure, loss and regressions. Require conversation/tool evaluations when those capabilities exist. Until then, only a synthetic smoke result can be claimed.

Retain trajectory diagnostics as recorded failures. This option does not rename them as passing or claim bitwise-equivalent training. It permits data/tokenizer and language-pilot work to progress while long-run reproducibility is evaluated through predeclared quality gates. It does not authorize paid training or teacher generation.

## Option B: strict training trajectory portability

Keep the existing full-size trajectory comparisons as a prerequisite. Continue reference-kernel/reduction/optimizer investigation before any claim of full-size training portability. Costs include additional numerical engineering, reduced optimization freedom and separate validation for every precision/kernel change. No completion date or assurance of a practical tolerance can currently be justified.

## Recommendation for review

Option A is accepted. Option B is retained as the alternative considered, not an outstanding decision. All historical failed comparisons remain recorded. Actual useful resumed-training quality, reduced precision and sustained performance still require measured evidence.
