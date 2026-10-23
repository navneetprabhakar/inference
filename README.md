# English SLM from scratch

Owner: Navneet Prabhakar (Forge). Goal: our own English foundation model with conversation and internal/MCP tool capabilities, below100M learned parameters. No public pretrained model weights are used; the reference experiment reuses a tokenizer.

## Current measured state — training paused

- **Post-run audit found an evaluator defect:** all600grammar/grounding candidates contain an extra whitespace token. The historical option-score changes below are not clean normal-text capability measurements. Sol's continuous rubric mean improved4.45→5.06/10despite flat binary passes; primary/Sol kappa0.222shows weak agreement. See [cause audit](restart/foundation-cause-audit-v1/REPORT.md). No corrected inference or training has run.
- Latest own checkpoint: **15,191,712 parameters**, step **2889**, **378,667,008 retained training target exposures**. The owner-approved successor completed1144updates/149,946,368additional targets and stopped. Parameters did not increase.
- **Development gate failed.** Validation NLL1.527115→1.400689; grammar75→78/100, but distinct grammar pairs37→36/45. Grounding regressed42→30/100. Conservative primary∩Sol coherence4/100, below20; the same paired regrade scored the previous checkpoint4/100. Published previous3/100 remains preserved. Primary alone23, Sol5; agent grades are unstable and do not establish conversation readiness.
- Final exact CPU checkpoint/optimizer reload passed. **Independent saved-checkpoint FP32 parity is unverified:** the verifier failed before inference with a missing clock-key error. One attempt consumed; no automatic patch/replay or tolerance change. This remains a failed correctness criterion.
- Training took231.2minutes including initialization. Sustained final30-minute throughput10,499targets/sec; peak supervised RSS1.473GiB; no additional swap/resource breach. All owned workers are reaped. Original cumulative306,104,851/320Mprocessed positions and4/4teacher requests remain charged.
- **No further foundation training, conversation SFT, tool training, new initialization or full reference run is authorized.** The current approval is consumed. The formal English gate is unpassed.

These are development diagnostics:100stories span20template families;100grammar trials contain45distinct pairs. Native-shard deduplication/leakage limitations remain unresolved. Three current continuations generated document-boundary BOS tokens; full response windows remain in the evidence. Lower loss alone has not delivered reliable semantic behavior.

## Path to the actual goal

The15.19M TinyStories model is a prototype, not the selected final broad-English architecture. This was the last proposed bounded exposure test of that narrative lineage. The next decision must address broad-English data admission and a fixed architecture below100M, with measured compute and a justified foundation acceptance gate before conversation/tool stages. See [goal path](restart/foundation-stage3-v1/GOAL_PATH.md). No next experiment is approved.

## Evidence

- [Latest completed experiment, failed gate and verifier failure](restart/foundation-stage3-v1/REPORT.md), [metrics](restart/foundation-stage3-v1/report.json), [terminal stop](restart/foundation-stage3-v1/global-stop.json)
- [Approved successor proposal](restart/foundation-stage3-v1/PLAN.md) and [approval receipt](restart/foundation-stage3-v1/approval.json)
- [Read-only diagnosis](restart/foundation-diagnosis-v1/REPORT.md)
- [Previous completed stage](restart/foundation-stage2-v1/REPORT.md) and [first stage](restart/foundation-stage1-v1/REPORT.md)
- [Corrected inference preflight](restart/foundation-inference-preflight-v2/REPORT.md), [earlier conversation diagnostic](restart/conversation-readiness-v1/REPORT.md)
- [Native benchmark](restart/mac-native-benchmark-v1/report.json), [verification](restart/mac-native-benchmark-v1/verification.json), [reference experiment](restart/mac15m-feasibility-v1/report.json), [data receipt](restart/mac15m-feasibility-v1/data-receipt.json)
- [Current work and prior decisions](restart/execution-v1/STATUS.md), [English gate](restart/ENGLISH_GATE.md), [milestone plan](restart/MILESTONE_PLAN.md)
- [Cleanup](restart/CLEANUP_AND_DATA.md), [cleanup manifest](restart/cleanup-manifest.json), [FineWeb salvage](restart/fineweb-salvage-reviewed-v1/REPORT.md)

Checkpoint review requested exactly GPT-6 Sol (`gpt-6-sol`) through Codex CLI, one blinded paired request with tools disabled and a240-second cap. No backend-resolved identity is returned; receipts distinguish requested identity from observed metadata. Historical Luna/Sol receipts are preserved. Teacher outputs did not enter this training run.

Native dependencies are recorded in `restart/mac-native-benchmark-v1/runtime-versions.json`. Latest local weights: `restart/foundation-stage3-v1/stage3-checkpoint.pt`. Weights, optimizer states, token shards, source corpora, upstream downloads, virtual environments, SQLite ledgers and raw CLI events are excluded from Git. Selected code, hashes, generated evaluation outputs and audit receipts are versioned; a clone does not contain a runnable trained model or the full local audit history. Historical experiment scripts are terminal execution artifacts, not approval to rerun them.

The pre-restart experiment was archived locally at `/Users/navneetprabhakar/Documents/git/image/inference-history-20261021/`; its Git history remains available. Archived approvals do not authorize current work. Latest execution records supersede historical status prose without changing acceptance thresholds.
