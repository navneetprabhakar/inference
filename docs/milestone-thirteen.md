# Gradient accumulation and portable update boundaries

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

The FP32 reference trainer now supports **supervised-token-weighted gradient accumulation** on MLX and PyTorch. Local tests match a native full-batch reference and preserve optimizer/data/scheduler state across resume. The full **80,765,440-parameter** model passes a bounded MLX own-trajectory resume probe with accumulation. This does not satisfy the still-failed full-size cross-backend trajectory gate, establish a language pilot or validate accumulation on NVIDIA hardware.

## Update contract

`Recipe.accumulation_steps` is a positive integer from 1 to 1,024, default **1**. It counts microbatches, not tokens. Current shard batches have one sequence, so fixed 1,024-position batches with 32 accumulation steps process 32,768 positions/update; short batches/tails and SFT masks change the actual processed/supervised counts.

For each update, all microbatches use the same pre-update parameters. If microbatch `i` has `n_i` supervised targets and mean-loss gradient `g_i`, the optimizer receives:

`g = sum(n_i * g_i) / sum(n_i)`

- Accumulate FP32 gradient sums on the selected backend. MLX evaluates each running sum to bound the retained graph. Only the current batch/gradient and running sum are needed; earlier activation graphs are not intentionally retained.
- Normalize by supervised targets, not sequence count or processed positions. Report the similarly weighted loss. A single-microbatch group preserves the previous arithmetic without multiply/divide rescaling.
- Apply global gradient clipping and bias-corrected AdamW **once**, after normalization. Epsilon placement, decay groups, optimizer equations, default loss and numerical bounds are unchanged.
- The token-based warmup uses **all processed positions after the group**, including masked context. Supervised positions are counted separately. A group may cross shard boundaries; no cursor is committed while accumulating.
- Consume a final partial group with its actual token denominator. Do not drop it, pad it with extra examples, wrap the dataset or silently repeat exposure.
- Commit weights/moments and update/cursor/token counters only after the group and functional optimizer succeed. Read errors, nonfinite loss/gradients, optimizer exceptions and interrupts leave the last completed state intact. Retrying starts from that group's original data cursor.

The reference path still exports gradients to the host for finite checks. This is deliberate diagnostic overhead, not an optimized training implementation. The trainer is synchronous; callers must serialize update/save operations rather than use it as a concurrent checkpoint service.

## Checkpoint compatibility

New checkpoints use training-state **version 2** with the same Safetensors file layout. State includes accumulation count, normalization/clipping/tail policies, zero pending microbatches and the trainer implementation hash. Saving during an update or reentrant updating is refused. No partially accumulated gradients are saved.

- `step` counts completed optimizer updates; `cursor` counts consumed microbatches. They no longer have to be equal.
- Nonterminal cursors must align to complete groups. A dataset-ending short group is allowed. Resume verifies step/cursor relationships, prefix token totals, tokenizer/data hashes, recipe/policy agreement and all existing optimizer integrity checks.
- Version-1 checkpoints load with accumulation **1**; a v1 state cannot claim multi-microbatch accumulation. Subsequent saves upgrade to version 2. Older project code that only understands v1 cannot read new v2 states; deploy the current reader on both hosts.
- Changing accumulation or replacing the dataset/curriculum on resume is not an implemented operation. Such a transition needs an explicit future contract.

The overfit, portability and timing utilities now distinguish optimizer updates from microbatches. Repeated synthetic exposure and timed positions include accumulation; portable fixture probe steps remain optimizer steps.

## Validation

Full suite: **221 passed, 7 CUDA skips**. The new accumulation module contributes **34 passing cases and one CUDA skip**. Existing tests remain green.

| Check | Evidence |
| --- | --- |
| Native numerical reference | MLX and PyTorch CPU each match native PyTorch full-batch cross-entropy, gradients, global clipping, AdamW weights and moments over unequal supervised counts, multiple updates and a short tail. Original bounds: weights/loss 1e-5 absolute, gradients/moments 1e-6 absolute, relative 1e-4. |
| Same-backend resume | Exact tested own-trajectory weights/moments and metrics on MLX/CPU, including initial/end checkpoints, variable lengths and a partial final group. |
| Failure recovery | Both local backends retain the prior weights/moments/counters after microbatch I/O, nonfinite loss/gradients, optimizer failure and keyboard interruption. |
| Disk-backed batches | Accumulated groups cross numeric shards; a fresh reader resumes from the exact microbatch cursor, without rereading prior batches for counting. Synthetic reviewed fixture only. |
| Tiny backend migration | MLX → CPU → MLX accumulation continuation and a portable fixture round trip pass the original tiny numerical bounds. CUDA-specific accumulation is skipped locally. |
| Semantic corruption | Rehashed wrong policies, pending gradients, step/cursor/token inconsistencies, invalid accumulation settings and falsely labeled legacy states are refused. |
| Real historical artifact | Existing v1 tiny bundle `c546f1277b2b2b0ed171a4e427e0ca8ff1a0f1fe9f93f543bcb4151afe4abced` resumes on current CPU code from step 2 to 4 under original probe bounds and writes v2 with accumulation 1. |

An independent negative control shows that averaging unequal microbatch means changes the gradient materially. The positive native comparison captures the gradient **before clipping**, preventing a correct-looking AdamW endpoint from concealing the wrong aggregation.

## Full-model mechanics probe

The documented target architecture, random initialization seed 317 and five opaque synthetic microbatches were tested on the laptop's MLX GPU. Lengths: **16, 32, 24, 8, 12**; supervised counts: **10, 21, 16, 5, 8**. Accumulation is 2; recipe retains default epsilon 1e-8 and default legacy loss.

- Reference path: **3 logical optimizer updates**, 5 microbatches, **92 processed / 60 supervised positions**. Save after update 1, then load a second trainer and compare its own continuation at updates 2 and 3.
- Actual neural work, counting both continuations: **5 executed updates / 136 processed positions**. This is not a 1M-token language run, an overfit check or a statistically useful learning experiment.
- At each comparison, all **242,296,320 values** across weights and both moments match exactly. This is own-trajectory identity, not independent-run or cross-backend agreement.
- Process peak RSS: **4,985,421,824 bytes**; MLX allocator peak: **3,759,260,724 bytes**. These reflect a process holding **two trainer states** plus diagnostics/checkpoint work. Unified-memory figures overlap and must not be added; this is not a production single-trainer memory estimate.
- The temporary checkpoint was removed. Its size/hash, state hashes, timings, counters and hardware are in `reports/milestone-thirteen-81m-accumulation.json`. Short-context timings are not sustained throughput or cloud-cost estimates.

Other evidence: `reports/milestone-thirteen-tests.xml` and `reports/milestone-thirteen-legacy-resume.json`.

## Reproduction and remaining gates

```sh
.venv/bin/python -m pytest -q tests/test_accumulation.py
.venv/bin/python -m slm.eval.accumulation --config configs/target-81m.json --backend mlx --output data/probes/new-81m-accumulation.json
```

For an accumulated timing probe, use `python -m slm.eval.benchmark ... --accumulation-steps 2`; keep its context, warmup and measured-update scope with the result. The default remains 1.

No new cloud job, API request, CLI teacher generation or public/teacher-data training occurred. Public review and production-tokenizer selection remain required before the actual language pilot. Next: deterministic mixture/exposure accounting and curriculum transitions, plus an actual NVIDIA check of accumulated checkpoint continuation within the existing validation budget. Full-size cross-backend acceptance, sustained training, reviewed teacher release, MCP and ESCI remain open.
