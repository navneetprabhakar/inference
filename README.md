# English SLM from scratch

Owner: Navneet Prabhakar (Forge). This project builds its own English model from random weights, followed by conversation and internal/MCP tool use. No public pretrained model weights are used. The reference experiment reuses a tokenizer.

## Current measured state

- Own **15,191,712-parameter** TinyStories reference model; retained checkpoint has **78,774,272 applied target exposures**. This is an early benchmark checkpoint, not a completed foundation.
- Native MLX BF16 with FP32 master weights reached **14,081 tokens/s** in the final 30 minutes of a bounded confirmation run on an M4/24GB Mac. The full 13.1072B-position recipe still projects **13–14 days**, including 20% overhead. Power conditions varied; this is not a controlled constant-power comparison.
- **Full training is paused.** The three-hour benchmark is complete. Legacy runtime launch guards remain in place; a benchmark receipt is not approval for a full run.
- Response diagnostic: **0/8 coherent story continuations; 0/24 correct chat-format outputs across 12 scenarios**. Chat templates were never trained; the separate story failures are the stronger evidence of weak base coherence. These are development diagnostics, not the formal English acceptance gate.
- **GPT-6 Luna** reviewed the failures through the Codex CLI. Sixteen manually reviewed correction examples are prepared (**217 assistant target tokens, including EOS; 520 total tokens**). They have not been used for student training. This tiny seed is insufficient for conversation training.

## Evidence and reproduction

- [Latest response assessment and raw outputs](restart/conversation-readiness-v1/REPORT.md)
- [Native benchmark results](restart/mac-native-benchmark-v1/report.json) and [verification](restart/mac-native-benchmark-v1/verification.json)
- [Reference experiment](restart/mac15m-feasibility-v1/report.json) and [data receipt](restart/mac15m-feasibility-v1/data-receipt.json)
- [Current work and prior decisions](restart/execution-v1/STATUS.md)
- [English gate specification](restart/ENGLISH_GATE.md) and [milestone plan](restart/MILESTONE_PLAN.md)
- [Cleanup record](restart/CLEANUP_AND_DATA.md), [cleanup manifest](restart/cleanup-manifest.json), and [FineWeb salvage review](restart/fineweb-salvage-reviewed-v1/REPORT.md)

The response scripts pin the exact local benchmark checkpoint SHA and enforce read-only student evaluation. Teacher generation requests exactly `gpt-6-luna`, with tools disabled, one request, and a 240-second deadline. No backend-resolved model identity is returned by the CLI; receipts distinguish requested identity from observed metadata. The bounded native benchmark has no full-training mode. Experiment scripts are historical execution artifacts; inspect their contracts and resource bounds before running anything.

Python dependencies for the native experiment are recorded in `restart/mac-native-benchmark-v1/runtime-versions.json`. It ran in its own virtual environment; the root environment remains separate. The latest local checkpoint is `restart/mac-native-benchmark-v1/confirmation/checkpoint.pt`. Weights, optimizer states, token shards, source corpora, downloaded upstream code, virtual environments, and raw CLI event streams are intentionally not committed. Checkpoint hashes, data/source pins, code, and selected receipts are versioned. A clone does not contain a runnable trained model or the full local audit history. JSON evidence is selected explicitly to avoid committing corpus payloads.

The original pre-restart experiment was archived locally at `/Users/navneetprabhakar/Documents/git/image/inference-history-20261021/`; its Git history remains available. Archived launch approvals do not authorize current work. Original design documents describe their historical state; the measured state above and the latest execution records supersede their old status text without changing their acceptance thresholds.
