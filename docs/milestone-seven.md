# Loss accuracy and full-size NVIDIA validation

Creator: Navneet Prabhakar

Date: 18 October 2026

## Outcome

Full-size training-trajectory portability remains unaccepted. An accurate experimental cross-entropy formulation now has explicit recipe/checkpoint versioning. It fixes a measured cancellation problem but does not resolve trajectory drift. The validated legacy loss remains the default; no comparison tolerances changed.

## Loss accuracy investigation

The original expression subtracts the selected target logit from log-sum-exp. In a 16,384-class control with all other logits zero, target logit 20 has analytic loss 3.376730967e-5. The legacy implementations give 3.242492676e-5 on PyTorch and 3.433227539e-5 on MLX. At target logit 30 both give zero, whereas the analytic loss is 1.533059370e-9.

The opt-in `max-centered-target-tail-softplus-v1` computes the non-target tail relative to a detached maximum, then evaluates log-add-exp against zero. Analytic tests check the loss and every gradient, including confident/incorrect targets, representable common offsets, random multiclass FP64 controls and the one-class edge case. For MLX, operand order matters to the tiny-gradient result; the margin is the first operand. This is an accuracy result, not evidence of identical optimization paths.

Recipe and checkpoint metadata persist the exact loss implementation. Older accepted checkpoints without this field restore the legacy version. Conflicting recipe/reproduction versions are rejected. Training, resume, probe capture and overfit measurement use the selected version consistently.

## Failed candidates retained

- A controlled tiny 100-update diagnostic with the new formulation fails the original first-moment comparison from update 62: maximum difference at the first failure is 1.049833e-6. Across the run, maximum first-moment difference is 1.489883e-6. Weight maximum difference is 3.367662e-6. The legacy default still passes its existing 100-update test.
- A fresh 80,765,440-parameter experiment uses batch seed 211, initialization seed 109 and the explicit experimental recipe in `configs/experimental-stable-loss-recipe.json`. MLX → CPU updates 2–4 pass the unchanged research policy, but CPU → MLX updates 4–6 fail a layer-10 comparison: absolute difference 1.0224991e-5 at the violating element.
- The research policy was already rejected in milestone six and remains rejected. Improving scalar loss accuracy is insufficient to accept full-size training parity. These negative diagnostics are recorded separately from passing unit tests.

## Full-size learned-checkpoint control

The actual MLX checkpoint after 100 synthetic updates passes the 2,048-position finite and causal/cache checks locally. All logits and layer states are finite; selected cross-host comparison positions are 0, 127, 1,023, 1,024 and 2,047. MLX full-sequence versus cached final-token maximum difference is 4.768372e-6. The same learned checkpoint also passes the local PyTorch CPU comparison against the MLX reference, with a cache maximum difference of 4.291534e-6. This control tests a learned checkpoint rather than relying only on random initialization. It does not establish English ability.

## NVIDIA validation

A single private NVIDIA T4 VM in `executespecv1` completed all four independent job checks. It used a 45-minute server-enforced deletion limit, no external IP and no service account. The input archive SHA-256 is `bd2a88eefdce1e6189bb67ca280c07872f4323ff63e2da69f612c687ebb72d4c`; remote verification matched. The returned result archive SHA-256 is `ce857f8cf6bd0c81635e7bea78f63aad501bfa68c28936ba26d1e047c2760afa`; download verification matched. Neither archive is tracked in Git.

| Check | Result and limitation |
| --- | --- |
| Learned training-state import | All 654 tensors / 242,296,320 values exactly preserved on CUDA, with update-100 counters and recipe; zero optimizer updates in this audit |
| Learned 2,048-context inference | Finite full logits/layers and causal/cache checks pass; selected logits/layers match MLX at unchanged bounds; selected-logit max difference 2.861023e-6, CUDA cache max difference 4.768372e-6 |
| FP32 training workload | B1 × 1,024 positions, two warmup and five timed updates; 5,120 positions / 3.786581 seconds = 1,352.14 positions/second; peak allocated GPU memory 3,442,220,032 bytes |
| CUDA host tests | 71 passed, 17 skipped in 11.12 seconds; skips cover missing MLX and the guard that requires an unavailable CUDA device; includes the 100-update tiny CPU/CUDA resume test and three analytical CUDA loss checks |
| Runtime | Python 3.12.3, PyTorch 2.9.1+cu129, CUDA 12.9, Tesla T4; TF32 disabled |

The training benchmark starts from its own random initialization and diagnostic recipe. It does not train the imported update-100 checkpoint or compare full-size training trajectories. The job's all-checks-passed field applies only to its four named checks and does not override the failed trajectory gates. The 2,048-context comparison samples five positions after checking finiteness everywhere; it is not an all-position equality assertion.

On the M4 laptop, the identical 1,024-position workload measured 1,345.53 processed token positions/second over five timed updates after two warmup updates (3.805 seconds total). The reported MLX allocator peak is 3,960,880,276 bytes; process RSS is a separate lifetime high-water statistic and must not be added to allocator memory. This is a short synthetic measurement, not sustained thermal performance.

The benchmark counts processed token positions after warmup and includes host gradient checks. It is neither a production throughput claim nor a training-quality result. No main pretraining or paid teacher generation is authorized by this validation.

## Evidence and remaining gates

- Local suite: **96 passed, 5 skipped**; CUDA host: **71 passed, 17 skipped**. Separate host suites do not establish a full-size training round trip. See the two milestone-seven test reports.
- NVIDIA state/context/benchmark/job evidence: `reports/milestone-seven-cuda-*.json`, input manifest, host snapshot and driver output. Cleanup evidence is recorded in `reports/milestone-seven-cleanup.json`. The VM, boot disk and temporary firewall were verified absent at 18:01:47 UTC after result download. The cumulative USD 10 validation authorization remains the limit; conservative allowances total USD 3 across both jobs, with settled billing unknown.
- Analytic controls: `reports/milestone-seven-loss-accuracy.json`.
- Failed diagnostics: `reports/milestone-seven-candidate-tiny100.json` and `reports/milestone-seven-stable-loss-trajectory.json`.
- Accepted full-size training criteria, reduced precision, production tokenizer, source review, calibrated production data gates, teacher integration and language-training pilots remain open. Public-source approvals remain zero.

A separate [portability acceptance proposal](portability-acceptance-proposal.md) is pending review. It distinguishes exact state/inference/quality portability from tight training-trajectory matching. It changes no gate and authorizes no paid training.

## Reproduce the candidate diagnostic

Use fresh destinations. The last command is expected to fail the recorded trajectory gate; it is not an acceptance recipe.

```sh
OMP_NUM_THREADS=4 .venv/bin/python -m slm.eval.portability create --config configs/target-81m.json --recipe configs/experimental-stable-loss-recipe.json --seed 211 --initialization-seed 109 --comparison-policy full_depth_fp32_v1 --output checkpoints/new-stable-origin --backend mlx
OMP_NUM_THREADS=4 .venv/bin/python -m slm.eval.portability verify --bundle checkpoints/new-stable-origin --output checkpoints/new-stable-cpu --backend torch
OMP_NUM_THREADS=4 .venv/bin/python -m slm.eval.portability verify --bundle checkpoints/new-stable-origin --resume checkpoints/new-stable-cpu/checkpoint --output checkpoints/new-stable-return --backend mlx
```

The bounded benchmark is independently reproducible on either backend; use `--backend torch --device cuda` on an actual NVIDIA host:

```sh
OMP_NUM_THREADS=4 .venv/bin/python -m slm.eval.benchmark --config configs/target-81m.json --output checkpoints/new-benchmark-mlx.json --backend mlx --length 1024 --warmup 2 --steps 5
```
