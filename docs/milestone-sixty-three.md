# Frozen SFT evaluation and actual optimizer screens

Creator: Navneet Prabhakar

Date: 19 October 2026

## Evaluation contract

The new separate `slm.eval.research_sft` orchestration freezes the actual 109 complete research-release validation dialogues before scoring or training. Group identities, source records, exact serialized tokens and assistant masks are retained. No test losses participate in optimizer selection. The original 64 source-balanced validation groups are retained unchanged as foundation-retention diagnostics. These source responses are diagnostic references, not verified factual gold.

The actual foundation baseline yields mean per-group assistant NLL **4.649042160139171** on the 109 dialogues and source-balanced foundation NLL **5.042327988892794** on the original 64 groups. Equal-group means intentionally differ from token-weighted training loss. Both models use the already frozen numerical conventions and original tokenizer.

## Rules fixed before observing screen losses

Each learning-rate screen must complete exactly 64 optimizer updates / 256 scheduled batches / 115,195 prediction positions. Rates are 1e-5 and 5e-5; no other recipe or data-order difference. A screen is eligible only if foundation-retention NLL is no more than 0.2 nats above the baseline. Choose the lowest eligible assistant NLL, preferring the lower rate when within 0.01 nats. If neither is eligible, stop continuation and assess the lower-rate screen; do not silently adjust the guard.

The selected screen resumes its exact recorded optimizer state to 475 updates / 1,900 batches / 800,130 logical SFT prediction positions. The shared execution contract caps both screens plus selected continuation at **915,325 physical prediction positions / 539 updates / three passes per group**. Existing successful synthetic preflight receipts are reused without rerunning those gradient probes. Failed or uncertain reservations remain charged.

Terminal primary diagnostics use a paired group bootstrap: 10,000 resamples, seed 20261019, percentile 95% interval. The diagnostic smoke requires mean improvement at least 0.1 nats and an interval lower bound above zero. It does not establish conversation, factuality, tool use, readiness or deployment quality. The complete terminal retention diagnostics remain visible even if worse.

## Actual conversation before another iteration

`slm.eval.research_sft_interview` is separately frozen before real gradients. The terminal interview requires the completed scored run, exact checkpoint/state counters, source/tokenizer binding and experiment-recorded checkpoint. It reuses the unchanged first-iteration protocol: eight adaptive turns, 64 generated tokens each, raw cached greedy decoding, identical initial prompt, and five dimensions scored 0–4 / normalized to 100.

Follow-ups are chosen after reading the actual preceding reply. Every raw generated answer, including errors, remains in subsequent history. No repaired assistant text or training use. Complete transcript, raw token IDs, stop reasons and actual timing are retained. Direct delegated judgments cite turns and record all task outcomes and limitations; `human_attestation:false`. Token and identity checks validate evidence integrity, not the correctness of subjective grades.

A completed iteration receives this conversation and score even if its NLL smoke fails. The raw assessment must be recorded before starting the next training iteration. Prior results remain 0/100 for the first foundation pilot and 5/100 / zero of eight tasks for the second foundation pilot; no new score is claimed before actual assessment.

## Validation and evidence

- 67 research evaluation/stage/release/transition checks pass. Separate 28 evaluation/conversation checks pass, including changed protocol/wrapper refusal and the existing raw-token/history/grading checks. Suites overlap; do not add them as unique coverage.
- `reports/milestone-sixty-three-evaluation-freeze.json` binds the immutable private experiment protocol, launch contract, conversation wrapper and actual baseline.
- Private `data/iteration-three-sft-experiment-v1` contains exact validation groups, baseline and subsequent execution evidence. Large datasets, model states and raw conversation artifacts remain ignored locally.
- Historical runtime files, stage plans and successful resource-probe source bytes remain unchanged. No cloud activity, teacher generation or paid calls are used.

## Execution status

Both screen outcomes, selected continuation and terminal conversation are pending at this initial freeze. The experiment is now launched locally; completion and quality must be established from the actual reports, not inferred from this document.
