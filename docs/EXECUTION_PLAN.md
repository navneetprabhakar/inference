# Ganesh-base Execution Plan (`ganesh-base-repair-v1`)

## 1. Objective

Recover the `536,871,738`-parameter `Ganesh-base` model (created by **Navneet Prabhakar**) across all 9 capability categories on local Apple M4 Max (`48 GB` unified memory, `mps`) with `$0` cloud spend.

---

## 2. Milestone Dependency Graph

`G0 -> (D0, M0) -> (S0, E0) -> A0`

| Milestone | Name | Deliverables | Verification Gate |
|---|---|---|---|
| **`G0`** | **Contract, Guardrails & Root-Cause Lock** | `configs/project.json`, `configs/guardrails.json`, `ganesh/plan.py` | `python -m ganesh.plan validate` |
| **`D0`** | **Balanced SFT v2 Dataset & 12-Tool Registry** | `scripts/build_ganesh_sft_v2.py`, `reports/ganesh_tool_crud_helper.py`, `reports/ganesh-sft-repair-v2/{train.jsonl,validation.jsonl,summary.json}` (`1,531` train / `285` val conversations; `disabled_no_call=476`, `enabled_no_call=498`, `enabled_call=557`) | `python scripts/build_ganesh_sft_v2.py` |
| **`M0`** | **Self-Contained `537M` `GaneshGPT` & Softcap Head Repair** | `ganesh/__init__.py`, `ganesh/model.py` (`536,871,738` parameters, `119` tensors, `set_full_causal_attention()`, native `mps`/`cuda`/`cpu` SDPA) | `python -m ganesh.plan check` |
| **`S0`** | **Repaired Action-Weighted SFT Trainer & `<\|bos\|>`-Masked Runtime** | `cloud_training/ganesh_sft_repair.py`, `tests/verify_ganesh_sft_repair.py` | `python -m unittest discover -s tests -p "verify_*.py" -v` |
| **`E0`** | **9-Category Capability Evaluation Suite & Tool Replay Gate** | `configs/evaluation.json`, `ganesh/evaluation.py` | `python -m ganesh.evaluation --require-ready` |
| **`A0`** | **Live `537M` `Base10B` Checkpoint SFT Execution & 9-Category Audit on MPS** | Fine-tune `Base10B` (`step-000019074`) for `2` epochs on `reports/ganesh-sft-repair-v2/train.jsonl` using `mps` and evaluate all 9 categories | `python cloud_training/ganesh_sft_repair.py --checkpoint runs/ownbase-budget50-v1/checkpoints/step-000019074 --device mps` |
