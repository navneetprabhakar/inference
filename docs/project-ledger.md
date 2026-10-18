# Project ledger

Creator: Navneet Prabhakar

Updated: 19 October 2026

## Current state

- Objective: train a portable conversational SLM from random initialization.
- Current milestone: official OASST identity/partition join and held-out repair complete within audit scope; 23 previous train candidates quarantined, all 79 prior held-outs preserved. Public approvals remain zero; training trajectories still fail acceptance.
- Next implementation milestone: review the current packet at `data/official-split-audit-v1/pending-review.json`, calibrate English/privacy/quality gates and prepare production intake. Portability acceptance and separate teacher key/account/terms/category/budget readiness remain pending.
- Hardware validated: Apple M4 MLX GPU; Apple/Linux PyTorch CPU; NVIDIA T4 CUDA.
- Hardware/precision gates still open: accepted full-size training trajectories, reduced precision and sustained training.
- Spending: USD 10 cumulative authorized for CUDA validation in `executespecv1`; both tiny and full-size T4 jobs are finished and their VMs/disks/temporary firewalls are verified absent. Conservative planning allowances: USD 1 prior + USD 2 full-size = USD 3 total; these are not settled costs. No paid teacher calls or main pretraining; settled billing pending.
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
| 18 October 2026 | Loss accuracy / full-size NVIDIA validation | Validation scope complete; trajectory gate still failed | 96 passed / 5 skipped locally; 71 passed / 17 expected skips on T4; exact learned state and 2,048-context inference pass; opt-in accurate loss candidate fails trajectory criteria; see milestone-seven.md |
| 18 October 2026 | Tokenizer candidate / serialization foundation | Foundation complete; production selection open | 109 passed / 5 CUDA skips locally; train-only reviewed intake, disjoint IDs, assistant masks, integrity checks and comparison runner; both synthetic 16K/24K requests yield only 432 IDs; no public-data candidate trained; see milestone-eight.md |
| 18 October 2026 | Offline conversation teacher lifecycle | Foundation complete; live pilot open | 139 passed / 5 CUDA skips; provider request contract, durable cache, bounded journal and structured/executable validators; 30 handcrafted replays plus 30 cache hits; no real teacher calls or training approvals; see milestone-nine.md |
| 19 October 2026 | Official partitions / held-out repair | Audit scope complete; source review open | 148 passed / 5 CUDA skips; all 200 OASST sample trees joined to official identity projection; 23 prior train candidates now held out; 799/70/32 split; no public-data training; see milestone-ten.md |

## Decisions

- Sole project creator credit: Navneet Prabhakar. Technical source references and required third-party notices remain accurate.
- Every completed minor or major milestone receives a ledger update and cohesive commit/push to the private repository.
- Preserve meaningful milestone boundaries; do not push every intermediate edit.
- Teacher is required and configurable, initially GPT-6 Luna or GPT-5.6 Luna; offline data development only.
- Model-only checkpoints remain supported; training checkpoints now preserve optimizer/cursor/scheduler state. Tiny NVIDIA training migration and full-size exact state import/inference are validated; accepted full-size resumed-training trajectories and reduced precision remain unverified.
- CUDA evidence now includes full-size exact state import, learned-checkpoint context/inference and seven synthetic FP32 benchmark updates on T4. It does not establish accepted full-size continued-training trajectories, sustained throughput, reduced precision or optimized kernels.

- The milestone-three tiny-validation resources were deleted; Network Management was restored to disabled after deleting its temporary connectivity test. See the milestone-three cleanup report. The new full-size job has its own lifecycle and cleanup evidence.
- Column-major serialization failure was corrected by explicit row-major export; scalar shapes and logical values are covered by regression tests.

- Initial source probes: FineWeb-Edu, UltraChat, Dolly and complete OASST ready trees; sample bytes about 3.19 MB plus metadata. Raw data stays outside Git.
- All retained content remains unreviewed; the audit is not a source clearance or production data release. No new cloud spending or teacher calls.

- A human review request was presented in the app for `data/reviews/bootstrap-review.json`. It has 40 pending examples, four pending source reviews and no human attestation; selecting a response option does not approve records.
- Manual bootstrap release integrity is implemented; production-scale automated quality evidence and stratified human-audit release remain open.

- Full-size research numerical policy v1 failed independent validation and remains rejected; no tolerance changes followed those failures. The epsilon-1e-6 configuration is diagnostic, not a production choice.
- Both backends learn the 100-repeat synthetic fixture; endpoint weight drift is substantial (max per-tensor relative L2 29.94%). Exact import/export preserves 242,296,320 values, but does not establish trajectory equality.
- Recomputable duplicate probe arrays were retired after hash/evidence capture; checkpoints and provenance remain. No new cloud or teacher spending.

- Experimental stable loss improves analytic confident-target accuracy but fails existing tiny/full-size trajectory criteria; the legacy loss remains default, and loss version is stored with training recipes/checkpoints.
- Full-size cloud resources were deleted after checksum-verified result download; instance, auto-delete boot disk and temporary firewall were checked absent. See `reports/milestone-seven-cleanup.json`.
- A concrete portability acceptance proposal is pending review through an app input request. No existing failed gate is waived, and no paid training is authorized by the proposal.

- Tokenizer mechanics now use an optional pinned `tokenizers==0.22.2` runtime and ten disjoint structural IDs; the fixture byte serializer remains unchanged. Production selection, streaming intake, representative sampling, packed training and structured tool serialization remain open.
- The current sample-only public snapshot was refused by the tokenizer builder without output; zero public examples/sources are approved. No new cloud spending or paid teacher calls.

- Initial teacher API IDs are documented as `gpt-6-luna` and `gpt-5.6-luna`; account access, output-training rights/category review and paid teacher budget remain unverified. No API key is configured in the workspace environment.
- Live generation is disabled with zero budget. Current price/context registration requires revalidation after 25 October 2026. All teacher candidates remain ineligible for training until separate review/release; metadata checks do not verify prose truth/style/content.

- Current OASST mapping covers all 200 sampled roots against the pinned official identity projection; 191 upstream train and 9 validation trees. All 303 English paths retain mapping evidence. Full Parquet hashes/text equality and source approval are not claimed.
- The authoritative pending source/sample review target is now `data/official-split-audit-v1/pending-review.json` (40 examples/four sources, no approvals/attestation). The original packet is retained; current release guards reject unmapped OASST approvals and manual split overrides.
- Current mapped curation: 799 train / 70 validation / 32 test candidates. All 79 frozen hold-outs are preserved, and 23 OASST examples moved from local train to validation before any public-data training. No new cloud/teacher spending.

## Open gates

- [x] Portable optimizer, token-warmup scheduler and deterministic fixture-batch cursor.
- [x] Same-backend continuation and injected interrupted-save recovery tests.
- [x] Actual tiny-FP32 MLX/CUDA training-state round trip.
- [x] Full-size local instantiation, fixed-checkpoint context, exact state imports and synthetic learning checks.
- [x] Actual NVIDIA full-size exact-state import, learned-checkpoint 2,048-context inference and bounded reference training.
- [ ] Accepted full-size training trajectory portability; acceptance proposal pending review.
- [ ] Data audit, production tokenizer, and teacher integration.
- [x] Authorized GCP CUDA validation, limited to USD 10.
- [ ] Main pretraining and teacher-generation budgets.

## Ledger practice

Add dated entries when a milestone completes, a decision changes, or work is materially interrupted. Keep evidence and limitations together. Commit the ledger with the milestone; use Git history for commit identity. Verify push success against the remote before reporting synchronization.
