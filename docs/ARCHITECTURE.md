# Ganesh-base Architecture and SFT Repair Specification

## 1. Exact `536,871,738`-Parameter `GaneshGPT` Architecture

`GaneshGPT` (`ganesh/model.py`) implements the exact `119`-tensor decoder-only Transformer trained in `Base10B`:

| Component | Tensor Count | Shape | Parameter Count |
|---|---|---|---|
| **Token Embedding (`transformer.wte.weight`)** | `1` | `(32768, 1024)` | `33,554,432` |
| **Odd-Layer Value Embeddings (`value_embeds.{1,3,5,7,9,11,13,15}.weight`)** | `8` | `8 x (32768, 1024)` | `268,435,456` |
| **Untied Output Head (`lm_head.weight`)** | `1` | `(32768, 1024)` | `33,554,432` |
| **Attention & MLP Matrices (`transformer.h.{0..15}`)** | `96` | `16 x (4 x 1M + 2 x 4M)` | `201,326,592` |
| **Odd-Layer Value-Embedding Gates (`attn.ve_gate.weight`)** | `8` | `8 x (8, 12)` | `768` |
| **Residual, Smear & Backout Scalars (`resid_lambdas`, `x0_lambdas`, `smear_gate`, `smear_lambda`, `backout_lambda`)** | `5` | `16 + 16 + 24 + 1 + 1` | `58` |
| **Total (`d16`)** | **`119`** | — | **`536,871,738`** |

---

## 2. Root-Cause Diagnosis and Six Engineering Repairs

| # | Historical Failure in `SFT50` / `SFT194` / `Fit30` | Root Cause | Implemented Repair in `ganesh_sft_repair.py` and `ganesh/model.py` |
|---|---|---|---|
| **1** | `<\|assistant_end\|>` and `<\|python_start\|>` fail to fire (`end_ce = 7.72` nats while `content_ce = 0.004` nats) | `Base10B` never updated special token rows `32760..32767` (`RMS = 0.060` vs `<\|bos\|>` `RMS = 0.345`). Raw logits started at `-42.0`, where `15 * tanh(z / 15)` has derivative `0.014` (`98.5%` gradient vanishing). | `calibrate_control_token_heads()` scales `IDs 32760..32767` in `lm_head`, `transformer.wte`, and all 8 `value_embeds` tables to `>= 65%` of `<\|bos\|>` RMS before step 1. |
| **2** | 8-epoch memorization on 349 sessions (`train_loss = 0.0000839`, dev CE rising from `2.31` to `3.62`) | Uniform token loss let prose tokens overfit to `0.004` CE while rare action delimiters remained under-trained. | `action_weighted_sft_loss()` applies a `3.0x` loss weight to `<\|assistant_end\|>`, `<\|python_start\|>`, and `<\|python_end\|>`, and caps SFT at `2` epochs (`1,523` conversations). |
| **3** | `100%` compulsive tool-call hallucination on `Hi!` when `permit_calls=True` | `SFT194` had `0` `enabled_no_call` training examples, and `Fit30` had `0` `enabled_call` examples. | `build_ganesh_sft_v2.py` balances all 3 modes in `reports/ganesh-sft-repair-v2/train.jsonl`: `disabled_no_call = 472`, `enabled_no_call = 494`, and `enabled_call = 557`. |
| **4** | Model echoes policy JSON boilerplate or leaks `<\|bos\|>` mid-reply | `nano_chat_format.py` injected 85 tokens of JSON legalese per user turn, and `nano_sft.py` packed unrelated sessions with unmasked `<\|bos\|>` padding. | `compact_policy_header()` replaces the 85-token header with `[tools:off]` or `[tools:on allowed=...]`, `build_single_conversation_batch()` isolates each session with `NATIVE_IGNORE` (`-1`), and `generate_action_repaired()` masks `<\|bos\|>` (`32759`) to `-inf`. |
| **5** | Multi-turn context forgets entities and user corrections (`2/8` pass rate) | `SSSL` sliding window restricted 12 of 16 layers to half-context (`1,024` tokens). | `GaneshGPT.set_full_causal_attention()` upgrades `SSSL` to `LLLLLLLLLLLLLLLL` (`16/16` full causal layers) during SFT and inference. |
| **6** | `0/37` pass rate on 10-tool CRUD benchmark and aggressive weight destruction | `nano_chat_format.py` rejected all tools except `calculate`/`convert`, and `nano_sft.py` reused stale `step=19074` pretraining Muon moments (`lr=0.02`). | `validate_any_tool_call()` validates all 12 tools (`calculate`, `convert`, plus 10 CRUD tools), and `build_fresh_sft_optimizer()` uses a clean AdamW optimizer (`lr = 3e-5`, cosine schedule). |
