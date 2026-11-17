# Optimizer isolation — local result, 17 November 2026

**The small local test does not reproduce the CUDA restart failure. No fix or readiness pass is claimed.**

## Completed

`probe.py` imports the pinned upstream MuonAdamW implementation without editing it. It runs eager and compiled modes in separate subprocesses. Each uninterrupted process saves after update1 and completes update2; another fresh process restores that saved state and executes update2 with the same deterministic synthetic gradient. Each compiled branch has its own compiler-cache directory. Three16x64FP32 parameter matrices exercise the wide-matrix Muon path with BF16 internal compute, five polar iterations and one CPU thread.

Both modes match exactly on every recorded fused-kernel input, output and final serialized parameter/optimizer state. The comparator rejects an intentional one-element perturbation. Full input/output hashes include dtype, shape, stride and storage offset. CPU-only execution does not touch Own weights, datasets, serving defaults or GCP.

Run from repository root:

```
.venv/bin/python reports/optimizer-isolation-v1/probe.py
```

## What this narrows—and does not

The minimal serialization/restore wiring works on these synthetic CPU tensors. This does not reproduce real parameter shapes, preserved training moments, exact accumulated gradients, CUDA BF16 matmuls, GPU compilation or the production model graph. It therefore does not rule out a shape/device/compiler-dependent failure or establish the cause of the real failure. Eager versus compiled absolute results are not compared as an acceptance criterion; each mode is compared against its own restored continuation.

Static inspection of the pinned single-rank optimizer shows:

- Gradients and parameters are stacked in parameter-group order. Single-rank execution bypasses distributed padding/all-gather scratch paths.
- Group scalar tensors are filled immediately before the fused call. Their absence from optimizer.state_dict alone is not evidence of lost state.
- Muon mutates stacked gradients and both moment buffers. Existing production traces observe state before/after optimizer.step, but do not capture raw fused-call arguments or private compiler state.
- Thus there is no supported reason to reset moments, change data, waive the exact gate or label compilation as the root cause.

## Next bounded diagnostic specification

Prepare an opt-in capture/replay wrapper for the actual failing Muon group. Capture actual incoming gradients, stacked parameters, both moment buffers, all scalar values and their tensor properties immediately before the fused call; preserve group ordering, compute dtype, numerical flags, software/source identity and alias relationships. Take independent clones before in-place mutation. Capture output as well. The existing hashes cannot reconstruct raw gradients.

A future explicitly approved device run would capture once, then replay the **same captured inputs** in fresh processes using eager and compiled kernels, with cold and warm compiled paths recorded separately. Keep model compilation, input data and optimizer policy fixed. Compare eager repeatability and compiled repeatability separately; a systematic eager-versus-compiled rounding difference is not itself a restart defect. If fused inputs differ, investigate input assembly before blaming the kernel. If inputs match and only compiled repeated outputs differ, the compiler/kernel path becomes supported; if both modes differ, inspect shared numerical/device behavior. If all repeated outputs match, inspect production invocation context and alias/cache state rather than declaring resolution.

No GPU allocation is authorized by this document. Exact production restart, signal/upload/provider-stop qualification and English fit remain blocked. The downstream target stays the unchanged24-session English fit diagnostic, followed by generated transfer assessment if fit passes. More corpus volume is not the next remedy.
