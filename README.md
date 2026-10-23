# English SLM from scratch

Owner: Navneet Prabhakar (Forge). This project builds its own English model from random weights, followed by conversation and internal/MCP tool use. No public pretrained model weights are used. The reference experiment reuses a tokenizer.

## Current measured state

- Own **15,191,712-parameter** TinyStories reference model; latest checkpoint is step **1745**, with **228,720,640 retained target exposures**. No public pretrained model weights were used.
- The second approved continuation finished **572 updates / 74,973,184 additional targets** in **113.6 training minutes**. Validation NLL **1.710→1.527**; grammar **71→75/100**; grounded completion **27→42/100**.
- **The mandatory +150M narrative progress gate failed. All training is paused.** Primary review passed **8/100**, GPT-6 Sol **14/100**, and their conservative intersection **3/100**, below the required20. Prior/current outputs regraded with Sol had the same conservative score: **3→3/100**. Original Luna-based historical scores remain preserved.
- Numerical and resource checks passed: exact CPU checkpoint reload, FP32/BF16 loss difference **0.000131** within0.02, peak supervised RSS **1.48GiB**, zero additional swap. All workers exited. No further foundation run, conversation SFT or tool training is authorized.
- These are development diagnostics:100 stories span20 template families;100 grammar trials contain45 distinct pairs. Native-shard leakage is unresolved and the formal English gate is unpassed. No generated document boundaries occurred in current outputs; this does not explain the behavioral failure.
- Final30-minute training throughput was **10,682 targets/sec**. Further ETAs must use sustained rates and retain their wall-clock stops.
- **GPT-6 Sol (`gpt-6-sol`)** is the selected reviewer through Codex CLI. It graded prior/current outputs in one blinded paired request. The16 earlier Luna correction seeds (217 assistant targets) remain unused for student training.

## Evidence and reproduction

- [Latest completed stage, failed gate and raw evidence](restart/foundation-stage2-v1/REPORT.md)
- [Second-stage contract](restart/foundation-stage2-v1/PLAN.md)
- [Previous completed foundation stage and raw outputs](restart/foundation-stage1-v1/REPORT.md)
- [Corrected inference-only preflight](restart/foundation-inference-preflight-v2/REPORT.md)
- [Earlier conversation diagnostic](restart/conversation-readiness-v1/REPORT.md)
- [Native benchmark results](restart/mac-native-benchmark-v1/report.json) and [verification](restart/mac-native-benchmark-v1/verification.json)
- [Reference experiment](restart/mac15m-feasibility-v1/report.json) and [data receipt](restart/mac15m-feasibility-v1/data-receipt.json)
- [Current work and prior decisions](restart/execution-v1/STATUS.md)
- [English gate specification](restart/ENGLISH_GATE.md) and [milestone plan](restart/MILESTONE_PLAN.md)
- [Cleanup record](restart/CLEANUP_AND_DATA.md), [cleanup manifest](restart/cleanup-manifest.json), and [FineWeb salvage review](restart/fineweb-salvage-reviewed-v1/REPORT.md)

The response scripts pin the exact local benchmark checkpoint SHA and enforce read-only student evaluation. The latest checkpoint review requests exactly `gpt-6-sol`, with tools disabled, one blinded paired request and a 240-second deadline; historical Luna receipts remain preserved. No backend-resolved model identity is returned by the CLI; receipts distinguish requested identity from observed metadata. The bounded native benchmark has no full-training mode. Experiment scripts are historical execution artifacts; inspect their contracts and resource bounds before running anything.

Python dependencies for the native experiment are recorded in `restart/mac-native-benchmark-v1/runtime-versions.json`. It ran in its own virtual environment; the root environment remains separate. The latest local checkpoint is `restart/foundation-stage2-v1/stage2-checkpoint.pt`. Weights, optimizer states, token shards, source corpora, downloaded upstream code, virtual environments, and raw CLI event streams are intentionally not committed. Checkpoint hashes, data/source pins, code, and selected receipts are versioned. A clone does not contain a runnable trained model or the full local audit history. JSON evidence is selected explicitly to avoid committing corpus payloads.

The original pre-restart experiment was archived locally at `/Users/navneetprabhakar/Documents/git/image/inference-history-20261021/`; its Git history remains available. Archived launch approvals do not authorize current work. Original design documents describe their historical state; the measured state above and the latest execution records supersede their old status text without changing their acceptance thresholds.
