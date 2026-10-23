# English SLM from scratch

Owner: Navneet Prabhakar (Forge). This project builds its own English model from random weights, followed by conversation and internal/MCP tool use. No public pretrained model weights are used. The reference experiment reuses a tokenizer.

## Current measured state

- Own **15,191,712-parameter** TinyStories reference model; latest checkpoint is step **1173**, with **153,747,456 retained target exposures**. It is an early foundation, not a completed conversational model.
- The approved first continuation finished **572 updates / 74,973,184 additional targets** in110.4 training minutes. Validation NLL **2.367→1.710**; grammar **55→71/100**; grounded comprehension **28→27/100**. Conservative story coherence **0→1/100** (primary agent9/100, GPT-6 Luna1/100; disagreements fail).
- **All training is paused for owner review.** No next foundation stage or conversation SFT is authorized; all workers exited. Original checkpoint, schedule, data and earlier charges remain preserved.
- These are development diagnostics with repeated templates, not the formal English gate. A token audit found generated document-boundary markers in9/100 story outputs; frozen full-window scores remain unchanged. This limitation does not establish conversation readiness.
- Final30-minute training throughput was **10,809 targets/sec**, below the earlier bounded benchmark estimate. Future ETAs must use sustained rates and retain their wall-clock stops.
- **GPT-6 Luna** reviewed the failures through the Codex CLI. Sixteen manually reviewed correction examples are prepared (**217 assistant target tokens, including EOS; 520 total tokens**). They have not been used for student training. This tiny seed is insufficient for conversation training.

## Evidence and reproduction

- [Latest completed foundation stage and raw outputs](restart/foundation-stage1-v1/REPORT.md)
- [Corrected inference-only preflight](restart/foundation-inference-preflight-v2/REPORT.md)
- [Earlier conversation diagnostic](restart/conversation-readiness-v1/REPORT.md)
- [Native benchmark results](restart/mac-native-benchmark-v1/report.json) and [verification](restart/mac-native-benchmark-v1/verification.json)
- [Reference experiment](restart/mac15m-feasibility-v1/report.json) and [data receipt](restart/mac15m-feasibility-v1/data-receipt.json)
- [Current work and prior decisions](restart/execution-v1/STATUS.md)
- [English gate specification](restart/ENGLISH_GATE.md) and [milestone plan](restart/MILESTONE_PLAN.md)
- [Cleanup record](restart/CLEANUP_AND_DATA.md), [cleanup manifest](restart/cleanup-manifest.json), and [FineWeb salvage review](restart/fineweb-salvage-reviewed-v1/REPORT.md)

The response scripts pin the exact local benchmark checkpoint SHA and enforce read-only student evaluation. Teacher generation requests exactly `gpt-6-luna`, with tools disabled, one request, and a 240-second deadline. No backend-resolved model identity is returned by the CLI; receipts distinguish requested identity from observed metadata. The bounded native benchmark has no full-training mode. Experiment scripts are historical execution artifacts; inspect their contracts and resource bounds before running anything.

Python dependencies for the native experiment are recorded in `restart/mac-native-benchmark-v1/runtime-versions.json`. It ran in its own virtual environment; the root environment remains separate. The latest local checkpoint is `restart/foundation-stage1-v1/stage1-checkpoint.pt`. Weights, optimizer states, token shards, source corpora, downloaded upstream code, virtual environments, and raw CLI event streams are intentionally not committed. Checkpoint hashes, data/source pins, code, and selected receipts are versioned. A clone does not contain a runnable trained model or the full local audit history. JSON evidence is selected explicitly to avoid committing corpus payloads.

The original pre-restart experiment was archived locally at `/Users/navneetprabhakar/Documents/git/image/inference-history-20261021/`; its Git history remains available. Archived launch approvals do not authorize current work. Original design documents describe their historical state; the measured state above and the latest execution records supersede their old status text without changing their acceptance thresholds.
