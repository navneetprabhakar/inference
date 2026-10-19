# Bounded SFT execution and real complete-step preflight

Creator: Navneet Prabhakar

Date: 19 October 2026

## Result

The separate research SFT entry point now supports exact foundation-weight import, explicitly fresh AdamW, checked same-stage resume and shared experiment exposure accounting. **64 focused checks pass**, including actual tiny MLX and PyTorch CPU execution. No CUDA claim follows.

The final real **81M MLX initialization-only probe** preserves all **218 tensors / 80,765,440 FP32 values** exactly, with empty optimizer, zero local counters and no update events. Both full-size disposable optimizer-step preflights pass on the Apple M4 / 24 GiB host. **No real SFT data has trained the conversational checkpoint; its score remains 5/100.**

Next: freeze optimizer selection, validation/regression criteria and terminal conversation assessment into the launch contract, then execute the finite screens and selected continuation. The entry point refuses real training without that contract; it is not yet created.

## Separate training path

`slm.research_sft_stage.ResearchStageInputs` consumes an explicit version-2 spec through the pinned research reader. It verifies the entire admitted source-to-token stream before model allocation, keeps the original architecture/tokenizer/numerical conventions, and reconstructs the exact scheduled group order. It supports one token component or a finite single-component mixture; curriculum/mixed-source expansion is refused.

The transition checks the actual terminal foundation checkpoint, report and event coverage. Foundation weights are imported exactly; source counters and lineage remain recorded. **Fresh optimizer is an explicit objective-transition policy**, never an ordinary resume behavior. Learned same-stage resume preserves its optimizer/counters and must refer to a checkpoint already recorded by the same experiment ledger. Zero-step imports cannot smuggle changed foundation weights.

Original readers, all 26 historical runtime files and the earlier stage-transition implementation remain unchanged. No runtime monkeypatch or relaxed resume binding is used. Model/data logical identity remains independent of backend choice. Tiny learned MLX state imports exactly to CPU without updates; this is separate from actual CUDA resumed-training quality, which remains open.

## Experiment-wide physical accounting

Every training invocation requires a frozen contract binding its exact plan/policy, limits, matching successful per-plan preflight and required terminal conversation/score assessment. Preflight device checks apply to training; an initialization-only import can examine recorded learned state on the other locally allowed backend without taking gradients.

`ExposureLedger` uses an exclusive file lock, a fixed execution location, a hash-linked reservation/checkpoint journal and a separately saved committed head:

- Charge positions, one update and all consumed groups **before** calling the optimizer. Failed/uncertain reservations remain charged.
- Share charges across optimizer screens, branches and resumed invocations. Enforce position/update/group-pass ceilings without hidden replay.
- Record checkpoint identities for learned resume admission. Copying the contract into another folder cannot silently create a fresh budget.
- Reject missing journals/heads, complete-prefix truncation, changed committed tails and incompatible contracts.
- Recover a valid durable suffix after a crash conservatively: retain every extra charge and advance the head, never roll back to its earlier count.

The ledger is local execution accounting, not a portable-model-format restriction or an authorization to use GCP. This research policy still allows only local MLX or PyTorch CPU. Future cloud validation requires the appropriate accounting/authorization boundary.

## Frozen execution-plan candidates

Final plan preparation is `data/iteration-three-sft-stage-v2/`. Both plans differ only in peak learning rate, **1e-5 versus 5e-5**. They use four microbatches per optimizer update, 8,192 processed-position warmup and unchanged FP32 dense-embedding/legacy-loss conventions. Checkpoint cadence is 64 updates, retaining two checkpoints.

The deterministic single-component schedule contains **1,900 whole-dialogue batches**, exactly two passes over the 950 prepared train dialogues:

| Measure | Prepared execution plan |
| --- | ---: |
| Selected logical chain | 475 updates |
| Prediction positions | 800,130 |
| Assistant targets | 716,288 |
| Repeated prepared prediction positions | 400,065 |
| Prospective screen prefix | 64 updates / 256 batches |
| Discarded screen prefix positions | 115,195 |
| Selected chain plus one discarded prefix | 915,325 |

The prospective combined total is below the **1,048,576** physical-data-position ceiling. Screened prefix groups would receive at most three physical passes; other groups two. These are prospective counts, not executed training. The learning-rate selection/regression protocol and launch contract remain separate work; no candidate is selected based on resource timing.

## Real full-size resource probes

`slm.sft_research_preflight` loads a disposable copy of the actual foundation weights and performs **one complete cold fresh-optimizer step** per candidate. Each uses four synthetic microbatches of length 1,583, the longest admitted training sequence, with a shifted seeded content-token stream and half-target masks. This includes gradient computation/export, supervised normalization, clipping and AdamW, plus finite parameter/moment checks. The main source checkpoint is reopened and unchanged; the clone is discarded.

| Candidate peak LR | Complete first-step interval | Peak Metal allocation |
| --- | ---: | ---: |
| 1e-5 | 4.964187 s | 5,949,264,664 bytes / 5.54 GiB |
| 5e-5 | 4.907795 s | 5,949,264,664 bytes / 5.54 GiB |

Each clone performs 6,332 synthetic gradient positions / 3,168 masked positions. Total: **12,664 synthetic gradient positions / two disposable optimizer updates / zero main-student updates**, within the separate 16,384-position policy ceiling. A preflight reservation journal charges each trial before its clone update and refuses silent replay.

These are **fresh-optimizer first steps**, not a sustained or steady-state benchmark. Later optimizer moments, real mask/length distributions, checkpoint overhead, thermal effects and background load can change resource use. Peak allocation is observed after subsequent finite checks; process-lifetime RSS includes earlier verification. Do not sum allocator, cache and RSS on this unified-memory host or treat these peaks as upper bounds. The timing difference does not establish a learning-rate performance effect. Hardware was observed after the probes, not used as a thermal control.

## Verification and retained development history

The 64-check suite covers exact tiny own-resume on both local backends, learned-state MLX-to-CPU import without updates, same-stage counters/moments, finite mixture order, authority/recipe/model/data limits, physical caps, concurrent invocation refusal, bad preflights, unknown resume checkpoints, copied contracts, lost/truncated journals, changed tails and conservative suffix recovery. Tests use synthetic source decisions and do not grade real language quality.

The independent actual checker reopens the final initialization, both source/initialized checkpoint trees, all model tensors, both complete-step receipts, their reservations, execution-plan hashes and current reference sources. It confirms original runtime hashes remain intact and both plans differ only in LR.

Before actual gradients, the first development plan/import was superseded to add the committed-head rollback guard. Its initialization, protocol and source snapshot remain under `data/iteration-three-sft-stage-v1/`; it is not reused as a current plan. **V1 consumed zero synthetic gradient positions and zero main updates.** Final v2 completes both reserved probes without replay. An earlier static run-loop indentation error and an extra argument in a tiny resume-test helper were corrected before final execution; source/error records remain under `data/research-sft-stage-development-v1/`. No tolerance, source admission or historical failure is waived.

The final staged whitespace audit identifies one extra empty line at the frozen runner's EOF. Preserve its executed bytes and source hashes; an explicit blank-at-EOF exception is used for this audit, while all other whitespace checks remain active. No runtime, numerical or admission rule changes.

Evidence: [final execution plans](../reports/milestone-sixty-two-sft-stage-plans-v2.json), [actual full-size probes and integrity checks](../reports/milestone-sixty-two-actual-stage-probes.json), [test receipt](../reports/milestone-sixty-two-tests.xml), [observed hardware](../reports/milestone-sixty-two-hardware.json).

## Reproduction and next action

```sh
.venv/bin/python scripts/prepare-research-sft-stage.py
.venv/bin/python scripts/probe-research-sft-stage.py --trial lr-00001 --mode initialize
.venv/bin/python scripts/probe-research-sft-stage.py --trial lr-00001 --mode preflight
.venv/bin/python scripts/probe-research-sft-stage.py --trial lr-00005 --mode preflight
.venv/bin/python scripts/check-research-sft-stage-probes.py
```

The completed attempt refuses replacement/replay. The checker reopens retained evidence. Finalize frozen validation and optimizer-choice/regression rules, baseline/terminal diagnostics, actual raw-history conversation/direct-score contract and the experiment launch contract before taking real SFT gradients. Use the existing prepared corpus; do not reopen broad data selection as an unnecessary prerequisite to this bounded pilot.

Every completed meaningful training iteration still requires actual conversation and direct assessment before the following iteration. Required teacher use, broad English/styles/content, learned tools/MCP, actual MLX/CUDA resumed-training quality, deployment optimization and ESCI remain open. No teacher/model API call, cloud job, paid activity or spending change; full goal active/incomplete.
