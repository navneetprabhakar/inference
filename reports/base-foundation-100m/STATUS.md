# Own-base run: first learning checkpoint

Status at the first evaluation: training continues. A usable conversational/tool model has **not** been demonstrated.

The student is the 124,439,808-parameter GPT-2 model from our own verified random-initialization lineage. This run continues the protected 2,457,600-target pre-SFT base with fresh optimizer moments, then restores full optimizer/RNG/cursor state between execution leases. No downloaded model weights enter this lineage.

| Additional targets | Held-out CE | Context-sensitive pairs | Greedy loops, blinded AI review |
|---:|---:|---:|---:|
| 0 | 7.0349 | 0/32 | 17/32 |
| 1,007,616 | 6.5526 | 0/32 | 29/32 |

The train-only unigram reference has CE 7.5294 on the same 256 validation windows. The model's first-window CE improvement is 0.4823 nats, with descriptive paired document SE 0.0143. Domains can correlate, so this SE is not an independent-domain uncertainty estimate.

Loss improved, but the separate-context AI reviewer found zero relevant completions for both checkpoints and more repetition after 1M targets. Ratings are subjective AI review, not ground truth; the randomized labels, rubric, raw outputs and unblinding receipt are preserved in `completion-review-001m/`. No conversational-quality improvement is claimed.

## Operation

- Run: `runs/own-base-foundation-01`; launched 2026-11-06 around 07:08 IST.
- Frozen ceiling: 99,999,744 attempted targets, 36 active hours, seven calendar days; approximately 24 active hours expected from launch.
- Next measurements: approximately 5M, every 10M, and the actual endpoint. Temporary resource stops and four-hour leases use the bounded supervisor.
- Live status: `runs/own-base-foundation-01/status.json`; full fixed evaluations: `validation.json`; supervision: `runs/own-base-foundation-01-supervisor.json`.
- LaunchAgent: `local.forge.own-base-foundation`. AC-only system-sleep prevention is bounded to the supervisor's lifetime. No display-sleep override.
- Explicit stop: create `runs/own-base-foundation-01/STOP`. The supervisor never removes or overrides it.
- Runtime/training code and budget remain frozen. CPU recovery, milestone interruption, corruption/identity and supervisor tests pass. Production step96 and protected step123 full optimizer checkpoints were published successfully.

`base_sample.py` provides explicit-checkpoint, CPU-only raw completion inspection. Its 18 small CPU tests passed, and an actual one-token smoke run against protected step123 completed. It does not provide an assistant or execute tools. See `README-base-sample.md` at repository root.

The existing chat preview remains the earlier experimental assistant. This foundation run does not silently replace it.
