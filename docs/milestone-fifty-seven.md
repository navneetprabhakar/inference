# Actual MLX SFT context sizing

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

Keep **2,048 positions as the candidate maximum** for the next whole-dialogue SFT design. The actual 81M MLX forward/backward probe completes at both 1K and 2K, including resident optimizer-shaped buffers, with source parameters unchanged. This supports further testing of 2K; it does **not** establish complete optimizer-step memory, sustained training throughput or conversation quality.

The preceding pinned 200-row short-conversation prefix has 113 whole dialogues fitting 1K versus 198 fitting 2K. That prefix is not a population-quality sample. Before training, complete source/content admission and a finite full-step preflight. Existing SFT batches retain their actual dialogue lengths without padding every short row to the maximum, so allowing 2K need not make every batch a 2K workload.

## Predeclared actual workload

- Actual completed foundation checkpoint, 80,765,440 FP32 parameters / 24 layers, unchanged architecture and tokenizer vocabulary; model manifest bound to the previous exact-import receipt.
- Actual hardware: **Apple M4 / 24 GiB**. Device must be the MLX GPU; no CPU fallback. Hardware and NumPy 2.5.4 metadata were observed after the probes, not used as thermal/background-load controls.
- Unchanged dense-onehot embedding and legacy loss implementations from the reference recipe. Batch size one; no precision/fused-kernel change.
- Fixed seeded synthetic content-token stream; 1K is exactly a prefix of 2K. Shifted targets and a last-half binary loss mask. These are not real assistant messages or a language evaluation.
- **Four fresh subprocesses in 1K → 2K → 2K → 1K order**, frozen before execution. Each has one warmup and three timed forward/backward calls. Six timed calls / two independent process initializations per length.
- Two materialized, distinct FP32 parameter-shaped buffers reserve **646,123,520 bytes**. Their contents are synthetic and they are not used by an optimizer; they do not import or update the source optimizer.
- No clipping, AdamW, data/checkpoint pipeline or gradient export in the measured interval. Finite loss/gradient checks and parameter-bit checks run outside timing. Peak allocator scope is reset after warmup and includes subsequent finite checks with the buffers resident.

## Results

| Fixed context | Median forward/backward | Observed timed range | F/B positions per second | Peak Metal allocation |
| --- | ---: | ---: | ---: | ---: |
| 1,024 | 0.557714 s | 0.549266–0.561736 s | 1,840.17 | 4,027,980,944 bytes / 3.75 GiB |
| 2,048 | 1.560362 s | 1.552682–1.568420 s | 1,312.80 | 7,974,681,744 bytes / 7.43 GiB |

All four probes have finite gradients/losses, zero optimizer updates and bitwise-unchanged parameters. Total synthetic work including warmups: **24,576 gradient positions / 12,288 masked targets**. These are additional diagnostic computations, not logical training progress, new unique text, extra scheduled foundation exposure or new learned skill.

The 2K fixed-length forward/backward call takes about 2.80 times the 1K median and delivers fewer positions per second. These measurements omit major full-training costs and cannot be substituted for end-to-end throughput or cloud-cost estimates. ABBA ordering and warmup reduce obvious order/cold-start effects; they do not establish thermal causality, long-run stability or a confidence interval.

Metal allocator peaks and process RSS have different accounting/scope on this unified-memory host. Raw receipts retain process-lifetime RSS (about 1.25 GiB here), but it is not complete GPU working-set memory. Do not sum allocator and RSS or infer total free system memory. Dummy moment-shaped buffers are not complete AdamW scratch/output residency, so 7.43 GiB is **not an upper bound on actual training memory**.

Evidence: [actual four-trial protocol, raw results, aggregation and controls](../reports/milestone-fifty-seven-context-sizing.json). Private artifacts: `data/sft-context-sizing-v1/{protocol.json,trial-*.json,trial-*.log,summary.json}`.

## Verification and reproduction

**Six focused checks pass / zero skips**, covering deterministic nested shifted workloads, content-only IDs, mask counts, invalid workload bounds and pre-allocation output/workload refusal. Actual four-process GPU execution is separate from those pure workload checks.

The independent receipt checker reaggregates all saved per-trial timings, counts, peaks and identities; reopens the source model transitively; verifies the declared reserved buffer size; and confirms all 26 original training source hashes remain unchanged. No model, optimizer or main training checkpoint is modified.

```sh
.venv/bin/python -m pytest -q tests/test_sft_context_probe.py
.venv/bin/python scripts/measure-sft-context.py
.venv/bin/python scripts/check-sft-context-sizing.py
```

The measurement attempt already exists and refuses replacement/replay. The checker reopens those retained results; source/implementation/protocol changes require a separately declared fresh attempt. The process workload is finite; there is no hard thermal or wall-time guarantee.

## Next work

Prioritize content and constituent-specific admission for a sufficiently large short-conversation SFT slice. Then freeze the candidate 2K maximum, actual exposure/replay caps, optimizer recipe and new-stage terminal conversation/diagnostic contract; measure a complete finite training step before launch. If resource evidence requires another context or batching choice, declare that change rather than truncate away dialogue history.

The existing 12-row approved SFT control and 174-row unadmitted extraction slice remain insufficient substitutes for broad training. The next meaningful completed training iteration must still receive an actual raw conversation and direct score before further iteration. Current foundation baseline remains 5/100 / 0-of-8. Broader styles/content, required reviewed teacher, learned tools/MCP, actual MLX/CUDA resumed-training quality, deployment optimization and later ESCI remain open. No new teacher/model API call, cloud job or paid activity; full project goal active/incomplete.
