# Project ledger

Creator: Navneet Prabhakar

Updated: 18 October 2026

## Current state

- Objective: train a portable conversational SLM from random initialization.
- Current milestone: full-size local numeric bring-up and diagnostics recorded; exact state import/inference pass, training-trajectory acceptance fails. Public approvals remain zero.
- Next implementation milestone: investigate full-size trajectory drift and full-size NVIDIA state/inference within the authorized validation budget; continue calibrated data gates while human review is pending.
- Hardware validated: Apple M4 MLX GPU; Apple/Linux PyTorch CPU; NVIDIA T4 CUDA.
- Hardware/precision gates still open: accepted full-size training trajectories, NVIDIA full-size checks, reduced precision and sustained training.
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
| 18 October 2026 | Bounded source audit and curation foundation | Complete within audit scope | 57 passed / 2 CUDA skips; 800 input records → 901 retained sample-only examples; pinned revisions, protected held-outs and deterministic shards; see milestone-four.md |
| 18 October 2026 | Bootstrap review/release contract | Complete within bootstrap scope | 63 passed / 2 CUDA skips; pending 40-example packet, source/content-bound review gates and checked train-only reader; no public approvals; see milestone-five.md |
| 18 October 2026 | Full-size local bring-up / drift diagnostics | Partial; training gate failed | 74 passed / 2 CUDA skips; 80,765,440 parameters; exact state import, 2,048-context checks and 100-update learning pass locally; trajectory comparisons fail; see milestone-six.md |

## Decisions

- Sole project creator credit: Navneet Prabhakar. Technical source references and required third-party notices remain accurate.
- Every completed minor or major milestone receives a ledger update and cohesive commit/push to the private repository.
- Preserve meaningful milestone boundaries; do not push every intermediate edit.
- Teacher is required and configurable, initially GPT-6 Luna or GPT-5.6 Luna; offline data development only.
- Model-only checkpoints remain supported; training checkpoints now preserve optimizer/cursor/scheduler state. Tiny NVIDIA migration is validated; full-size/reduced-precision migration remains unverified.
- CUDA evidence is limited to the tiny FP32 implementation on the tested T4; do not generalize it to the full model or optimized kernels.

- GCP validation resources are deleted; Network Management was restored to disabled after deleting its temporary connectivity test. See the cleanup report.
- Column-major serialization failure was corrected by explicit row-major export; scalar shapes and logical values are covered by regression tests.

- Initial source probes: FineWeb-Edu, UltraChat, Dolly and complete OASST ready trees; sample bytes about 3.19 MB plus metadata. Raw data stays outside Git.
- All retained content remains unreviewed; the audit is not a source clearance or production data release. No new cloud spending or teacher calls.

- A human review request was presented in the app for `data/reviews/bootstrap-review.json`. It has 40 pending examples, four pending source reviews and no human attestation; selecting a response option does not approve records.
- Manual bootstrap release integrity is implemented; production-scale automated quality evidence and stratified human-audit release remain open.

- Full-size research numerical policy v1 failed independent validation and remains rejected; no tolerance changes followed those failures. The epsilon-1e-6 configuration is diagnostic, not a production choice.
- Both backends learn the 100-repeat synthetic fixture; endpoint weight drift is substantial (max per-tensor relative L2 29.94%). Exact import/export preserves 242,296,320 values, but does not establish trajectory equality.
- Recomputable duplicate probe arrays were retired after hash/evidence capture; checkpoints and provenance remain. No new cloud or teacher spending.

## Open gates

- [x] Portable optimizer, token-warmup scheduler and deterministic fixture-batch cursor.
- [x] Same-backend continuation and injected interrupted-save recovery tests.
- [x] Actual tiny-FP32 MLX/CUDA training-state round trip.
- [x] Full-size local instantiation, fixed-checkpoint context, exact state imports and synthetic learning checks.
- [ ] Accepted full-size training trajectory portability and actual NVIDIA full-size validation.
- [ ] Data audit, production tokenizer, and teacher integration.
- [x] Authorized GCP CUDA validation, limited to USD 10.
- [ ] Main pretraining and teacher-generation budgets.

## Ledger practice

Add dated entries when a milestone completes, a decision changes, or work is materially interrupted. Keep evidence and limitations together. Commit the ledger with the milestone; use Git history for commit identity. Verify push success against the remote before reporting synchronization.
