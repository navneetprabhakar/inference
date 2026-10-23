# English SLM from scratch

Owner: Navneet Prabhakar (Forge). Goal: our own English foundation model with conversation and internal/MCP tool capabilities, below100M learned parameters. Public pretrained model weights are not used; the reference experiment reuses a tokenizer.

## Current measured state — stopped at data admission

- **Corrected foundation recovery:** R0 evaluator calibration passed; D0 data admission failed. R1 and R2 never started. Blanket execution approval and all failed attempts remain recorded. No further overnight approval request is pending.
- Model size remains **15,191,712parameters**. The selected research reference is our own cooldown checkpoint at step3145, with412,221,440retained target exposures. It is not an accepted English/conversation release. All original checkpoint hashes remain unchanged.
- **Zero new training updates.** Native BF16 versus independent FP32 NLL difference was at most0.000233; teacher repeat agreement95%, primary/teacher kappa0.649/0.792. Selected-reference conservative coherence was only1/20and new premise-grounded accuracy37/100. Calibration passing does not establish capability.
- D0 produced **15,764provisional documents /13,657,292native content tokens** after filtering/deduplication/protected exclusions. Only1,460,204tokens were everyday explanations, below the required1.5M in training alone. These counts are not admitted/usable supply.
- The once-frozen50uniform+50weighted semantic sample failed during the first six full uniform reviews: out-of-scope poetry, a media-only stub and duplicated classroom text were present. **Zero new broad documents/tokens were admitted.**94draws and the cross-split100-nearest audit remain unreviewed/unrun; no accepted train/dev/sealed split exists.
- All workers are reaped. No downloads, new student initialization, conversation SFT or tools training occurred. The immediate blocker is data admission; formal English and conversation gates remain unpassed.

## Evidence and lineage

- [Latest corrected recovery report](restart/foundation-recovery-v2-corrected/REPORT.md), [metrics](restart/foundation-recovery-v2-corrected/report.json), [terminal stop](restart/foundation-recovery-v2-corrected/STOP.json)
- [Approved recovery design](restart/foundation-recovery-v2/PLAN.md), [blanket approval receipt](restart/foundation-recovery-v2-corrected/approval-receipt.json)
- [Preserved preparation-defect stop and correction proposal](restart/foundation-recovery-v2/REPORT.md)
- [Earlier resolution experiment](restart/foundation-resolution-v1/REPORT.md), [previous foundation stage](restart/foundation-stage3-v1/REPORT.md)
- [Formal English gate](restart/ENGLISH_GATE.md), [milestone plan](restart/MILESTONE_PLAN.md), [goal path](restart/foundation-stage3-v1/GOAL_PATH.md)
- [Native Mac benchmark](restart/mac-native-benchmark-v1/report.json), [original reference/data receipt](restart/mac15m-feasibility-v1/data-receipt.json)
- [Historical work log](restart/execution-v1/STATUS.md), [cleanup and license/provenance context](restart/CLEANUP_AND_DATA.md)

Teacher review requested exactly`gpt-6-sol`through the pinned Codex CLI, high reasoning, tools disabled and120seconds/request. Backend-resolved identity is unavailable. Ten requests used39,376observed output-plus-reasoning tokens. Teacher reviews never became student training data.

Weights, optimizer states, source corpora, token shards, private sealed plaintext, virtual environments, SQLite and raw CLI events remain local and outside Git. Source code, evaluation outputs, hashes and audit receipts are versioned. A clone does not contain trained weights or the full local corpus/runtime. Historical scripts/approvals are not permission to rerun terminal experiments. Latest receipts supersede older status prose without rewriting older results or relaxing gates.
