# Project ledger

Creator: Navneet Prabhakar

Updated: 19 October 2026

## Current state

- Objective: train a portable conversational SLM from random initialization.
- Current milestone: five synthetic local tools, typed decision framing, bounded host execution and verified tool-SFT intake complete within reference scope. Scripted controls pass; actual random students fail. No learned tool capability or MCP transport is claimed.
- Next implementation milestone: application-owned MCP transport/discovery mapping and executable timeout/error checks. In parallel, complete source/suite review, English/privacy/quality calibration, teacher rights/quality review and production tokenizer selection. CLI-only teacher; no API fallback.
- Hardware validated: Apple M4 MLX GPU; Apple/Linux PyTorch CPU; NVIDIA T4 CUDA.
- Hardware/precision gates still open: accepted full-size training trajectories, reduced precision and sustained training.
- Spending: USD 10 cumulative authorized for CUDA validation in `executespecv1`; all three T4 validation jobs are finished and their VMs/disks/temporary firewalls are verified absent. Conservative planning allowances: USD 1 tiny + USD 2 full-size + USD 2 current accumulated-state job = USD 5 total; these are not settled costs. No Platform teacher API calls or main pretraining; one real CLI teacher generation consumes account usage of unknown settled cost. Settled cloud billing pending.
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
| 19 October 2026 | Token shards / resumable data consumption | Reference path complete; production runs open | 166 passed / 6 CUDA skips; exact tested same-backend resume, tiny MLX/CPU round trip, EOS/SFT masks and 2.60M-position synthetic reader probe; no public-data training; see milestone-eleven.md |
| 19 October 2026 | CLI teacher pilot | Transport validated; training release open | 187 passed / 6 CUDA skips; one real GPT-5.6 Luna correction demonstration, three cache rechecks, two failed launch slots retained; no API calls or training approvals; see milestone-twelve.md |
| 19 October 2026 | Gradient accumulation / v2 update boundaries | Local reference path complete; NVIDIA accumulation open | 221 passed / 7 CUDA skips; native full-batch checks, tiny MLX/CPU migration, real historical v1 resume, and full 81M own-resume over 3 logical updates; no public-data training; see milestone-thirteen.md |
| 19 October 2026 | Actual NVIDIA accumulation / v2 state transport | Scoped validation complete; trajectory/quality gates unchanged | 222 passed / 7 skips locally; 187 passed / 29 expected skips on T4; tiny numerical round trip, full exact import/finite continuation/MLX return and CUDA own-resume; packaging failure retained/corrected; resources verified absent; see milestone-fourteen.md |

## Decisions

- Sole project creator credit: Navneet Prabhakar. Technical source references and required third-party notices remain accurate.
- Every completed minor or major milestone receives a ledger update and cohesive commit/push to the private repository.
- Preserve meaningful milestone boundaries; do not push every intermediate edit.
- Teacher is required and configurable, initially GPT-6 Luna or GPT-5.6 Luna. Active transport is Codex CLI with saved ChatGPT auth; generation stays offline from deployed inference, with no Platform API fallback.
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

- Initial teacher API IDs are documented as `gpt-6-luna` and `gpt-5.6-luna`. Historical API readiness was unverified at milestone nine; API keys remain unused. The subsequent CLI sign-in and one real GPT-5.6 Luna generation are verified. Account-specific training rights and quality/category review remain open.
- The historical API entry point remains disabled with zero configured budget. Current price/context registration requires revalidation after 25 October 2026. All teacher candidates remain ineligible for training until separate review/release; metadata checks do not verify prose truth/style/content.

- Current OASST mapping covers all 200 sampled roots against the pinned official identity projection; 191 upstream train and 9 validation trees. All 303 English paths retain mapping evidence. Full Parquet hashes/text equality and source approval are not claimed.
- The authoritative pending source/sample review target is now `data/official-split-audit-v1/pending-review.json` (40 examples/four sources, no approvals/attestation). The original packet is retained; current release guards reject unmapped OASST approvals and manual split overrides.
- Current mapped curation: 799 train / 70 validation / 32 test candidates. All 79 frozen hold-outs are preserved, and 23 OASST examples moved from local train to validation before any public-data training. No new cloud/teacher spending.

- Token shards use one-pass deterministic B1 batches with tokenizer/data hash binding and lazy numeric-shard verification. The current bootstrap release verifier still materializes its records; bulk release/intake, curricula and actual target-model data runs remain open. Gradient accumulation was added in milestone thirteen.
- Tiny own-trajectory resume passes exactly in the tested updates. Independent MLX controls showed up to 3.7253e-9 differences even without disk reading; original FP32 bounds and failed full-size gates are unchanged.
- The 2.60M-position temporary synthetic reader probe is data-only, with zero neural updates or real review approvals. It does not count as the planned 1M-token language pilot; no paid calls/cloud jobs were used.

- On 19 October, up to USD 1 was authorized for the proposed teacher API pilot; the follow-up instruction “use codex cli, dont use API” changed the active transport. API calls remain disabled. No API-dollar estimate is applied to CLI usage; no credit purchase/reset is authorized automatically.
- The active CLI pilot uses installed version 0.144.4 and selected GPT-5.6 Luna, present in the local model catalog. One real output passes structured checks but has no human/training approval. Reported usage: 11,088 input, 116 output and 35 reasoning-output tokens; counter overlap/settled cost are not inferred.
- Two initial CLI launches failed without retained outputs. One old journal remains halted; the other failed key was explicitly abandoned using observed terminal-process evidence, retaining its launch slot and forbidding replay. The current journal allows 19 slots plus one frozen historical slot, for 20 combined; three are consumed. No underlying HTTP retry count is claimed.
- Future CLI failures retain bounded private diagnostics. Metadata, usage and cached outputs are revalidated. One successful generation and three cache reads do not establish general conversation/style quality or teacher training rights. Gradient accumulation was subsequently implemented in milestone thirteen.

- Accumulation defaults to 1; configured groups sum gradients weighted by supervised targets and normalize before one global clipping/AdamW update. Learning-rate warmup counts all processed positions after each group. Short tails are consumed without drop/replay.
- New checkpoints use state v2 and explicitly bind accumulation, zero pending microbatches and independent optimizer-step/data-cursor counters. Historical v1 loads with accumulation 1; old readers require upgrading before reading v2. Dataset/curriculum changes on resume are not supported yet.
- Full-size MLX mechanics: 3 logical updates, 92 processed / 60 supervised positions; actual probe work is 5 updates / 136 processed positions with two continuations. Exact own-resume values pass; this is not independent or cross-backend acceptance, sustained timing or a language pilot. Peak RSS 4,985,421,824 bytes holds two trainer states; no new cloud/teacher calls or data approvals.

## Mixture validation — 19 October 2026

- Reference mixture foundation complete: 250 local tests passed / 8 CUDA skips; source-filtered reviewed preparation, finite weighted schedules, family/pass caps, per-record prepared-position exposure, path-independent hashes and accumulated resume. See milestone-fifteen.md and its test XML/mixture audit.
- Native repeated-ID MLX GPU gradient variability diagnosed; explicit dense embedding control passes tested local determinism/resume and the original golden100. Both native and dense fail an additional repeated-token 100-update MLX/CPU trajectory stress. First retained rerun failure: updates 64/65 respectively. Negative evidence retained, original bounds unchanged; dense remains opt-in and actual dense CUDA is unvalidated.
- Full 81M dense local own-resume probe: 92 logical / 136 actually executed processed positions, no language claims. Separate short timing probe: 10,240 timed positions in 7.381194s, allocator peak 4,674,112,660 bytes; not a sustained or controlled native/dense comparison.
- No public/teacher training or teacher/cloud call. Real source approvals remain zero; curriculum transitions and production tokenizer selection remain pending. CUDA planning allowances unchanged at USD 5 out of USD 10; settled costs unknown.

## Curriculum validation — 19 October 2026

- Reference curriculum mechanics complete: 286 local tests passed / 9 unavailable-CUDA skips. Exact own-resume at stage boundaries, separate manual optimizer control, independent analytic LR clocks, explicit replay/family caps, interruption/corruption refusal and tiny local MLX/CPU/MLX continuation. See milestone-sixteen.md and its evidence.
- Full 80,765,440-parameter local dense-mode probe preserves all 242,296,320 state values across exact own-resume and foundation → SFT continuation. Two logical updates / 100 processed / 80 supervised positions; three actually executed updates / 136 processed positions. Not language quality, actual NVIDIA evidence or a passed full-size cross-backend trajectory gate.
- Standard v1/v2 checkpoints remain supported by the ordinary trainer; v3 requires the curriculum trainer. No implicit plan append, legacy checkpoint migration or optimizer reset. Quality exit-gate orchestration remains separate from data-stage transitions.
- No public source approvals, teacher generation or cloud calls added. Existing numerical failures and dense production/CUDA gates remain open. CUDA planning allowances unchanged at USD 5 of USD 10; settled charges unknown.

## Language evaluation — 19 October 2026

- 316 local tests passed / 10 unavailable-CUDA skips. Raw cached greedy decoder, final-answer content-only reference NLL, exact-task scoring, bound human reviews, family/scenario denominators and baseline-aware stage screens. See milestone-seventeen.md and its evidence.
- 500 synthetic candidate cases cover 100 scenarios/ten template families and five style controls: 400 exact-format tasks, 100 human-reviewed open responses. Zero approvals/grades; the stage policy remains proposed. Case intervals are descriptive, not independent-sample reliability evidence.
- Actual random-weight controls reject: tiny 34,976 parameters, 0/400 exact tasks on 500 cases; full 80,765,440 parameters, 0/8 on a ten-case professional subset. All raw generations stop on invalid structural IDs. Reference scoring completes separately and is not task success. Zero training updates; no new teacher/cloud calls.
- Reserved evaluation IDs/exact contexts are refused in teacher training generation, reviewed train publication and verified train reads. Semantic overlap and historical prepared-token auditing remain open; no retrospective contamination guarantee.
- Previous source approvals remain zero and numerical failures remain failed. CUDA planning allowances remain USD 5 of USD 10, settled cost unknown. This milestone adds no actual NVIDIA validation or language-training pilot.

## Local tools and SFT framing — 19 October 2026

- Final local suite: 385 passed / 11 unavailable-CUDA skips. Five synthetic tool schemas/handlers, typed wire format, role-derived masks, portable token-shard v2 reader, explicit plain/tool filtering, bounded raw runtime and continued caller history. Plain token-shard v1 and existing training checkpoint versions remain readable.
- Seven scripted controls pass independent structured action/result/final-metadata checks; valid wrong-quantity and wrong-result controls fail semantics. Free-text truth/style are not automatically verified. Actual random 34,976-parameter MLX model fails all seven scenarios and executes zero tools. No model training occurs in the runtime audit; separate two-logical-update synthetic masked-training/resume tests cover mechanics.
- Initial full suite: 2 failed / 380 passed / 10 skipped, retained. New shard hashes changed batch order and exposed incidental tail-size assumptions. Updated fixtures guarantee short tails/different accumulation sizes and derive boundaries from declared counts; exact resume/independent rate checks and tolerances remain unchanged.
- Evidence: milestone-eighteen.md, final/initial XML, source-hashed tool audit and ignored local-tools-audit-v4 raw traces. Seven synthetic scenario families remain unreviewed and protected from exact train/teacher reuse.
- No actual NVIDIA typed-runtime validation, MCP calls, teacher generation or cloud jobs added. Public approvals remain zero, prior numerical failures remain failed and CUDA planning allowances remain USD 5 of USD 10; settled costs unknown.

## Open gates

- [x] Portable optimizer, token-warmup scheduler and deterministic fixture-batch cursor.
- [x] Same-backend continuation and injected interrupted-save recovery tests.
- [x] Actual tiny-FP32 MLX/CUDA training-state round trip.
- [x] Full-size local instantiation, fixed-checkpoint context, exact state imports and synthetic learning checks.
- [x] Actual NVIDIA full-size exact-state import, learned-checkpoint 2,048-context inference and bounded reference training.
- [ ] Accepted full-size training trajectory portability; acceptance proposal pending review.
- [ ] Data audit, production tokenizer, and teacher integration.
- [x] Authorized GCP CUDA validation, limited to USD 10.
- [ ] Main pretraining budget and sustained teacher-generation capacity/cost policy. Small CLI pilot authorized; account usage is not an enforceable dollar cap.

## Ledger practice

Add dated entries when a milestone completes, a decision changes, or work is materially interrupted. Keep evidence and limitations together. Commit the ledger with the milestone; use Git history for commit identity. Verify push success against the remote before reporting synchronization.

## Completed validation job — 19 October 2026

- `slm-accum-20261019`, project `executespecv1`, zone `us-central1-a`; one T4/n1-standard-4, no external IP/service account, 100 GiB auto-delete standard disk and 45-minute server deletion limit. Dedicated IAP SSH rule `slm-accum-iap-ssh`, VM and boot disk are deleted and verified absent after checksum-verified result retrieval; see milestone-fourteen-cleanup.json.
- USD 2 conservative job allowance, USD 5 cumulative out of USD 10 authorized; settled costs unknown. Source, dependency and fixture hashes are recorded in `reports/milestone-fourteen-input-manifest.json`. No public data or teacher outputs are included.

- Final cloud checks pass after preserving/fixing an initial archive omission of `scripts/audit-data.py`; corrected suite 187 passed / 29 expected skips, original 1-failure suite retained. No tests, numerical code or thresholds changed to fix packaging.
- Full v2 state import preserves 242,296,320 values on CUDA and again on MLX. The 7-microbatch chain ends on MLX at update 4/cursor 7, 122 processed/79 supervised positions. This finite mechanics chain is not an independent trajectory or language-quality evaluation.
- Matching short accumulation-2 timing probes: 10,240 timed positions, MLX 7.900121s and T4 9.306863s. Unfused paths include host checks, library versions differ, and measurements are not sustained production rates. No new teacher generation/public-data training; full trajectory acceptance remains open.
