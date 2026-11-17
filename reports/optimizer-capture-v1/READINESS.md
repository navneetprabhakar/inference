# Actual Muon input capture/replay — local readiness

17 November 2026 (IST). **Local implementation and checks complete. CUDA/root-cause/English-learning gates remain blocked. No new cloud cap has been approved.**

## Delivered

`cloud_training/nano_optimizer_capture.py` wraps the actual pinned upstream `muon_step_fused` call. `nano_sft` exposes it only with explicit `--capture-muon-step 0|1`, isolated `--fit-diagnostic`, and matching boundary tracing. The default is off. Capture settings and module hash are included in the checkpoint identity; older checkpoints are not silently reinterpreted under the new identity.

The default parameter selector is `transformer.h.0.mlp.c_proj.weight`. It selects the entire containing Muon group, not just layer0. The failing production group contains16wide projection matrices. Exactly one group and one absolute update are captured per process/run. Single-rank execution is required; missing groups, changed call schedules, nested capture and unsupported tensor layouts fail closed.

Captured before and after the real call:

- Stacked gradients and parameters, momentum and factored second-moment buffers, four scalar tensors, iteration count and reduction dimension.
- Values, dtype, device, shape, stride, storage offset, allocation size and shared-storage relationships. Unreferenced padding is zeroed, never copied from uninitialized memory. Mixed-dtype storage aliases and ambiguous/internal-overlap layouts are rejected.
- Parameter order, group hyperparameters, absolute step, training identity, upstream and harness source hashes, Torch/CUDA versions, compute dtype, numerical flags, CPU thread counts and available GPU name/capability.

The wrapper does not replace the optimizer algorithm. It clones evidence before in-place mutations and restores the original function on exit/error. Evidence is immutable, size-bounded, hash-verified and committed only after the complete expected optimizer call schedule. Incomplete captures and corrupted files cannot be replayed. `weights_only=True` is used for loading our trusted local artifacts; hashes detect corruption, not a malicious replacement of the entire receipt chain.

The2GiB cap covers before/after payloads with serialization margin. The full16x1024x4096group is approximately1.5GiB before+after, excluding small scalars/context. Two branch captures therefore add approximately3GiB, plus replay outputs and transient host copies; future lease/storage/transfer planning must include this. No upload, launch or retry automation was added.

## Local checks and their limits

- 120 regression tests passed covering SFT/objective/masking, checkpoint/restart, tracing, packaging, quality/fit gates, retention and serving.
- 23 focused/integration tests passed, including13capture tests, real-loop dispatch, overwrite/corruption/incomplete-evidence rejection, size bounds, alias/stride/offset reconstruction, exception cleanup and package closure. Some existing trace tests appear in both suites; these are not143unique tests.
- The fresh-process CPU harness uses actual upstream optimizer calls with two parameter groups and preserved first-update moments. Selected-group capture inputs and outputs match exactly between uninterrupted and restored branches.
- An uncaptured compiled control produces exactly the same final model/optimizer state as the captured branch on this fixture.
- Two fresh eager replay processes and two fresh compiled replay processes each execute three calls with fresh reconstructed inputs. Each mode is internally exact across first invocation, warm repeats and fresh processes. Compiled replay matches the captured compiled output on every call.
- Eager replay does **not** match compiled output. On this synthetic BF16-compute CPU fixture, the maximum parameter difference is0.00020518899; this is a repeatable cross-mode difference, not a restart failure or a tolerance proposal. `cross-mode-differences.json` retains per-argument measurements.
- All41frozen files are unchanged. Real tokenizer/data/contract validation passes with capture enabled and a two-update limit. The printed96planned updates describe the full64epoch schedule; the explicit two-update diagnostic bound is smaller and no training was executed.
- A new local runtime archive was built and independently extracted/hash-checked:149members,26adapter modules, complete import closure. Archive hash is in `package-readback.json`. The previous runtime was not overwritten; the new runtime is not GPU-qualified or uploaded.
- HTTP8765remains off. Own model files, serving defaults, acceptance thresholds and release sets were not changed.

These tests use reduced synthetic CPU tensors, not the missing raw gradients from the failed A100 run. Existing production traces contain hashes and cannot reconstruct those tensors. No actual failing GPU input capture has yet been produced. Storage pointer addresses, GPU allocator/cache state, compiler internals and scheduling are not reconstructed. Fresh replay processes use separate Inductor-cache directories; this is not a claim that hardware/driver caches have been flushed.

## Predeclared next experiment — not authorization

Only after a new finite cap and fresh authenticated inventory/lease are approved:

1. Start from the retained immutable base and unchanged reviewed English inputs. Use one writer and the existing exact restart schedule. Enable `--trace-updates 2 --capture-muon-step 1 --capture-muon-param transformer.h.0.mlp.c_proj.weight` on both branches. Keep numerical settings, optimizer moments, learning rate, model compilation and data order fixed. Require a committed capture from both branches; an early stop or absent capture is not a pass.
2. Compare the actual fused inputs and group/environment identity first. Different input values/layouts/group order direct diagnosis to assembly/restoration; do not blame the kernel.
3. Replay identical captured inputs in separate eager and compiled processes; record first-call and warm-repeat results separately. Compare each mode against itself across processes. Cross-mode equality is not required and cannot be used to choose a retrospective tolerance.
4. If identical inputs vary only in compiled repeats, investigate the compiled path. If both modes vary, inspect shared numerical/device behavior. If replay is exact but live calls diverge, inspect invocation/private state and capture perturbation. Do not label any branch as a resolved root cause without the distinguishing evidence.
5. A result does not waive the production exact-restart gate or signal/upload/provider-stop checks. Preserve/read back required evidence before normal shutdown; retain the finite STOP fallback. No automatic budget extension, GPU upgrade, retries, optimizer reset or fit pilot on qualification failure.
6. After the required gates pass, complete the unchanged bounded24-session/72-turn English fit diagnostic. Generated fit and transfer behavior—not optimizer loss or infrastructure completion—determines the next curriculum action. No source expansion, maths or CBSE work before the English gate.

Replay CLI (run in a new process, with a new output directory, on a matching environment):

```
python -m cloud_training.nano_optimizer_capture \
  --capture <committed-capture-directory> --repo <pinned-nanochat-source> \
  --mode compiled --output <new-output-directory>
```

Repeat separately with `--mode eager`. CPU captures cannot authorize CUDA results. The harness restores recorded numerical flags and rejects mismatched recorded software/source/device properties; inspect the recorded environment rather than assuming every external driver/compiler property is covered.

## Remaining blockers

- New explicit finite GPU cap and lease; no compute is authorized by this report.
- GCP auth refresh: the read-only inventory attempt failed reauthentication. Last successful inventory at cleanup confirmed zero VMs/disks. This task started or modified no cloud resources.
- Actual production-shape CUDA capture/replay and root-cause resolution remain outstanding.
- New capture overhead and GCS upload/readback timings are not measured. Existing fault qualification remains incomplete.
- No completed English fit pilot and no accepted conversational model yet.

To rerun the local subprocess fixture, set `OWN_CAPTURE_CHECK_DIR` to a new absolute directory and run `.venv/bin/python reports/optimizer-capture-v1/run_checks.py`; existing evidence is never overwritten. Compiler caches and superseded synthetic first-pass artifacts were removed after verification.

Local evidence: `local-checks/results.json`, `integration-tests.log`, `regression-tests.log`, `frozen-inputs.json`, `preflight-command.json`, `package-readback.json`, `vm-inventory.json`. No GCS upload, commit or push was performed.
