# English SLM from scratch

Owner: Navneet Prabhakar (Forge). Goal: our own English foundation model with conversation and internal/MCP tool capabilities, below 100M learned parameters. Public pretrained model weights are not used; the reference experiment reuses a tokenizer.

## Current measured state — transfer trial failed; stopping improved

- **Latest matched transfer test failed:** short-answer-first scored 1/48 correct+EOS on fresh probes; shuffled control scored 2/48. Both scored 0/16 on paired fact-change checks. EOS endings improved to 40/48 and 43/48; reliable factual grounding did not pass.
- Both arms consumed 200 updates each, with identical full SFT exposure multisets and narrative replay order: 152,642 SFT target exposures plus 819,200 replay exposures across separate models. Execution took 173.71 seconds. Selected update 175 research checkpoints remained within the original 5% narrative-regression guardrail (+4.94%/+4.45%). No checkpoint was promoted; training is paused.
- **Earlier memorization diagnostic passed:** eight directly reviewed training conversations, all 10 assistant answers reproduced exactly, including two correction sequences; EOS emitted on all 10 turns. Stopped early at update 25 after 1,100 supervised target exposures and 12.48 seconds of execution. Foundation narrative NLL rose 3.24%, within the unchanged 5% guardrail. This tests training-set memorization, not unseen generalization. No checkpoint was promoted.
- **Earlier broader conversation diagnostic:** 62 directly reviewed training conversations, 10 development and 10 test conversations. Three passes consumed 24 updates and 11,490 assistant/EOS target exposures. All 84 selected records were inspected; two training records were excluded without replacement.
- **Earlier held-out response quality: 0/24 before and 0/24 after.** Repetitive story continuations persisted, and no output emitted an EOS end-of-turn token. Lower token loss did not establish conversational capability. No checkpoint was promoted; further training is paused.
- Epoch 2 was selected using development loss alone: 16 retained SFT updates and 7,660 retained SFT target exposures. Held-out test assistant NLL fell from 5.897426 to 5.323741 (9.7%); narrative foundation NLL rose from 1.343035 to 1.380192 (2.8%, within the 5% guardrail). Epoch 3's 8 updates/3,830 exposures remain charged but were not selected.
- Model size remains **15,191,712 parameters**. The original reference remains our own cooldown checkpoint at foundation step 3145, with 412,221,440 retained foundation target exposures; its hash is unchanged. Research SFT child checkpoints retain separate optimizer/exposure provenance and are not an English/conversation release.
- Masked native BF16 versus independent Torch FP32 preflight passed: NLL difference 0.002218, gradient relative L2 error 0.01919, cosine 0.9998165. Changing masked target labels or right-padding inputs changed loss by zero. Two setup-only failures occurred before model work; all stops are preserved, with the same aggregate clock and caps.
- The new 1,000-conversation Sol batch retained **957 screened candidates**: 759 training, 100 development, 98 test. These are not fully certified training data. The diagnostic used only its separately reviewed subset. No actual internal/MCP tool-call traces were generated.
- **Foundation recovery remains stopped:** R0 calibration passed, D0 data admission failed, and R1/R2 never started. Its 15,764 documents / 13,657,292 native content tokens remain provisional; semantic and mixture admission failed, and cross-split audits remain incomplete. No new broad foundation data was admitted. The heuristic domain counts are not a certified measure of coverage.
- All workers have exited. No automatic continuation, new downloads, new model architecture, or tool training occurred. Formal English and conversation gates remain unpassed.

## Evidence and lineage

- [Latest matched transfer report](restart/short-answer-transfer-v1/README.md), [decision](restart/short-answer-transfer-v1/decision.json), [correctness](restart/short-answer-transfer-v1/correctness.json)
- [Earlier eight-conversation memorization report](restart/conversation-memorization8-v1/README.md), [decision](restart/conversation-memorization8-v1/decision.json), [correctness](restart/conversation-memorization8-v1/correctness.json)
- [Earlier bounded SFT report](restart/sol-conversation-sft-diagnostic-v1/README.md), [decision](restart/sol-conversation-sft-diagnostic-v1/decision.json), [correctness](restart/sol-conversation-sft-diagnostic-v1/attempt-3/correctness.json)
- [1,000-conversation batch](restart/sol-conversation-data-1000-v1/README.md), [earlier 100-conversation batch](restart/sol-conversation-data-v1/README.md)
- [Corrected foundation recovery report](restart/foundation-recovery-v2-corrected/REPORT.md), [metrics](restart/foundation-recovery-v2-corrected/report.json), [terminal stop](restart/foundation-recovery-v2-corrected/STOP.json)
- [Approved recovery design](restart/foundation-recovery-v2/PLAN.md), [blanket approval receipt](restart/foundation-recovery-v2-corrected/approval-receipt.json)
- [Preserved preparation-defect stop and correction proposal](restart/foundation-recovery-v2/REPORT.md)
- [Earlier resolution experiment](restart/foundation-resolution-v1/REPORT.md), [previous foundation stage](restart/foundation-stage3-v1/REPORT.md)
- [Formal English gate](restart/ENGLISH_GATE.md), [milestone plan](restart/MILESTONE_PLAN.md), [goal path](restart/foundation-stage3-v1/GOAL_PATH.md)
- [Native Mac benchmark](restart/mac-native-benchmark-v1/report.json), [original reference/data receipt](restart/mac15m-feasibility-v1/data-receipt.json)
- [Historical work log](restart/execution-v1/STATUS.md), [cleanup and license/provenance context](restart/CLEANUP_AND_DATA.md)

Conversation generation requested exactly `gpt-6-sol` through the pinned Codex CLI with tools disabled. Backend-resolved identity was unavailable. Usage and data-token counts are recorded separately per experiment. No new teacher call was used by the bounded SFT diagnostic.

Weights, optimizer states, source corpora, token shards, private evaluation plaintext, virtual environments, SQLite and raw CLI events remain local and outside Git. Reusable code, aggregate evaluation results, hashes and audit receipts are versioned. Exact executed SFT source snapshots containing private probes remain local with versioned hashes. A clone does not contain trained weights or the full local corpus/runtime. Historical scripts and approvals are not permission to rerun terminal experiments. Latest receipts supersede older status prose without rewriting older results or relaxing gates.
