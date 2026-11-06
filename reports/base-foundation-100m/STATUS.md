# Own-base run: 40M learning checkpoint

Status at the 40M evaluation: training continues. A usable conversational/tool model has **not** been demonstrated.

The student is the 124,439,808-parameter GPT-2 model from our own verified random-initialization lineage. This run continues the protected 2,457,600-target pre-SFT base with fresh optimizer moments, then restores full optimizer/RNG/cursor state between execution leases. No downloaded model weights enter this lineage.

| Additional targets | Held-out CE | Context-sensitive pairs | Greedy loops, blinded AI review |
|---:|---:|---:|---:|
| 0 | 7.0349 | 0/32 | 17/32 |
| 1,007,616 | 6.5526 | 0/32 | 29/32 |
| 5,005,312 | 6.1033 | 0/32 | 32/32 |
| 10,002,432 | 5.8357 | 0/32 | 32/32 |
| 20,004,864 | 5.5142 | 0/32 | Not independently rated |
| 30,007,296 | 5.2862 | 0/32 | Not independently rated |
| 40,001,536 | 5.1327 | 0/32 | Not independently rated |

The train-only unigram reference has CE 7.5294 on the same 256 validation windows. The first-window CE improvement was 0.4823 nats (descriptive paired document SE 0.0143). At 5M, CE improved another 0.4493 nats (SE 0.0091) versus 1M. At 10M, CE improved another 0.2676 nats (SE 0.0045) versus 5M. Domains can correlate, so this SE is not an independent-domain uncertainty estimate.

Loss improved, but separate-context AI reviewers found zero relevant completions at all four checkpoints. Loop counts were 17/32, 29/32, 32/32 and 32/32 respectively. Ratings are subjective AI review, not ground truth; the randomized labels, rubric, raw outputs and unblinding receipt are preserved in `completion-review-001m/`, `completion-review-005m/` and `completion-review-010m/`. No conversational-quality improvement is claimed.

A separate mechanical check, applied retrospectively using the optimizer screen's frozen rule (any generated four-token sequence repeated at least three times), flags 17, 29, 32, 31, 32, 32 and 32 of 32 completions at the seven checkpoints above. These counts are not independent relevance judgments and do not replace the blinded ratings. In particular, the 40M checkpoint still produces repetitive completions despite lower held-out CE.

## Operation

- Run: `runs/own-base-foundation-01`; launched 2026-11-06 around 07:08 IST.
- Frozen ceiling: 99,999,744 attempted targets, 36 active hours, seven calendar days. At approximately 45M, measured throughput is about 1,444 targets/second, giving roughly 10.6 active hours remaining; use the live status for subsequent estimates.
- Next measurements: every 10M and the actual endpoint. Temporary resource stops and four-hour leases use the bounded supervisor.
- Live status: `runs/own-base-foundation-01/status.json`; full fixed evaluations: `validation.json`; supervision: `runs/own-base-foundation-01-supervisor.json`.
- LaunchAgent: `local.forge.own-base-foundation`. AC-only system-sleep prevention is bounded to the supervisor's lifetime. No display-sleep override.
- Explicit stop: create `runs/own-base-foundation-01/STOP`. The supervisor never removes or overrides it.
- Runtime/training code and budget remain frozen. CPU recovery, milestone interruption, corruption/identity and supervisor tests pass. Production step96 and protected step123 full optimizer checkpoints were published successfully.

`base_sample.py` provides explicit-checkpoint, CPU-only raw completion inspection. Its 20 small CPU tests passed after the baseline context-limit correction; an earlier actual one-token smoke run against protected step123 completed. It does not provide an assistant or execute tools. See `README-base-sample.md` at repository root.

The existing chat preview remains the earlier experimental assistant. This foundation run does not silently replace it.

Exact CPU value verification reproduced every original parameter from random seed103 and verified live initial weights equal the protected own-parent checkpoint; see `lineage-value-verification.md`. An isolated bare-MLX tiny CPU port also passed three-seed numerical checks; GPU speed and full-runtime migration remain untested. It does not participate in this frozen training run.

A second isolated MLX experiment passed tiny CPU optimizer-state conversion and exact fresh-process resume for three seeds, including 21 refusal checks. It preserves AdamW moments instead of resetting them. This is preparation for a possible future runtime; full-model GPU speed, mixed precision and production recovery remain untested. See `reports/mlx-own-base-resume-feasibility/README.md`.

The user approved the corrected three-arm optimizer experiment on 2026-11-06. Its frozen protocol is `reports/optimizer-ablation-v1/PROTOCOL.md`. It waits for the exact completed 100M endpoint, then compares preserved moments, reset moments and reset moments with beta2=0.9991988633566534 on the same next 19,996,672 targets per arm. All arms use a common explicit LR restart. CPU verification and independent review passed. No optimizer-screen outcome constitutes an assistant-quality pass.
