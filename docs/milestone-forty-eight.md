# Frozen second-iteration optimizer experiment

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

The local 81M foundation experiment is frozen and passes actual data preflight. Run **3e-4**, then **1e-3**, for **256 updates / 262,144 positions each**, from identical canonical random initialization and the same schedule prefix. Select by the predeclared source-balanced validation metric and continue only the selected checkpoint under its unchanged logical plan.

This milestone establishes a reproducible experiment, not a completed training iteration. At freeze, no second-iteration student update or model score had occurred. Runtime progress belongs to the actual run artifacts under `data/iteration-two-experiment-v1`; no liveness claim follows from a directory or reservation alone. The prior conversation result remains 0/100.

## Finite schedule and physical budget

| Bound or actual scheduled value | Positions |
| --- | ---: |
| Cumulative physical training ceiling | 10,485,760 |
| Each optimizer screen | 262,144 |
| Selected-chain ceiling, including its screen | 10,223,616 |
| Actual selected-chain schedule | 10,223,491 |
| Discarded screen plus actual selected chain | 10,485,635 |
| Unused physical-budget margin | 125 |
| Prepared positions touched once in selected chain | 7,796,611 |
| Repeated prepared positions in selected chain | 2,426,880 |

The schedule has **9,984 batches**, at most two exposures per prepared batch in the selected chain, and no implicit wraparound or partial-batch truncation. Its maximum group exposure is **28,305 positions**, below the 32,768 cap. All 25,339 records / 15,741 groups are touched. Prepared-position uniqueness includes shared message prefixes and is not lexical or semantic uniqueness.

The discarded screen is physical work even though its parameters are discarded. Across both separate model chains, a prepared batch can be used at most **three times**: twice in the selected chain plus once in the discarded trial. This does not describe three passes in one checkpoint. Both screen reservations remain consumed on failure; no third trial, replay update, automatic fresh restart or additional compute is budgeted. Any failure must be reconciled against actual events/checkpoints before revising the execution plan.

Source exposure in the selected schedule is measured from exact packed record spans: **7,081,373 OASST positions / 3,142,118 Dolly positions**. The stream is not equally balanced by token count. Validation gives each source equal weight; it does not change the training mixture.

## Version-two packed scheduling

The old scheduler explicitly requires a single source per component. The new source mix lives in one checked packed leaf, so a version-two contract explicitly permits a mixed-source **foundation** component. Version one retains its old requirement. The optional mode does not enable mixed-source SFT or bypass research admission.

All prior dataset/content/identity, pass, family and position checks remain. Version two additionally reports exact per-source processed, supervised and unique-prepared exposure and recomputes that accounting on read. Component weights control components, not the sources packed inside one component. The research trainer still sees one admitted foundation leaf; it does not gain curriculum/SFT/CUDA authorization.

## Frozen model, optimizer and evaluation

- **Model:** 80,765,440 parameters, 24 layers, width 512, 8 query / 2 KV heads, intermediate 1,536; new 16K tokenizer, configured maximum context 2,048, packed training context 1,024. Fresh canonical FP32 seed 20261019; no iteration-one embeddings or optimizer state.
- **Optimizer:** only learning rate changes. AdamW beta1 0.9 / beta2 0.95, epsilon 1e-8, decay 0.1, clip 1.0, 32,768-position warmup, one microbatch per update. Retain the existing dense-onehot embedding and legacy loss conventions to avoid confounding the learning-rate comparison. No architecture or numerical-gate change.
- **Validation:** 64 distinct groups, 32 per source, SHA-ranked after canonical row selection. Use complete conversations with at most 1,024 prediction positions and at least 16 assistant targets; reject oversized/short-supervision rows without truncation. No train-group overlap. No test-set model losses.
- **Selection:** lower equal-source mean of per-group full-foundation NLL wins. Choose 3e-4 if it is within 0.01 nats of 1e-3. Report assistant-target NLL separately; it cannot replace the primary metric after observing results.
- **Final smoke comparison:** reconstruct canonical initial weights and compare the same groups against the selected terminal checkpoint. Require finite foundation losses, mean improvement at least 0.1 nats and positive lower 95% source-stratified group-bootstrap bound: 10,000 draws, seed 20261019. Report assistant-target changes separately. No conversation/tool capability follows from passing NLL criteria.

Both specifications share the same data hash, initialization, architecture and all recipe fields except learning rate. Actual checked `Inputs` preflight succeeds for both. The first 256 scheduled batches are independently checked to contain exactly 262,144 processed and supervised positions. Protocol, selection, recipes, plans and implementation hashes are frozen before student scores.

The screen launcher holds an exclusive process lock for the whole run, persists an exclusive per-trial reservation before calling the trainer, refuses retries, and requires first-screen completion before launching the second. Trials run sequentially with 1,800-second soft invocation limits; the planned selected continuation has a 21,600-second soft limit. Wall checks occur at safe boundaries and are not hard time guarantees. Checkpoint every 128 updates, retaining two checkpoints per attempt.

The score verifier requires a complete canonical-random 256-update screen, exact counters, event coverage, unchanged frozen selection/plan and a verified terminal checkpoint before model scoring. It refuses partial, resumed, mismatched or nonfinite evidence. Its paired-bootstrap tests independently reproduce the declared sampling and preserve failed improvements.

## Validation and execution boundary

Final focused suite: **161 passed / three hardware-dependent skips**. The additional launcher reservation/lock suite passes **two** checks. Total across these final suites: **163 passed / three skips**. Checks cover mixed-source scope/accounting, old schedule regressions, source-balanced selection, real tiny CPU masked loss, optimizer tie-breaking, bootstrap reconstruction, invalid-terminal rejection, unchanged research limits, training/curriculum/restart mechanics and durable launch failure/concurrency handling. No actual NVIDIA validation is inferred.

Freeze construction completes actual full-source preflights and selects all 64 validation groups. The report records zero model updates/scores at freeze. Raw schedule, token arrays, protocol token IDs and checkpoints remain ignored outside Git. The committed receipt retains hashes, metadata, source exposure and limits.

Next launch the first frozen screen, observe its actual process handle and checkpoint evidence, then execute and score both trials. Resume the selected chain only after comparing verified complete screen results. After the completed training iteration, conduct the required actual conversation and publish direct scoring before advancing; separate conversation-SFT admission and the broader project requirements remain open.

No new teacher generation, Platform API call, cloud job, purchase/reset or spending authorization. Teacher reservations remain 17/20; conservative CUDA allowances remain USD 7/10 with settled costs unknown. Learned MLX/CUDA quality, production data/teacher rights, mature-content/styles/tools and later ESCI remain open. Full goal active/incomplete.

Evidence: [frozen experiment receipt](../reports/milestone-forty-eight-experiment-freeze.json).

```sh
# Refuses an existing experiment root; do not overwrite the frozen experiment.
.venv/bin/python scripts/freeze-iteration-two.py

# Execute once; failure retains the reservation and requires reconciliation.
.venv/bin/python scripts/launch-iteration-two-screen.py --trial lr-0003
.venv/bin/python scripts/launch-iteration-two-screen.py --trial lr-0010

# Only after that screen has completed successfully.
.venv/bin/python -m slm.eval.iteration_two_results \
  --root data/iteration-two-experiment-v1 --trial lr-0003 \
  --freeze reports/milestone-forty-eight-experiment-freeze.json \
  --output reports/iteration-two-lr-0003-score.json
```
