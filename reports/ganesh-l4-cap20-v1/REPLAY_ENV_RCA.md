# L4 qualification: replay launcher defect

18 November 2026 IST. English pilot remains blocked. No thresholds or optimizer settings were relaxed.

## Observed evidence

One L4 allocated in us-west1-a after capacity failures in us-central1-a/b/c and us-east1-b/c/d. Uninterrupted two updates and separate one-update + GCS restore + one-update branches completed under the same reviewed diagnostic settings.

The selected actual Muon group capture is identical across branches: inputs, output values/layouts and context; both capture manifests SHA256 98249361f5ff823a416a7a94ee598fc30e4bc2160329bdd47a5a789489a0647f. A supplemental CPU-only comparison of the completed checkpoint bundles passed bitwise: 159 tensors, 1,409,489,630 tensor elements, zero tensor/metadata mismatches, zero nonfinite elements and equal quality-loop state. This comparison ran after the replay launcher failed; it is evidence, not a synthesized overall qualification pass.

The original worker stopped progression at its first fresh eager replay: `ValueError: Replay environment/source mismatch`. SFT sets CUBLAS_WORKSPACE_CONFIG=:4096:8 inside its child process. That setting is captured, but was not restored by the replay CLI, and cannot propagate back into the parent worker. The CLI restored Torch numerical flags and dtype but omitted this process environment variable. The replay correctly rejected the mismatch before running the kernel.

## Local correction and guard

The CLI now restores the captured CUBLAS workspace environment before CUDA runtime use, including removing an inherited setting when the capture records absence. A real subprocess regression test covers both directions with a conflicting or missing parent environment, verifies recorded environment identity and exact eager replay output on the small CPU fixture. All 203 targeted tests pass locally. This does not qualify the correction on CUDA.

The deployed runtime and captured files remain immutable. The updated source hash intentionally differs; do not edit capture manifests or weaken environment comparison to replay old evidence. Old GPU captures require their retained original runtime plus an explicit launch environment matching the recorded capture. A newly built runtime must be separately bound and qualified before training.

## Unresolved gates

Fresh eager/compiled GPU replay did not complete. Signal rollback/resume, rejected-upload and provider-STOP drills did not run because the worker halted at the replay error. Decode throughput was not qualified. No English fit, curriculum pilot, independent release or MPS promotion occurred. Matching L4 checkpoint states do not resolve the historical A100 mismatch universally, nor explain or repair English conversation quality.

Required backups and final compute closeout are tracked separately in the active attempt directory and spend ledger. No automatic optimizer retry, learning-rate/epoch increase, runtime replacement on the VM, or fit dispatch is permitted from this partial result.

## Local package after the fix

The new runtime is `runs/ganesh-l4-cap20-v1/runtime-replay-env-fix.tar.gz`; its independent extraction/source verification is recorded in fixed-runtime-readback.json. It has not been uploaded, deployed or GPU-qualified. The original deployed runtime remains necessary for replaying the immutable old captures without changing their source identity. All 52 existing/new frozen data files remain hash-identical.
