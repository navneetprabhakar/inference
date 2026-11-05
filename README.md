# English conversation and tool calling from scratch

Updated 3 November 2026 (IST). This repository contains the restarted, laptop-first project: a 97,536,768-parameter English language model initialized with random weights, a fresh tokenizer, native MLX training, and offline tool-call evaluation. It is an experimental model, not a production assistant.

## Latest assessment and cleanup

[Recovery assessment and proposed plan](reports/recovery-assessment-v1/ASSESSMENT_AND_PLAN.html) reconstructs both failed improvement cycles, distinguishes verified defects from hypotheses, and gives gated alternatives with laptop ETAs. No new training was started.

The 3 November cleanup removed 100 failed/superseded weight and optimizer files totaling **49.16GB**, leaving approximately **95.7GiB free**. Ten useful student snapshots, both foundation optimizers, all datasets, raw outputs, reviews and STOP files remain. Historical references to deleted checkpoints now have explicit tombstones; consult the [cleanup ledger](reports/recovery-assessment-v1/cleanup-ledger.jsonl) before attempting recovery. All four UI model paths were preserved and verified.

## Direct weight-edit experiment

[Measured results and research](reports/weight-edit-experiment-v1/RESULTS.html): four fixed, no-gradient edits of checkpoint copies scored **3/40, 4/40, 3/40 and 2/40** complete development conversations versus unchanged V11 **4/40**. None met the refinement gate. On a fresh, once-only 40-conversation holdout, both V11 and the selected embedding/norm rollback scored **0/40** complete conversations. The edit was not promoted. All actual outputs and per-case assistant judgments are linked in the report; these are not independent human ratings. No training or cloud spending occurred.

## Current state

**The eight-hour improvement attempt missed its goal: the frozen 97.5M-parameter student passed 3/100 complete final conversations (25/200 correct turns). Training is permanently closed.** The user cap is 200M parameters. Compute remained on the laptop; GPT teachers used current-auth Codex CLI, with no other paid APIs or cloud compute. Electricity, developer time and subscription cost are not included in experiment spending.

[Final report](runs/eight-hour-improvement-v1/DELIVERY_REPORT.md) · [All 100 actual final conversations](runs/eight-hour-improvement-v1/ACTUAL_100_CONFIRMATION_CONVERSATIONS.md) · [Final metrics](runs/eight-hour-improvement-v1/FINAL_METRICS.json) · [Local test interface](http://127.0.0.1:18765).

Final tool performance: 8/14 exact calls, but only 1/14 complete conversations requiring a call. All six no-call decisions were respected, but only one complete abstention conversation passed. The student is runnable and remains unreliable; serving availability is not a quality claim.

- Hardware: Apple M4 MacBook Air, 24GB unified memory.
- Model: 12 layers, width 768, 16,384-token byte-level BPE vocabulary, 512-token context; FP32 master weights and BF16 compute.
- Pretraining: 100M-token pilot completed; a separate continuation reached 200M total and stopped. No 300M run. The current SFT lineage comes from the **100M-token pilot**, through the selected V2/V3 SFT checkpoints; it does not inherit the 200M continuation weights.
- Revised V2 SFT: two 5M-input-slot arms on the 100M base completed (LR 1e-5 and 3e-5). The two planned 200M-base arms did not run.
- V3 repair: two 2M-input-slot arms completed from the 100M + 5M SFT LR 3e-5 checkpoint. Development selection chose **repair-lr3-2m**.
- Penalty sweep: 1.2, 1.3, 1.4 and 1.5 evaluated on the same 550 development cases. Keep 1.2 under the predefined regression gates; stronger global penalties damage tool chains.

## Current strict conversation development

These are 40 frozen, text-disjoint two-turn development conversations with actual sequential student responses. All substantive turns must be correct, relevant and grounded for a conversation pass. Tool results and final answers are checked separately from JSON validity. Reviews are assistant judgments with per-case evidence, not independent human review. The separate frozen 100-conversation confirmation set was evaluated once after selection: 3/100 complete passes. It is now exposed and must not be reused as an untouched test.

| Candidate | Whole conversations | Correct turns | Complete tool conversations | Exact required calls |
|---|---:|---:|---:|---:|
| Immutable baseline | 0/40 | 2/80 | 0/10 | 1/8 |
| Goal v7, template-heavy | 2/40 | 7/80 | 1/10 | 1/8 |
| Goal v8, natural-dialogue mixture | 2/40 | 10/80 | 2/10 | 4/8 |
| Goal v9, token-weighted accumulation | 3/40 | 10/80 | 2/10 | 4/8 |
| Goal v10, higher LR | 2/40 | 8/80 | 2/10 | 2/8 |
| Goal v11, corrected menus | 4/40 | 10/80 | 3/10 | 5/8 |
| Goal v12, fresh foundation + 2M SFT | 0/40 | 4/80 | 0/10 | 1/8 |
| Goal v14, cleaner core | 3/40 | 8/80 | 3/10 | 4/8 |
| Goal v15, expanded clean data | 4/40 | 12/80 | 4/10 | 6/8 |
| Goal v16, frozen lower layers | 3/40 | 14/80 | 2/10 | 5/8 |
| Goal v17, permission repair | 4/40 | 12/80 | 4/10 | 6/8 |
| Goal v18, clean foundation + 1M SFT | 1/40 | 4/80 | 1/10 | 2/8 |
| Goal v18, continuation to 3M SFT | 2/40 | 12/80 | 2/10 | 4/8 |
| Goal v19, matched role-token reset | 1/40 | 7/80 | 1/10 | 2/8 |

These scores are inadequate for a working assistant. V11 is the current development best: **4/40 whole conversations, 10/80 turns, 3/10 complete tool conversations, 5/8 exact required calls and 2/2 required abstentions**. Only one of 30 prose conversations passed. A correct call does not imply a correct answer: V11 received 56 from a multiplication fixture but reported 61.

V10's matched higher-learning-rate trial regressed to 2/40 conversations. V12 started from the separately retained **200M-token pretrained foundation** and reached 2M new SFT input tokens; both its 1M and 2M evaluations scored 0/40. That lineage is closed. It does not change the 100M-pretraining lineage of the selected V11 reference.

A fresh semantic spot audit found material failures in older conversations labelled reviewed, including fabricated room-access claims and claiming to highlight an email. **All 2,145 legacy local-teacher records are now quarantined from future goal training.** Original data and review evidence remain preserved. Earlier review labels must not be treated as certification of correctness. V13 was stopped at 70,210 committed input tokens when this was discovered; its updates are not used by the next run.

V14 completed its cleaner-core stage but regressed to **3/40 conversations and 8/80 turns**. Removing its prose repetition penalty did not improve accuracy and increased repeated four-gram frequency. It was not promoted.

V15 completed its expanded clean-data stage: **4/40 conversations, 12/80 turns, 4/10 tool conversations and 6/8 exact calls**. It passes no complete prose conversations and attempts a forbidden tool call, so V11 remains the default reference; V15 is a separate tool candidate. Freezing the embedding/lower six layers in V16 reduced complete-conversation success to 3/40. V17 added 200 explicit no-tool and 120 missing-argument examples, but its first 1M-token stage still scored 4/40 with the forbidden-call failure intact.

The current cleaned corpus contains 4,397 episodes: 200 original assistant-authored dialogues, 577 reviewed GPT-teacher dialogues, 1,600 grounded QA episodes, 1,400 positive fixture episodes and 620 tool-boundary episodes. Context checks and 1,726 fixture replays pass; these checks do not certify naturalness or generalization. V18 tested this corpus from the original **200M-token pretrained foundation**, without the quarantined legacy teacher data used in the earlier V12 foundation trial. Its first 1M-input-token stage scored **1/40** complete conversations. Continuation to **3M total SFT input tokens** improved it to **2/40 conversations and 12/80 turns**, still below V11. It is closed and not promoted; the first-stage control checkpoint and final evidence are preserved.

Retrieving one training dialogue as an in-context example was rejected: V11 fell to 0/40 complete conversations and copied example facts into unrelated answers. This is not enabled in the interface. V19 reset four highly aligned role-token embeddings and otherwise matched V18. It also scored **1/40** complete conversations and was not promoted. The embedding separation persisted, but whole-conversation correctness did not improve; the geometric observation did not establish a practical fix.

A separate 12-conversation **training-corpus diagnostic** yielded 4/12 complete passes for V11, V18 and V19. All 12 examples were verified consumed by V18/V19; only 10 were verified consumed in V11's latest stage (four complete passes among those ten), with earlier-lineage exposure not established for the remaining two. Some responses were reproduced exactly while other consumed examples failed. These probe scores are not held-out accuracy or selection metrics.

V20 completed a bounded 1M-input-token exploratory mixture from V11: unchanged clean chat/tool data plus 2,000 screened, 128-target-token Wikipedia/textbook training segments. Raw-language replay accounts for a planned 15% of supervised targets and is separately counted from assistant targets. The initial FineWeb replay preparation was rejected after a sampled segment exposed drug-ad spam in garbled prose. A second preparation was superseded to filter bibliography/title-heavy chunks. The admitted replay is sampled for prose suitability, not exhaustively fact-checked. V20 scored **2/40 complete conversations and 11/80 turns**, with a tool-prohibition regression; it is closed and not promoted. V21 tested a dialogue-emphasized mixture from V11: 80% of target tokens from the 777 original/fresh reviewed dialogues, 20% from tools/boundaries, and no grounded-QA templates or raw-language replay. Its 1M-input-token stage scored **2/40 complete conversations and 11/80 turns**; it is closed without continuation. A single fixed 50/50 weight blend of retained V11/V15 (V22) scored **3/40 complete conversations and 11/80 turns** and was rejected. It added no parameters or gradient training. V21’s preserved early checkpoint (159k tokens) tied V11 at **4/40**, with 13/80 correct turns, but retained a tool-prohibition regression and fewer exact calls; it was not promoted. V11 remains the experimental default at 4/40; none of these scores establishes a usable assistant. V23 is a controlled lower-LR comparison against V21 (3e-6 instead of 1e-5), with the same data, order, seed, starting weights and initial 1M-token budget. It scored **1/40 complete conversations and 6/80 turns**, and is closed. V24 tested explicit readable role labels from the original 200M-token foundation, with 4,397 unchanged clean conversation records and an initial 1M-token budget. It scored **1/40 complete conversations and 6/80 turns** and is closed; the retained V11 interface is unchanged. V25 tested full-dialogue supervision from the same foundation, with the same examples, order and optimizer-update boundaries as V18. Context targets were counted separately from assistant targets. V25 scored **1/40 complete conversations and 5/80 turns**, with both abstention cases failing. It is closed. **Training is now permanently closed for this iteration**, and the frozen V11 checkpoint completed the once-only 100-conversation confirmation evaluation: **3/100 complete conversations and 25/200 correct turns**. No tuning or training followed confirmation.

The local interface at `http://127.0.0.1:18765` exposes V11 as an explicitly experimental development candidate. Actual HTTP tests verified a correct 9 × 4 tool call and answer 36, but a greeting was incoherent. GPU contention blocks requests safely while training/evaluation runs.

Evidence: [V11 report and actual outputs](runs/eight-hour-improvement-v11/STAGE_REPORT.md), [rejected fresh-foundation trial](runs/eight-hour-improvement-v12/STAGE_REPORT.md), [new semantic audit](runs/eight-hour-improvement-v1/natural-corpus-spot-audit-review.json), [cleaner-core manifest](data/eight-hour-clean-core-v1/manifest.json), [V14 results](runs/eight-hour-improvement-v14/STAGE_REPORT.md), [V15 plan](runs/eight-hour-improvement-v15/PLAN.json), [all best-candidate development conversations](runs/eight-hour-improvement-v1/BEST_DEVELOPMENT_CONVERSATIONS.md), [actual interface traces](runs/eight-hour-improvement-v1/ui-v11-real-smoke.json).

## Historical template-based results

V3 test release: 1,000 cases, selected model and two references on the same cases. Selection used development data only. This test set has now been inspected and must not be described as fresh for future tuning.

| Metric | Starting LR 3e-5 reference | Selected V3 repair |
|---|---:|---:|
| Single-tool full success | 14/200 | 122/200 |
| Tool-chain full success | 0/150 | 103/150 |
| Result-only exact answer | 99/150 | 135/150 |
| Grounded exact answer | 9/100 | 70/100 |
| Clarification accepted reference | 0/150 | 150/150 |
| Clarification canonical exact | 0/150 | 71/150 |
| Error canonical answer | 0/100 | 100/100 |
| No-tool canonical answer | 0/50 | 50/50 |
| Chat mean repeated four-gram fraction | 9.81% | 9.82% |
| Chat EOS termination | 83% | 79% |
| FineWeb perplexity | 59.71 | 57.38 |
| TinyStories perplexity | 6.92 | 6.39 |

Tool cases use synthetic, template-correlated offline fixtures. These numbers do not establish production tool reliability or broad English competence. Chat quality is not human-certified. Canonical and accepted-reference clarification scores measure different things.

| Development penalty | Chat repetition | Single-tool success | Chain success |
|---|---:|---:|---:|
| 1.2 | 9.45% | 56% | 74.67% |
| 1.3 | 2.06% | 55% | 72% |
| 1.4 | 0.39% | 55% | 69.33% |
| 1.5 | 0.01% | 54% | 48% |

Reducing repetition alone does not establish coherence. Some prompts request repetition; future scoring must distinguish legitimate repetition from loops.

## Historical author-only generation and review

**Current override: the older review missed substantive errors. All 2,145 retained local-teacher records from this source are quarantined from new goal training; see the current-state audit above. The following describes historical processing, not current quality certification.**

The user reduced the target to **2,500 total conversations**: 200 existing chat-assistant-authored records plus 2,300 local teacher outputs. The pretrained Qwen3-4B-Instruct-2507 4-bit teacher is separate from the below-1B student. All 13 outputs saved by the first local run are preserved. The old 10,000-target runner is blocked by its own STOP file.

The first local runner stopped after 20 malformed-envelope attempts at slot 13. The new runner gives an explicit JSON shape and can losslessly wrap an alternating string list with role/content fields; raw text and the normalization are recorded. No dialogue wording is changed by normalization.

A single model serves batched GPU generation, testing concurrency 4, 8, 16 and 32 with retained production outputs, then selecting the fastest observed safe batch size. This avoids multiple independent model copies competing for laptop memory. Timing calibration is not conversation-quality evaluation.

Generation finished at 2,500 records (200 chat-authored, 2,300 local teacher), using batch size 32. Status: `runs/local-author-v2/status.json`; log: `runs/local-author-v2/console.log`. The original `data/author-only-v2/conversations-2500.jsonl` and manifest are preserved. Every local output identifies its teacher, revision, batch seed and raw attempt.

The original corpus has now received a full per-record Codex CLI assistant review. The auditable ledger records 870 keeps, 1,475 repairs, and 155 exclusions (zero unreviewed); every decision was checked against the immutable source and includes a reason plus before/after content. The deterministic, separately stored projection has 2,345 records and SHA-256 `3c30fc0934544dfa929e3ed3aafc30a7fa6cfd45bc746c42f353689110a3b6ac`. This is **not** independent human certification or training approval. See [finalization evidence](reports/author-review-v1/finalization.json) and the [ledger](reports/author-review-v1/systematic-review-ledger.jsonl).

Candidate-level validation now tokenizes all 2,345 projected records with the actual student tokenizer, including all 1,475 repairs. It found one repaired 961-token context overflow (`local-author-v1-02099`) and source provenance records with missing explicit dataset/license labels; these are open gates, not silently repaired. The candidate has no full normalized duplicates, no exact/near held-out user-turn overlap, and one duplicate first-user group, retained as an audit finding. A versioned v3 suite has 120 assistant-authored development cases and 120 separately frozen confirmation cases across grounding, rewrite, constraints, follow-up, ambiguity, tool abstention, single calls, chains, result use, and errors. It is not an independent benchmark; confirmation is not used for selection. The legacy 12-case confirmation suite remains frozen and uninspected. The decoder follows actual tool emissions until a final answer or bounded turn limit and compares prose 1.2 vs 1.3 with tools fixed at 1.2. The authorized development-only host decode completed; confirmation was not opened. Manual review found semantic prose 2 pass / 9 partial / 77 fail at 1.2 and 2 / 8 / 78 at 1.3, while strict diagnostic 7/88 is not semantic accuracy. Tool outputs are identical across arms except timing; strict full success is 1/32 and semantic passes 2/32. Prose repetition fell from 11.75% to 4.56%, but correctness remains unacceptable. See the [output review](reports/author-review-v1/development-decoding-v2/OUTPUT_REVIEW.md), [readiness](runs/codex-corpus-review-v2/host-inference-readiness.json), [evaluation preparation](reports/author-review-v1/evaluation-preparation.json), and [derived validation](reports/author-review-v1/derived-candidate-validation.json).

[Revised generation protocol](reports/local-author-v2/PROTOCOL.html)

## Conversation-data pilot (31 October 2026)

A separate 1,000-candidate pilot contains 200 newly authored conversations and 800 curated local conversations. All fit the current context and passed encoding/held-out overlap screens. **Its quality gate failed; do not train or scale this corpus.** Assistant inspection held back 61 of 80 curated sample records for correctness, grounding, scope, style or verification issues. This is a stratified screening result, not a population error estimate or independent human review. An extended screen quarantined 83 records; the other 917 remain unapproved. No training runner uses this dataset.

- [Pilot audit, quality gate and samples](reports/conversations-v1/PILOT_REPORT.html)
- [All 200 authored candidates](reports/conversations-v1/AUTHORED_200.html)
- [Quality decision](reports/conversations-v1/quality-gate.json)

The next data step is stricter curation and replacement review, not automatic expansion to 10,000. Data remains local under `data/conversations-v1`; preparation and read-only verification scripts are under `scripts/`.

## Documentation and evidence

## Approved-next-three Stage 1 (prepared; not trained)

The authorized one-run experiment is prepared under `runs/approved-next-three-v1`. Its immutable training input is `data/approved-next-three-sft-v1`: the validated 2,345-record v2 projection appears exactly twice, plus 256 deterministic tool-replay records selected only from the existing `sft-v3` **train** split. Development and confirmation are excluded. Source attribution is preserved, but per-row output rights/license remain unknown; this is not a redistribution claim. The later read-only [scoring/training audit](reports/scoring-training-audit-v1/AUDIT.md) supersedes quality interpretation where it conflicts, while preserving these run artifacts as history.

The isolated runner enforces at most 1,000,000 non-padding input tokens, two candidate passes, and four active hours, with run-specific STOP, health guards, resumable provenance counters, no checkpoint pruning, and checkpoint hashes. `scripts/evaluate_approved_next_three_sft.py` uses fixed greedy decoding and blocks confirmation until a development selection artifact is frozen. See `runs/approved-next-three-v1/stage1-ready.json` for the exact host commands and hashes. Stage 1 did not train or decode a new candidate.

## Approved-next-three Stage 2 (blocked; baseline retained)

The one authorized SFT run stopped safely at 441,999 non-padding input tokens (220,283 supervised assistant tokens, 1,525 steps, 787.54 active seconds), before its 1M-token cap. On 2 November 2026, an auditable disk cleanup removed 59 unreferenced/redundant checkpoints (64.32 GiB) after preserving the initial checkpoint, the preceding distinct 434,525-token checkpoint, and the exact `latest.json` final checkpoint (including optimizer state). The baseline milestone is unchanged; no training was resumed or started. The loopback UI was then verified ready with 77.23 GiB free. See `runs/disk-cleanup-v1/manifest.json` and `result.json`.

The final partial checkpoint was evaluated once against the frozen baseline using identical greedy decoding, then confirmation was evaluated once after a development-only decision freeze. It is **not promotable**: development tool full success was 1/32 for both models, while exact call traces fell from 15/32 (baseline) to 5/32 (partial candidate). Confirmation tool full success was 0/32 for both. A later complete assistant reading of the saved development outputs found baseline 4 pass / 9 partial / 107 fail and partial candidate 9 / 8 / 103; it is not independent human review. Earlier `semantic-review` labels were heuristic categorization rather than semantic reading and are preserved only as superseded audit history. Keep `runs/sft-v3/repair-lr3/milestones/2000000` as the selected baseline. Full evidence: `runs/approved-next-three-v1/STAGE2_REPORT.md`, `semantic-correction-result.json`, and `stage2-result.json`. The [v1 audit](reports/scoring-training-audit-v1/AUDIT.md) records the documented cleanup chronology: the historical 62-checkpoint state preceded the authorized retention of three checkpoints, and it is not causal attribution for the tool-trace decline.

## Local inspection UI (Stage 3)

`scripts/local_ui.py` is a loopback-only browser interface for inspecting the frozen baseline and the clearly labelled non-promoted partial candidate. It keeps local conversation history, has reset/send/cancel controls, displays model provenance and limits, and shows a trace of actual model-emitted tool calls. Tool mode exposes only the existing deterministic calculate, conversion, weather, item lookup and notes fixtures; it cannot run shell commands, make network requests, or modify files.

### Local interface during the active goal

The interface is available at `http://127.0.0.1:18765`. The immutable baseline remains its default until a final experimental checkpoint is selected. Full tool-call/result history is retained across follow-ups, checkpoint hashes are checked before loading, and a shared GPU lock prevents UI inference during training or evaluation. A busy or resource-guard response is an explicit refusal to run inference, not a model answer.

Start it manually (from this repository) with:

```sh
../inference-archive-20261029/.venv/bin/python scripts/local_ui.py --port 18765
```

Then open `http://127.0.0.1:18765`. It binds only to loopback. The current server is a detached local Python process; do not assume a launch-daemon service is installed.

The15GiB disk guard remains enabled. Historical Stage3 inference was blocked at12.9GiB free; that historical limitation is not the current disk state. Goal cleanup removed unused optimizer files from closed rejected trials while preserving model weights and evaluation evidence. Current live state is in `runs/eight-hour-improvement-v1/progress.json` and `root-active-run.json`. An actual final selected-model UI smoke test is still required before delivery.

- [Current plan and constraints](PLAN.md)
- [Local operation, setup and recovery](LOCAL_RUN.md)
- [Completed pretraining continuation](CONTINUATION_RUN.md)
- [Architecture, data and evaluation](docs/ARCHITECTURE.md)
- [Experiment history and artifact map](docs/EXPERIMENTS.md)
- [V3 comparison and actual outputs](reports/sft-v3/experiment/REPORT.html)
- [Completed penalty comparison and actual outputs](reports/sft-v3/penalty-sweep-v1/REPORT.html)
- [V3 dataset readiness](reports/sft-v3/READINESS.html)

Top-level documents and docs/ describe the current project. Dated reports and configs are immutable experiment evidence, including failed or superseded approaches; their launch-time status fields are not live authorization.

## Setup and verification

Use Python 3.14 on Apple Silicon with Metal support:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Tests exercise small models and fixtures; they do not launch a training campaign. Existing measurements used `../inference-archive-20261029/.venv/bin/python` as a dependency environment only. Archived trainer code and model weights were not inherited.

Git contains code, configs and reports. Raw data, token arrays, checkpoints and runtime state are ignored and remain local. A clone alone cannot reproduce the reported generations without the matching local assets and hashes. See [the runbook](LOCAL_RUN.md) before invoking any preparation or training script.

## Restart boundary

The previous project is preserved on `codex/archive-before-scratch-20261029` at `309c9accdaf2bad074e16fe702e313049abc86f7`. Its ignored files remain in the sibling `inference-archive-20261029`; relocation evidence is in `reports/archive.json`. Historical reports are retained for provenance, not carried forward as current capabilities. No archive deletion or Git history rewrite is required.
