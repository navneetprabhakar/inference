# Architecture, data and evaluation — 31 October 2026

## Model and execution

Native MLX causal language model: 97,536,768 parameters, 12 layers, width 768, 16K vocabulary and 512-token context. Fresh byte-level BPE and random initialization were used at restart. Training uses FP32 master weights/AdamW state, BF16 compute and gradient clipping. Current inference recomputes the sequence each token; do not assume a production KV-cached serving engine.

`benchmark_mlx.py` defines the model; `sft_common.py` supplies conversation rendering, generation and memory controls. `sft_v3.py` defines typed offline tool contracts, aliases and fixtures. `train_sft_v3.py` implements weighted repair training; `evaluate_sft_v3.py` implements strict execution scoring; `select_sft_v3.py` selects using development data. All are under scripts/.

Tool fixtures simulate calculations, conversion, weather, inventory and lookup. They do not connect the model to live external systems. Generated calls are evaluated against contracts and deterministic fixture results.

## Frozen V3 data

20,500 training examples: 5,000 chat; 3,000 single tool; 2,500 result-only; 2,500 chains; 1,500 clarification; 500 error; 500 no-tool; 2,000 grounded; 3,000 replay. Development has 550 cases and test has 1,000.

Chat training reuses filtered existing Smol-SmolTalk training examples. Fresh chat evaluation came from a separately pinned public shard with overlap filtering. Replay uses old TRAIN blocks, 1,500 each FineWeb/TinyStories; protected loss blocks were excluded. Tool examples include aliases, distractors, four chain routes, nine missing slots, five error types and paired counterfactual results. Language remains template-correlated.

Data preparation and verification: `prepare_sft_v3.py`, `verify_sft_v3.py`. Preserve upstream receipts, source terms and hashes; no paid teacher generation was used. Synthetic data may still have upstream model provenance. Existing local raw corpora were reused without inheriting old model weights or tokenizers.

## Loss and token accounting

Result-only/error examples mask supplied call/result history and supervise the final assistant answer. Other SFT examples supervise assistant spans; replay supervises language-model targets. Dynamic trimming reduces padding to about 1%.

Each repair arm processed 2,000,000 input slots: 1,980,007 nonpadding tokens and 770,234 supervised targets. These quantities are not interchangeable. Source weights target aggregate weighted mass of 25% chat, 50% tool, 10% grounded and 15% replay; that is not a claim about gradient contribution or learning gain. Fractional target mass is preserved through accumulation. Both arms use the same exposure order and fresh AdamW from the same source checkpoint.

## Evaluation contract

- Full tool success requires exact intended calls and the canonical final answer. Schema validity alone is insufficient.
- Wrong but valid calls execute their own fixture result, never the intended call's gold result.
- Report call sequence accuracy, per-argument/per-step accuracy and final-answer success conditional on exact calls separately.
- Clarifications report canonical exact and finite accepted-reference scores separately.
- Chat coherence requires human review; repeated four-grams and EOS are diagnostics only.
- Retention perplexity uses frozen loss sets. Development selection precedes test evaluation. Inspected test results are no longer fresh confirmation evidence.

The penalty sweep held weights/data fixed, used greedy decoding and a 96-token cap, and changed only the generated-token penalty. It included JSON tokens, explaining a plausible mechanism for tool degradation; the measured association does not isolate every causal factor. Proposed prose/tool separation is not yet implemented.
