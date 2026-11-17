# Ganesh-base: local pilot readiness

17 November 2026. Creator: Navneet Prabhakar.

**Local preparation is complete for the bounded pilot. Cloud launch remains on HOLD.** No new cap is approved. No training, cloud write, HTTP start, model promotion or sealed release evaluation occurred. Reauthentication succeeded; the read-only inventory recorded zero VMs and disks. This is not GPU qualification or evidence of model improvement.

## Integrated execution

The hash-bound controller executes six stages: frozen fit training → checkpoint probes → full semantic review → curriculum pilot → baseline/best/last probes → full semantic review. It runs only after actual qualification receipts exist. Provisioning and qualification are separate supervised steps, not implemented as an automatic provisioning daemon by this controller.

Every command passes the evidence/cap/lease gate, uses pinned code and data, journals intent before spawning, verifies outputs, and cannot silently replay an interrupted task. A machine-wide SFT writer lock supplements output-directory and controller locks. Timeout/signal handling terminates and joins worker process groups. Review jobs can finish locally after compute stops; they cannot authorize another command without renewed valid gates. Human/agent semantic reviews remain explicit, hash-bound and complete; the controller does not grade its own answers as correct.

The actual unapproved request was submitted to the dispatch path and returned `hold_gate` without spawning a worker. Evidence: `unauthorized-dispatch.json`. Request template: `request-template.json`; approval-time paths, absolute lease, quote and cloud evidence still must be finalized.

## Reviewed curriculum

`../ganesh-english-curriculum-v2/` is a frozen synthetic seed pilot, fully reviewed: 31 train sessions / 91 user turns / 1,052 unique assistant target positions; 16 development sessions / 47 turns / 496 reference target positions. All 138 turns have review records; all six calculator calls were replayed. Both no-call modes and positive tool calls are represented. Identity contributes 45 train targets (4.28%), from three train examples; two identity development examples remain separate. These examples have not been trained into the weights.

Natural lessons cover ordinary English, instructions, corrections and within-conversation recall after distractors. They are short: at most 638 serialized tokens. This is not long-context qualification. Source/scenario groups and exact prompts are separated; abstract task structures overlap. Development is exposed, not pristine release. No new organic rows were admitted. The previous v1 was rejected before training because identity target mass exceeded 5%; its compact audit remains.

The tokenizer/contract preflight gives 25 packed rows and **seven updates across three epochs**, 3,156 replay target exposures. The 64-update ceiling does not imply 64 updates will run. This small pilot can test learning/transfer, not establish broad English competence. Failure does not authorize more epochs or new data automatically.

## Validation and packaged artifacts

- 202 distinct targeted tests pass (`final-tests.log`): objective/masking, restart control flow, serving, contracts, capture, retention, packaging and controller adverse cases.
- Both integrated validate-only preflights pass. No optimizer ran.
- All 41 pre-existing frozen file hashes and 11 new curriculum hashes match. Sealed release content was not included in the packet.
- Runtime: `../../runs/ganesh-controller-v1/runtime-qualified-local.tar.gz`, SHA-256 `31d393da1a4cf9ffb663368adad7d1a7062b68068ae318bc8eb36d4f86ce354d`; 155 members, 30 adapter modules, extracted and verified.
- Data packet: `../../runs/ganesh-controller-v1/data-packet.tar.gz`, SHA-256 `3c19f919e81406fe8f1d68254afec0b66c7dde5db15f55ecdacdee5b7f6bf794`.
- Base10B and local default194 payloads verified; other selected weights retained. Current local default remains experimental and unaccepted.

## Approval and execution sequence

1. Obtain a new finite cap and reserve against a fresh SKU/region quote. Finalize one VM, one campaign, fixed absolute provider STOP and non-auto-delete recovery disk. No old retry request is reusable.
2. Verify input GCS backup readbacks, fresh inventory, access and image/runtime. Qualify real CUDA memory and decode throughput; the generator recomputes prefixes without a KV cache.
3. Qualify exact restart with aligned observations, actual optimizer input capture/replay, signal recovery, GCS restore, upload rejection and provider STOP before fit. Existing exact-restart mismatch remains unresolved. No no-resume exception or tolerance relaxation is approved.
4. Only after those receipts pass, run the bounded frozen fit (64 epochs AND 64 updates, LR multiplier .25, packing 1, batch 8192, seed 103). Review all milestone/best/last outputs with frozen per-turn budgets. Fit requires at least 23/24 complete sessions plus full semantic/action checks. It cannot authorize release.
5. Only after fit passes, run the seven-update curriculum pilot and review base/best/last English plus protected tool probes. Stop on regressions; two failed pilots force diagnosis/hold. No budget/epoch/GPU/retry escalation.
6. Stop/join writers; back up required checkpoints, optimizer state, raw outputs, journal and receipts; verify GCS readbacks before normal shutdown. The absolute provider STOP remains effective on backup failure, preserving disk for recovery. Keep selected weights available locally. Local reviews may finish after shutdown.

Generation budgets permit at most 318,528 generated tokens: 228,096 frozen fit/dev, 81,216 curriculum comparisons, 9,216 protected checks. This upper bound includes up to three broker actions per turn and the frozen development budget of 192 tokens. Price the actual decode, checkpoint, upload/readback and qualification workload, not only optimizer update time. No cost-to-completion guarantee is established locally.

## Remaining boundaries

GPU qualification, live backup/shutdown proof, measured end-to-end timing and approved cap remain blockers. Independent release review and local MPS acceptance are required before any promotion; this pilot contract explicitly denies release. Same-agent adverse review is not independent acceptance. No current model has passed English conversation acceptance, and no new identity weight embedding is claimed.
