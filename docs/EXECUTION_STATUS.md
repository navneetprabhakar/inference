# Ganesh-base Execution Status

## 1. Milestone Status Summary

| Milestone | Status | Observed Verification Result |
|---|---|---|
| **`G0` (Contract & Guardrails)** | `completed` | `python -m ganesh.plan validate` passed (`536,871,738` parameters, `119` tensors). |
| **`D0` (Balanced SFT v2 Dataset)** | `completed` | `1,531` train conversations (`5,744` assistant text turns, `732` execution-verified tool calls; `disabled_no_call = 480`, `enabled_no_call = 510`, `enabled_call = 541`) and `285` validation conversations built in `reports/ganesh-sft-repair-v2/`. |
| **`M0` (Self-Contained `537M` `GaneshGPT`)** | `completed` | `GaneshGPT` matches all `119` tensors and `536,871,738` parameters of `Base10B` without requiring `runs/nanochat-source` or CUDA FlashAttention-3. |
| **`S0` (Repaired SFT Trainer & Decoder)** | `completed` | `8/8` unit and convergence tests in `tests/verify_ganesh_sft_repair.py` passed on `mps`. |
| **`E0` (9-Category Evaluation Gate)** | `completed` | `python -m ganesh.evaluation --require-ready` verified all 9 capability categories and replayed all reference tool calls. |
| **`A0` Ganesh-base v0.1 English pilot** | Pending | The pilot uses the verified v0.1 parent, native chat baseline, and best/last checks. The model training run remains pending. |
