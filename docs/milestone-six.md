# Full-size local bring-up and trajectory diagnostics

Creator: Navneet Prabhakar

Date: 18 October 2026

## Outcome

The **80,765,440-parameter** candidate now runs on the laptop. Fixed-checkpoint inference, 2,048-token context checks, exact training-state import/export and fixed-batch learning checks pass locally. **Matching an uninterrupted training trajectory across backends does not pass the declared numerical gates. Full-size training portability is not accepted.**

The model uses the documented 24-layer, width-512, FFN-1536, 8-query/2-KV-head architecture. `configs/target-81m.json` allocates a provisional 16,384-token vocabulary; tokenizer selection remains open. FP32 weights occupy 323,061,760 bytes; weights plus two FP32 Adam moments occupy about 969 MB before metadata/temporary buffers.

## Verified results

| Check | Evidence and scope |
| --- | --- |
| Actual full-size instantiation | 218 canonical parameter tensors, exactly 80,765,440 values; no pretrained student weights |
| Exact state import/export | 654 tensors / 242,296,320 values checked by content hashes; weights and both moments preserved exactly, together with counters/recipe; tested at updates 4 and 100 |
| Direction of state checks | PyTorch CPU → MLX GPU and MLX GPU → PyTorch CPU at update 100; import/export performs zero updates and does not prove trajectory equality |
| Full-context finite check | Every full-sequence logit and every layer state checked for finiteness at 2,048 positions |
| Full-context cross-backend comparison | Logits/all layer states compared at positions 0, 127, 1,023, 1,024 and 2,047, with the same checkpoint; original pointwise bounds retained |
| Cache and causal-prefix checks | Full-sequence versus 2,047-token prefix plus cached final token; independent-seed cache max error 2.15e-6 on MLX and 1.79e-6 on CPU |
| Synthetic learning | Each backend ran 100 updates on the same repeated opaque-token batch: masked loss 9.668 → 0.000203 MLX / 0.000211 CPU; 100% on 18 supervised positions |
| Exposure accounting | 24 input positions repeated 100 times: 2,400 processed / 1,800 supervised positions per run; no English or broad knowledge claim |
| Tests | **74 passed, 2 CUDA checks skipped locally**; these green unit tests do not override failed full-size integration results |

Observed process RSS peaks include approximately 3.46 GB for the MLX 100-update check and 2.74 GB for CPU, with roughly 5.17 GB seen in all-tensor trajectory diagnostics. MLX allocator peaks are reported separately and overlap process/system memory on unified-memory hardware; do not add the numbers. The 100-update reference loops took 23.81 seconds MLX and 26.38 seconds CPU with four requested CPU threads. These are short synthetic validation workloads with host gradient checks, not production throughput estimates or a basis for cloud token-cost extrapolation.

## Failures retained

1. With the original epsilon 1e-8 and prototype bounds, fixed-checkpoint probes at update 2 passed. After CPU continuation to update 4, logit and gradient comparisons failed. The complete diagnostic scan found maximum logit difference 1.824e-5 and embedding-gradient difference 4.888e-6.
2. A controlled epsilon-1e-6 ablation kept seeds/data/initialization fixed. It reduced disagreement but still failed the prototype gradient pointwise check. The variant is a diagnostic fixture recipe, **not a selected production optimizer**.
3. An explicit research policy added depth/width-scaled relative-L2 and maximum-error bounds for logits/gradients while retaining original state/layer checks. It was fixed before fresh-seed validation. That fresh-seed epsilon-1e-8 run failed the maximum-logit bound; two epsilon-1e-6 fresh-seed outbound CPU phases passed, but their return phases failed per-layer bounds.
4. The failed research policy remains unchanged and is rejected for acceptance. It is documented in [numerical policy](full-depth-numerical-policy.md). No failed full-size gate has been reclassified as passing.
5. A diagnostic continuation collected all tensors through return updates 4 → 6 despite comparison failures, without approving the result. Values stayed finite; at update 6, layers 10, 22 and 23 failed the declared pointwise criterion.
6. After 100 independent same-seed fixed-batch updates, endpoint parameters differ substantially despite both runs memorizing the fixture: maximum per-tensor weight relative L2 difference **29.94%**, maximum absolute weight difference **0.02042**. This is not evidence of trajectory reproducibility.

An independent CPU FP64 diagnostic uses complex-valued RoPE, native cross entropy and native AdamW, with FP32 projection at update boundaries. Its rotary gradient has a finite-difference test. At a shared starting checkpoint, maximum MLX gradient error against this reference was 3.05e-7. After two updates, maximum gradient relative-L2 errors against the reference were 8.71e-6 MLX and 1.17e-5 CPU. These findings are consistent with sensitivity to small gradient/optimizer differences; they do not resolve or certify long-run equivalence. Exact state-import hashes rule out a tensor/value change during the tested import operations.

## Reproduce in fresh directories

Basic full-size prototype-bound diagnostic (currently fails continuation checks):

```sh
OMP_NUM_THREADS=4 .venv/bin/python -m slm.eval.portability create --config configs/target-81m.json --output checkpoints/new-fullsize-origin --backend mlx
OMP_NUM_THREADS=4 .venv/bin/python -m slm.eval.portability verify --bundle checkpoints/new-fullsize-origin --output checkpoints/new-fullsize-cpu --backend torch
```

The CLI accepts explicit optimizer recipe and initialization/batch seeds. `configs/fullsize-diagnostic-recipe-eps1e-6.json` is the epsilon ablation. `--comparison-policy full_depth_fp32_v1` selects the **rejected research policy** for diagnostics; default tiny bounds remain unchanged. Policy selection is stored in the fixture before verification and there is no numeric tolerance override.

Full-context probe, using a model-only directory inside a training checkpoint:

```sh
OMP_NUM_THREADS=4 .venv/bin/python -m slm.eval.context --model checkpoints/new-fullsize-origin/initial/model --output checkpoints/new-context-mlx --backend mlx
OMP_NUM_THREADS=4 .venv/bin/python -m slm.eval.context --model checkpoints/new-fullsize-origin/initial/model --output checkpoints/new-context-cpu --backend torch --reference checkpoints/new-context-mlx
```

Learning smoke checks and exact state audits:

```sh
OMP_NUM_THREADS=4 .venv/bin/python -m slm.eval.overfit --config configs/target-81m.json --output checkpoints/new-overfit-mlx --backend mlx --updates 100
OMP_NUM_THREADS=4 .venv/bin/python -m slm.eval.state_transfer --checkpoint checkpoints/new-overfit-mlx/checkpoint --fixture checkpoints/new-overfit-mlx --output checkpoints/new-import-cpu.json --backend torch
```

`slm.eval.drift` collects all comparison failures while continuing a diagnostic run; its report explicitly denies acceptance and emits no approved checkpoint. `slm.eval.precision` supplies the FP64 investigation when provided a fixture and a corresponding CPU probe tensor file. These are reusable diagnostic tools, not alternate paths around failed release gates.

## Produce the FP64 diagnostic input

The precision command expects a CPU probe captured after the two resumed updates. For a fresh complete fixture:

```python
from pathlib import Path
from safetensors.numpy import save_file
from slm.common.training import Trainer
from slm.eval.portability import get_batches, capture
bundle = Path('checkpoints/new-fullsize-origin')
probe = Path('checkpoints/new-cpu-probe-4.safetensors')
assert not probe.exists()
trainer = Trainer.resume(bundle/'initial', get_batches(bundle), 'torch', 'cpu')
trainer.update()
trainer.update()
save_file(capture(trainer), str(probe))
```

```sh
OMP_NUM_THREADS=4 .venv/bin/python -m slm.eval.precision --bundle checkpoints/new-fullsize-origin --cpu-probe checkpoints/new-cpu-probe-4.safetensors --output checkpoints/new-fp64-diagnostic.json
```

These full-tensor probe files are approximately 1.3 GB each. Use a complete freshly generated fixture; retired diagnostic bundles are deliberately incomplete.

## Evidence, storage and next gates

- Compact evidence: `reports/milestone-six-fullsize.json`, `reports/milestone-six-tests.xml` and `reports/milestone-six-artifact-retirement.json`.
- Duplicated, recomputable multi-GB probe tensors were retired after collecting evidence and verifying their hashes. Original bundle manifests, source configurations, seeds, training checkpoints and compact reports remain. Retired fixtures intentionally cannot validate as complete portability bundles; regenerate into fresh directories for reproduction. No accepted/public-data model checkpoint was deleted.
- Full-size NVIDIA state import/inference remains untested. The previous tiny T4 result must not be generalized. No new cloud resources or paid calls were used in this milestone.
- Resolve full-size numerical/optimization drift and define a defensible accepted training criterion before claiming seamless full-size training or launching a substantial training run. The current failed policy cannot serve as that criterion.
- Full-size 100-update learning and endpoint diagnostics are not all-tensor equality checks at every intermediate update. Longer trajectories, resume stability, reduced precision and optimized kernels remain separate work.
- Public data remains sample-only, with zero human approvals. Source review, calibrated language/privacy/quality gates, production tokenizer, teacher workflow and language learning remain open.
