# Project ledger

Creator: Navneet Prabhakar

Updated: 18 October 2026

## Current state

- Objective: train a portable conversational SLM from random initialization.
- Current milestone: tiny FP32 cross-host verification complete; proceed with the data pipeline.
- Next implementation milestone: audited data pipeline and production tokenizer, followed by full-size architecture parity.
- Hardware validated: Apple M4 MLX GPU; Apple/Linux PyTorch CPU; NVIDIA T4 CUDA.
- Hardware/precision gates still open: full 81M model, reduced precision and sustained training.
- Spending: USD 10 authorized for a short CUDA validation job in `executespecv1`; one T4 validation VM used. No paid teacher calls or main pretraining. VM/disk/firewall deletion verified; conservative allowance below USD 1, settled billing pending.
- Repository: [navneetprabhakar/inference](https://github.com/navneetprabhakar/inference), verified private.
- Baseline branch: `main`. This ledger is committed with the initial project baseline; remote synchronization is verified after pushing.

## Milestone history

| Date | Milestone | Status | Evidence and limitations |
| --- | --- | --- | --- |
| 18 October 2026 | Architecture and data planning | Complete | Training plan, dataset plan, configurable conversation teacher requirement |
| 18 October 2026 | Tiny dual-backend prototype | Complete locally | 27 tests passed, 1 CUDA test skipped; 100-update numerical parity; see milestone-one.md |
| 18 October 2026 | Execution goal and repository setup | Complete | Private repository created and visibility verified; goal prompt, ledger, sole creator credit, and initial baseline prepared for milestone push |
| 18 October 2026 | Local training-state checkpoint and resume | Complete locally | 33 passed, 1 CUDA skipped; exact same-backend continuation; MLX/CPU cross-backend resume; see milestone-two.md |
| 18 October 2026 | Tiny cross-host and NVIDIA validation | Complete | 39 passed / 2 CUDA skips on Mac; 22 passed / 6 expected skips on T4; MLX/CUDA/MLX continuation and 100 CPU/CUDA updates; see milestone-three.md |

## Decisions

- Sole project creator credit: Navneet Prabhakar. Technical source references and required third-party notices remain accurate.
- Every completed minor or major milestone receives a ledger update and cohesive commit/push to the private repository.
- Preserve meaningful milestone boundaries; do not push every intermediate edit.
- Teacher is required and configurable, initially GPT-6 Luna or GPT-5.6 Luna; offline data development only.
- Model-only checkpoints remain supported; training checkpoints now preserve optimizer/cursor/scheduler state. Tiny NVIDIA migration is validated; full-size/reduced-precision migration remains unverified.
- CUDA evidence is limited to the tiny FP32 implementation on the tested T4; do not generalize it to the full model or optimized kernels.

- GCP validation resources are deleted; Network Management was restored to disabled after deleting its temporary connectivity test. See the cleanup report.
- Column-major serialization failure was corrected by explicit row-major export; scalar shapes and logical values are covered by regression tests.

## Open gates

- [x] Portable optimizer, token-warmup scheduler and deterministic fixture-batch cursor.
- [x] Same-backend continuation and injected interrupted-save recovery tests.
- [x] Actual tiny-FP32 MLX/CUDA training-state round trip.
- [ ] Full-size architecture verification.
- [ ] Data audit, production tokenizer, and teacher integration.
- [x] Authorized GCP CUDA validation, limited to USD 10.
- [ ] Main pretraining and teacher-generation budgets.

## Ledger practice

Add dated entries when a milestone completes, a decision changes, or work is materially interrupted. Keep evidence and limitations together. Commit the ledger with the milestone; use Git history for commit identity. Verify push success against the remote before reporting synchronization.
