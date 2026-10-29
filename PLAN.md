# Laptop-first plan and budget — 29 October 2026

## Decision

Start with an 80M–150M random-weight candidate, selected after measured throughput and a small quality pilot. The previous 654M/100B–300B proposal remains a cloud-scale research option; it is not the laptop minimum. No budget can guarantee useful general conversation. The lower-cost target is short, coherent English dialogue plus 5–10 defined tools with validated arguments and correct result summaries. General knowledge, arbitrary unseen APIs, and long autonomous workflows are outside the first acceptance target.

## Cost assumptions

Incremental cash estimates exclude the existing laptop, developer labor, recurring hosted serving, taxes, and card/FX fees. Free datasets do not imply zero storage, curation or verification effort. INR examples use a rounded planning rate of INR95/USD; Wise displayed about INR95.30 on 29 October 2026 (https://wise.com/us/currency-converter/usd-to-inr-rate/history/29-10-2026).

Runpod's retrieved public page lists RTX4090 at USD0.89/GPU-hour and H100 PCIe at USD2.89/GPU-hour. Availability and measured training throughput determine actual economics. Do not compare devices by hourly price alone. Source: https://www.runpod.io/pricing (retrieved 2026-10-29).

| Path | Incremental cash envelope | Interpretation |
|---|---:|---|
| Laptop feasibility pilot | INR0–5,000 | Existing hardware/free data; power and small incidental expenses. Does not buy a verified usable model. Optional SSD is additional. |
| Minimum credible narrow-assistant attempt, 80M–150M / 10B–30B | USD500–1,500 (INR47,500–142,500) | Laptop preparation/inference and optional rented GPU pretraining; limited iterations. An experiment budget, not a quality guarantee. |
| More defensible iterative small-model budget | USD1,000–3,000 (INR95,000–285,000) | More data/recipe iterations, post-training and evaluation. Still not a frontier/general-assistant promise. |
| Original 654M / 100B | USD2,500–6,000 (INR2.38–5.70 lakh) | Main pretraining, modest experiments, SFT, evaluation and storage reserve. |
| Original 654M / 300B | USD7,000–16,000 (INR6.65–15.20 lakh) | Same scope with more pretraining; repeated full reruns increase this materially. |

Illustrative lower-cost allocation: USD200–900 GPU training/reruns; USD50–200 post-training/evaluation; USD0–100 synthetic-data API (reuse free data first); USD25–100 storage/transfer; USD100–200 contingency, rounded to USD500–1,500. These are allowances, not incurred spend. No paid compute or API use has been authorized.

Calculator: approximate training FLOPs = 6*N*D. With H100 sustained effective 100–200 TFLOP/s (assumption, not measured) and 1.3x operating overhead:
- 150M / 20B, two runs: 65–130 GPU-hours, USD188–376 compute only.
- 654M / 100B, one run: 709–1,417 GPU-hours, USD2,048–4,095 compute only.
- 654M / 300B, one run: 2,126–4,251 GPU-hours, USD6,143–12,285 compute only.

Small models may underutilize GPUs. Explicit attention costs, poor kernels, and long contexts can invalidate 6ND-based estimates. Benchmark first; the rental envelope is conditional. Electricity-only illustration: 30–60W continuously at INR8–12/kWh is approximately INR173–518 per 30 days; actual wall power and tariff have not been measured. Laptop-only cash can be much lower than cloud, but the elapsed time and quality risk remain.

## Fresh laptop measurements

Native MLX, random initialization, BF16, batch 2, sequence 512, vocabulary 16K, forward/backward/AdamW included:

| Model | Short-probe training speed | Peak MLX allocation | 1B tokens | 10B tokens | 30B tokens |
|---|---:|---:|---:|---:|---:|
| 33.6M | 7,678 tokens/s | 0.85 GiB | 1.5 days | 15.1 days | 45.2 days |
| 97.5M | 2,944 tokens/s | 1.53 GiB | 3.9 days | 39.3 days | 117.9 days |

Linear projections assume 24/7 speed equal to the 45–60 second probe. Real runs will be slower with longer contexts, data loading, checkpointing and thermal throttling. Peak MLX allocation is not total system RAM. At 8 hours/day, elapsed calendar time is at least 3x. These are baseline measurements, not optimized hardware limits.

## Data inspected

Fresh script: `scripts/inventory_data.py`; outputs: `reports/local-data.json` plus `reports/supplemental-data.json`.

- TinyStories: all 50 extracted JSON shards parsed, 4,967,871 records. These are the native archive's records, not 4.97M proven-unique training examples. Existing derived bins/tokenizer are not selected for the new model. Useful for plumbing and simplified narrative, not adult conversation as the sole corpus.
- FineWeb-Edu: local Parquet footer confirms 182,101 records; schema and example rows inspected. A separate legacy index has 49,000 FineWeb rows which may overlap; do not add them.
- Wikipedia: local Parquet confirms 156,288 articles; schema and example rows inspected. Large XML partials are not a complete Wikipedia corpus.
- Cosmopedia: retained SQLite contains text for 49,064 records. Fresh SQL count, legacy token estimates only; quality/seed-lineage admission not repeated.
- Fresh JSONL parsing also confirmed 15,011 Dolly instruction rows and 13,854 OpenAssistant conversation trees (not individual English conversations). FineWeb upstream token_count sums to 190,104,122; the TinyStories prior-tokenizer receipt sums to 1,024,921,608. These are not deduplicated new-tokenizer counts.
- Legacy conversation sources are preserved, but counts alone do not establish clean English turns or correctly masked SFT data. No broad executable tool-training corpus was established by this inventory.
- Partial downloads, duplicate versions, indexes, and generated manifests account for substantial disk space. The 85GiB archive directory is not 85GiB of unique training text.
- Laptop initially had about 112GiB free. Moving files does not free disk space. 100B uint16 tokens alone need 200GB decimal: use bounded shards/streaming and external/cloud storage for larger runs. Retain archives; do not redownload entire dumps.

## Source selection

| Source | Role | Retrieved source / limitations |
|---|---|---|
| TinyStories | Pipeline pilot, small narrative fraction | https://huggingface.co/datasets/roneneldan/TinyStories ; synthetic child-vocabulary stories; track dataset terms and validation separation. |
| FineWeb-Edu | Main broader English pretraining | https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu ; ODC-By dataset label, web-source provenance still matters. |
| SmolLM-Corpus / Cosmopedia | Explanatory prose | https://huggingface.co/datasets/HuggingFaceTB/smollm-corpus ; preserve seed lineage and dedup across sources. |
| smol-smoltalk | Conversation SFT | https://huggingface.co/datasets/HuggingFaceTB/smol-smoltalk ; ~460K upstream train rows, Apache-2.0 card; not a replacement for tool trajectories. |
| APIGen / xLAM-60K | Seed tool-call data | https://huggingface.co/datasets/Salesforce/xlam-function-calling-60k ; CC-BY-4.0 card; download gated by acknowledgment. Must be adapted to executable fixtures; does not supply all multi-turn/error behavior. |
| Custom deterministic tools | Execution-grounded SFT/eval | Start with 5–10 local mock tools. Include missing arguments, no-tool cases, errors, renamed functions, and tool-result-to-answer turns. |

Do not buy data or generate a huge paid synthetic corpus initially. Reuse suitable local raw data and download bounded upstream slices only after selecting a token budget. Existing checkpoints and legacy evaluation outputs are never training inputs.

## Execution sequence

1. **Done:** preserve/push archive; clear active tree; inspect hardware and retained data; short MLX throughput probes.
2. **Next:** choose 80M–150M configuration and run a 30–60 minute sustained benchmark with real data, checkpoint writes, and memory monitoring. Current short probes do not establish thermal behavior. Compare MLX baseline against an optimized recipe before committing weeks.
3. Curate a bounded mixed English corpus; train a fresh tokenizer; reserve document/seed families before sampling; manually inspect a small sample for gross quality problems. Avoid recreating the previous sprawling audit process.
4. Train 100M tokens as a pipeline pilot. Verify causal loss/label shifting, resume, tokenizer round-trip, and held-out loss. Early stop for instability or leakage.
5. Continue to 1B tokens only if checks pass. Apply a small diagnostic chat/tool SFT run to a copy and measure actual conversational readiness. Do not mistake training-set memorization for capability.
6. Decide whether to fund 10B–30B on laptop or rented GPU using measured speed and quality. Preserve at least half the project budget until this decision.
7. Mixed SFT: dialogue + complete execution traces + clarification/no-tool/error cases, assistant-only loss. Include source and tool-family holdouts. Full-parameter tuning initially; no RL until a demonstrated need.
8. Release only if blind evaluation supports it: 200+ independently written dialogues, 500+ execution tasks, held-out tool variants, 90% single-call and 80% short-workflow success as proposed narrow-domain gates; report uncertainty and raw vs retry-assisted scores. Conversation acceptance needs a rubric and human review, not one aggregate benchmark.

## References

- SmolLM2 360M used 4T tokens: https://huggingface.co/HuggingFaceTB/SmolLM2-360M . A 10B–30B run cannot be presumed comparable.
- End-to-end low-cost training reference: https://github.com/karpathy/nanochat . Speedrun quality is distinct from reliable tool-assisted dialogue.
- Native Apple training examples: https://github.com/ml-explore/mlx-examples . Current benchmark is a fresh minimal implementation, not a reused old trainer.
- APIGen verification: https://arxiv.org/abs/2406.18518 . Verify format, execute, then check semantics.
- Tool generalization/irrelevance: https://arxiv.org/abs/2410.04587 . Include renamed tools and distractors.
