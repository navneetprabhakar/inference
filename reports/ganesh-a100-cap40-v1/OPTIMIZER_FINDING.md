# Actual A100 optimizer finding

The first qualification failed exact restart. This is an execution reproducibility finding, not a demonstrated explanation for poor conversation.

- Independent first updates matched through recorded pre-optimizer boundaries. The first divergence was after `optimizer.step`: 16 MLP projection weights and one second-momentum buffer. Later input/gradient differences followed that divergence.
- Replaying the same captured production Muon inputs: eager execution repeated exactly within and across two fresh processes. Compiled execution repeated within each process but differed across fresh processes. Compiled replays did not exactly match the originally captured compiled output.
- Environment: A100 40GB, torch 2.9.1+cu129, CUDA 12.9, deterministic mode, CUBLAS workspace `:4096:8`, highest matmul precision, matmul TF32 disabled. This does not prove a hardware fault or establish which compiler transformation caused the difference.
- Correction: explicitly select the pinned underlying eager Muon function. Bind that mode to checkpoint identity. Preserve compiled behavior as the default for historical compatibility; never silently switch on failure or resume across modes. AdamW, data, objective, masks, learning rate and training bounds are unchanged.
- Validation: 209 local tests and all 52 frozen file hashes pass. Actual corrected CUDA restart and captured-input replay now pass exactly: 159 tensors / 1,409,489,630 elements, zero numerical or quality-loop mismatches. Real SIGTERM rollback also passes exactly. Signal resume, upload rejection and decode timing remain in progress; readiness is not yet complete.

Raw evidence: `trace-boundary-diagnosis.json`, `first-update-different-tensors.json`, `replay-comparison-diagnosis.json`; original captures in the qualification evidence archive. Supplemental replay payloads are retained in GCS with full readback proof in `diagnosis-backup.json`.

The learning question remains separate: can Ganesh-base fit the reviewed English examples and then improve full multi-turn development conversations without tool regressions? The bounded fit and conditional curriculum address that question. Neither a deterministic optimizer nor lower loss establishes conversational competence. The seed curriculum is short, small and exposed; it cannot by itself support a broad English release claim.
