# Ganesh-base Codemap (`ganesh-base-repair-v1`)

## 1. System Identity

* **Model Name:** `Ganesh-base`
* **Creator:** **Navneet Prabhakar**
* **Parameters:** `536,871,738` (`119` tensors; `n_layer = 16`, `n_embd = 1024`, `n_head = 8`, `n_kv_head = 8`, `vocab_size = 32768`)
* **Target Hardware:** Apple M4 Max `48 GB` unified memory (`mps`)

---

## 2. Directory and Module Map

| Path | Role |
|---|---|
| `configs/project.json` | Canonical project contract for `Ganesh-base` (`536,871,738` parameters, 12-tool registry, SFT repair parameters, and 9-category thresholds). |
| `configs/guardrails.json` | Hard engineering guardrails and milestone dependency graph (`G0 -> D0, M0 -> S0, E0 -> A0`). |
| `configs/execution.json` | Active milestone state, blockers, next action, and SHA-256 artifact bindings. |
| `configs/evaluation.json` | Frozen 9-category evaluation benchmark and tool replay specification. |
| `configs/MODEL_IDENTITY.json` | 4-layer immutable `Ganesh-base` / `Navneet Prabhakar` identity manifest. |
| `ganesh/__init__.py` | Package identity constants (`MODEL_NAME = "Ganesh-base"`, `CREATOR = "Navneet Prabhakar"`, `TOTAL_PARAMETERS_D16 = 536_871_738`, `verify_model_identity`). |
| `ganesh/model.py` | Self-contained PyTorch implementation of the `536,871,738`-parameter `GaneshGPT` architecture (`wte`, 8 alternating `value_embeds` + `ve_gate`, `smear_gate`, `resid_lambdas`, `x0_lambdas`, `backout_lambda`, `15 * tanh(z / 15)` softcap, and `set_full_causal_attention()`). |
| `ganesh/plan.py` | Contract, guardrail, and SHA-256 evidence validator (`python -m ganesh.plan validate` and `python -m ganesh.plan check`). |
| `ganesh/evaluation.py` | 9-category evaluation readiness and tool-replay verifier (`python -m ganesh.evaluation --require-ready`). |
| `scripts/build_ganesh_sft_v2.py` | Dataset builder that compiles the balanced `1,531`-train / `285`-validation `ganesh-sft-repair-v2` dataset. |
| `scripts/run_extensive_ganesh_test.py` | 9-category (`18/18`) closed-loop `mps` benchmark and `537M` hardware profiler. |
| `scripts/run_tough_tests.py` | 12-scenario (`12/12`) multi-turn, tool-chaining, and adversarial security suite. |
| `reports/ganesh_tool_crud_helper.py` | Execution-verified 10-tool CRUD lesson generator replayed through `MockTools`. |
| `reports/ganesh-sft-repair-v2/` | Compiled `train.jsonl` (`1,531` conversations), `validation.jsonl` (`285` conversations), and `summary.json`. |
| `cloud_training/ganesh_sft_repair.py` | Repaired SFT trainer (`calibrate_control_token_heads`, `action_weighted_sft_loss`, `build_fresh_sft_optimizer`, `encode_conversation_repaired`, `generate_action_repaired`, `run_repaired_sft`, `save_ganesh_checkpoint`, `load_ganesh_checkpoint`, `immutable_ganesh_identity_guard`). |
| `tests/verify_ganesh_sft_repair.py` | Automated 8-test verification suite covering all architectural, loss, dataset, decoding, and 4-layer identity repairs. |
