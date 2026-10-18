# Project ledger

Creator: Navneet Prabhakar

Updated: 18 October 2026

## Current state

- Objective: train a portable conversational SLM from random initialization.
- Current milestone: repository setup and execution-goal update completed; next implementation work is training-state resume.
- Next implementation milestone: portable optimizer-state checkpoints and deterministic resume.
- Hardware validated: Apple M4, MLX Apple GPU, PyTorch CPU.
- Hardware not validated: NVIDIA CUDA.
- Spending: no paid teacher calls or cloud training jobs executed for this project.
- Repository: [navneetprabhakar/inference](https://github.com/navneetprabhakar/inference), verified private.
- Baseline branch: `main`. This ledger is committed with the initial project baseline; remote synchronization is verified after pushing.

## Milestone history

| Date | Milestone | Status | Evidence and limitations |
| --- | --- | --- | --- |
| 18 October 2026 | Architecture and data planning | Complete | Training plan, dataset plan, configurable conversation teacher requirement |
| 18 October 2026 | Tiny dual-backend prototype | Complete locally | 27 tests passed, 1 CUDA test skipped; 100-update numerical parity; see milestone-one.md |
| 18 October 2026 | Execution goal and repository setup | Complete | Private repository created and visibility verified; goal prompt, ledger, sole creator credit, and initial baseline prepared for milestone push |

## Decisions

- Sole project creator credit: Navneet Prabhakar. Technical source references and required third-party notices remain accurate.
- Every completed minor or major milestone receives a ledger update and cohesive commit/push to the private repository.
- Preserve meaningful milestone boundaries; do not push every intermediate edit.
- Teacher is required and configurable, initially GPT-6 Luna or GPT-5.6 Luna; offline data development only.
- Model-only serialization is not a training-resume checkpoint. Full state migration remains the next milestone.
- No claim of CUDA compatibility until validated on NVIDIA hardware.

## Open gates

- [ ] Portable optimizer, scheduler and deterministic data cursor.
- [ ] Same-backend interrupted-run and checkpoint recovery tests.
- [ ] Actual MLX/CUDA training-state round trip.
- [ ] Full-size architecture verification.
- [ ] Data audit, production tokenizer, and teacher integration.
- [ ] Training budget and authorized GCP execution.

## Ledger practice

Add dated entries when a milestone completes, a decision changes, or work is materially interrupted. Keep evidence and limitations together. Commit the ledger with the milestone; use Git history for commit identity. Verify push success against the remote before reporting synchronization.
