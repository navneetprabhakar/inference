# One-approval execution package: fresh narrative feasibility v1

Status: proposed, NOT approved. Owner: Navneet Prabhakar. Date: 21 October 2026, Asia/Kolkata.

The objective is to test whether one small model initialized from random weights learns coherent short English narratives within a fixed local budget. It is not a general-English, factual-knowledge, chat or tool-use launch. All initialization, loading and training remain blocked now. Approval of this exact package would authorize implementing and validating its controls, then automatically advancing through its stages only when their gates pass. There is no need for another approval between successful stages within these bounds.

This package replaces the incompatible architecture/mixture/budget proposal in FOUNDATION_DESIGN.md for this experiment only. ENGLISH_GATE.md remains the unfulfilled broader capability ambition. Its independent human-grading and multi-domain evidence requirements are not claimed satisfied by the narrower automated/assistant-graded research assessment here.

## 1. Freeze the inputs and scope

Use only `../fineweb-salvage-reviewed-v1/accepted-manifest.csv`, pinned by SHA256 in policy.json: 80,038 documents overall, 72,116 training documents. Existing-tokenizer counts: 15,317,518 training content tokens; 848,330 development; 831,587 test. Only 51 training records are FineWeb. All other FineWeb and all Cosmopedia remain excluded.

Retain all original splits, family IDs and text bytes. No acquisitions, synthetic training generation, teacher output, external model weights or cloud runs. Deterministic full-corpus passes without source oversampling: those 51 FineWeb records receive the same maximum three passes as every other document. No promise of a web-language capability from this tiny addition. Hash inputs and source code, record exact environment/backend versions and seed 42. Recheck family, exact and known near-overlap exclusions against frozen evaluation material before any model initialization. Newly discovered leakage stops preflight; do not silently repair a frozen release and continue.

## 2. Implement and prove the execution controls before opening training

The current hard block is implemented. The watchdogs and approval-scoped training path below are NOT yet implemented or validated. Implement them as the first approved stage, with pure synthetic-event tests that do not allocate model weights. Keep legacy entrypoints denied; expose only an experiment-scoped launcher that requires the specific owner approval receipt and pinned policy. No environment-variable bypass.

Test refusal for missing/mismatched approval, legacy checkpoint, changed data/tokenizer/config/code, split leakage, exhausted budget, missing heartbeat, NaN/Inf, invalid counters, checkpoint mismatch and every stop threshold. Fault-inject power/interruption bookkeeping and partial checkpoint publication. A failing control test blocks initialization. No claim that the application guard prevents arbitrary independently written programs; this controls the authorized launcher and its workers.

Use an independent supervisor with 10-second resource/heartbeat checks and process-group termination. Budget reservations must be persisted before updates, not merely counted after success. Recovery must not reset elapsed time or token/exposure accounting. Partial checkpoints cannot become resumable. At a forced kill, retain the last complete checkpoint and mark the failure; do not save half-updated state as valid.

## 3. Build the fresh tokenizer and sealed research evaluation

Fit one byte-level BPE with exactly 8,192 total IDs, including ten reserved controls, on a deterministic <=32 MiB training-only byte sample; no artificial FineWeb balancing. Never fit on dev/test. Re-encode all documents and report new exact content/EOS counts. This is authorized tokenizer fitting only after approval, not work already performed.

Require 10,000 fixed-string integrity cases to round-trip exactly, no unknown bytes/control-ID collisions/silent truncation, and explicit rejection of invalid Unicode. On 1,000 deterministic narrative development documents require median <=1.6 and p95 <=2.5 tokens per whitespace-delimited word, aggregate >=3 UTF-8 bytes/token. Report compression against old BPE, without treating a changed token count as new data. Failure stops; no automatic vocabulary replacement.

Before model updates, freeze development diagnostics and a separate final research set with distinct templates/entities/families. Construct and validate labels before viewing model outputs. Screen against the training corpus and existing protection families. Keep final files outside training paths and deny the trainer access. Automated scoring sees final items only at final evaluation. Because the same assistant prepares/reviews cases, call this a frozen research holdout, not independent human certification.

Use a fixed 200,000-target narrative dev-loss subset, at least 500 families; final loss uses all existing narrative test documents, at least 500,000 final-tokenizer targets and 500 families. If supply/integrity is insufficient, stop without lowering thresholds. Build training-only add-alpha unigram and modified-Kneser-Ney 5-gram reference baselines; freeze development-selected smoothing before the neural run. Validate baseline probabilities on toy distributions. Baseline fitting is included in the approved preparation work.

Freeze 200 grammar pairs (50 per subtype), 100 short narrative prefixes, and 100 passage-grounded four-choice items (50 explicit fact, 50 temporal/reference). Make separate development and final versions. Generate 80–120 words per prefix with temperature .7, top-p .9 and fixed per-item seeds; EOS before 40 words fails. No best-of selection or repairs. Full-continuation scoring for grammar/comprehension; match token lengths and balance alternatives before freezing. Also freeze 100 training-prefix and 100 matched heldout-prefix copying probes. These diagnostic training-prefix excerpts are never fed back as added training examples.

## 4. Validate computation, then initialize one candidate

Proposed candidate: **5,114,112 parameters**, calculated from existing configuration shapes without allocation. Four decoder blocks, width 256, SwiGLU intermediate 640, four attention heads/four KV heads, tied 8,192-token embeddings, RoPE theta 10,000, RMSNorm epsilon 1e-5, context 512, no linear biases/dropout. One random seed: 42. No old checkpoint or alternate model-size sweep.

Use FP32 MLX locally, with a tiny FP32 PyTorch CPU correctness reference. At most 20 toy optimizer updates, <=100,000 toy target tokens, <=30 minutes; toy/reference fixtures do not become candidates. Check target shifting, padding/EOS masks, causal and document boundaries, loss normalization over accumulation, tied embedding, optimizer math, checkpoint roundtrip and deterministic resume. Require all 40 frozen cases to pass; FP32 reference/save-reload/causal perturbation discrepancies <=1e-5 and toy-fit loss decrease >=50%. If these conservative tolerances are unsupported, stop and report; do not relax them in place.

Do not pack unrelated documents into one attention stream. Use independent padded sequences initially. For documents longer than 512, use contiguous segments with at most one predecessor context token at a boundary; never supervise the same target twice in a pass. All segments retain parent family/split/exposure IDs. Verify total predicted targets against original encodings plus EOS.

Batch: up to 8,192 supervised targets/update, accumulated over microbatches of up to four 512-position sequences. Permit reducing microbatch to two or one for capacity BEFORE pilot; preserve the target batch through accumulation. Tail batches may be smaller. Freeze actual batching before candidate updates; no runtime recipe switching.

AdamW: peak LR 2e-4, beta (.9,.95), epsilon 1e-8, matrix-only decay .1, global gradient clip 1.0 AFTER actual-target-normalized accumulation. Warm up over 250,000 predicted tokens, cosine decay to 2e-5 over the final declared cap. Persist schedule state and validate its arithmetic; existing legacy warmup-only code does not already implement this schedule.

## 5. Run the pilot; continue automatically only if it passes

Pilot: same candidate and future schedule, at most 2,000,000 real-data predicted targets and two active wall-clock hours, including pilot evaluations/checkpoints. No extra pilot tokens to chase a metric. Check dev loss at initialization, then 500k, 1M and 2M targets.

Continuation requires reaching 2M within two hours, all correctness/resource/stability checks passing, dev NLL at least 5% below initial NLL, and no two consecutive increases >5% above best prior dev NLL. Generation diagnostics must have no degeneration stop. Measure at least ten minutes of steady-state throughput after warmup. Project the remaining authorized updates plus 25% evaluation/checkpoint overhead to fit the remaining 36-hour active budget; otherwise stop. This is a feasibility gate, not proof of language understanding.

## 6. Continue within aggregate limits

The pilot is part of, not additional to, the total allowance. Stop at the first of:

- **48,000,000 real-data supervised targets**, counting content plus EOS under the new tokenizer;
- **three presentations of any original document's targets**, including retries/replayed work conservatively charged;
- **6,000 real-data optimizer updates**;
- **36 active hours** of candidate training, evaluation and checkpointing;
- **72 elapsed hours from approved execution start**, covering preparation and interruptions too.

Before initialization set the actual token cap to min(48M, three full eligible training passes including EOS). Check exact per-document/target ledgers; do not wrap indefinitely or duplicate short documents to fill a batch. A budget may stop the experiment below the pilot target. Token/update boundaries must be clipped before work; a hard-killed in-flight update remains charged. A frozen data-order seed defines each pass.

Evaluate the same dev-loss subset every 500k targets. Run the full development diagnostics and fixed train-loss sample every 2M; perform copying probes every 5M and at termination. No training decisions depend on final test results.

## 7. Automatic stop rules: stability and direction

These are conservative heuristics, not guarantees of convergence or desired behavior. They must be implemented and fault-tested in stage 2.

| Signal | Action |
|---|---|
| Any nonfinite loss, gradient, parameter or optimizer state | Stop before committing the update; no automatic rescue |
| Wrong hashes, unauthorized checkpoint, split/family leak, inconsistent token ledger, missing required metric | Fail closed immediately |
| After 100 updates, loss >2x previous 100-update median for five consecutive updates | Stop |
| After warmup, pre-clipping gradient norm >10x prior 100-update median for five consecutive updates | Stop; retain raw gradient diagnostics |
| Global parameter update norm / pre-update parameter norm >1% for three consecutive updates | Stop; protects against unstable steps even when clipping masks them |
| After pilot, dev NLL >5% worse than best at two consecutive checks | Stop and retain best checkpoint; do not continue from last |
| After pilot, no >=1% relative dev-NLL improvement over six consecutive 500k checkpoints | Stop for plateau; no LR/epoch extension |
| Training NLL improves >=5% while dev NLL worsens >=2% over the same last three full-diagnostic checkpoints | Stop for overfitting |
| At full dev checks, >=5/20 fixed smoke continuations have >20% repeated 4-grams or a sentence repeated >=3 times | Stop for collapse |
| Grammar or grounded accuracy drops >=10 percentage points from best on two consecutive full dev checks | Stop for behavioral regression |
| More than 5/100 train probes reproduce the full next 64 tokens, and exceed heldout copy rate by >5 percentage points | Stop for copying concern; preserve longest-match evidence |
| RSS >16 GiB for 30 seconds, RSS >18 GiB once, or swap growth >512 MiB versus pre-run baseline | Stop; no precision/architecture fallback |
| Free disk <20 GiB, worker heartbeat absent >120 seconds, thermal status serious/critical >60 seconds | Supervisor stops worker; unavailable required monitoring blocks launch |
| Any token/exposure/update/time cap or user stop | Stop and write final receipt |

A transient OS interruption may resume **once**, automatically, only from a complete checkpoint of this experiment with identical data/tokenizer/code/config and validated cumulative ledger. All counters continue; replay counts against the original allowance. A quality, correctness, resource, budget or acceptance stop is terminal and cannot use that resume permission. No automatic reseeding, LR reduction, data addition, precision change or retraining. Implementation fixes after candidate updates invalidate the candidate; another training attempt needs a new approval.

## 8. Preserve checkpoints and evaluate once

Save every 500k targets or 15 active minutes, plus before a clean stop. Atomic publication of weights, optimizer, RNG/data cursor, exposure ledger, policy/code/tokenizer hashes and checksums. Retain latest two complete checkpoints and one best-development checkpoint; reserve 4 GiB for states/temporary files. Keep logs/raw diagnostics even when pruning superseded checkpoints.

After a normal budget end or plateau, select the lowest-dev-NLL checkpoint that has no earlier integrity failure. No candidate comparison on final test. If divergence, leakage, copying, regression or other terminal failure occurred, mark the run failed; diagnostic evaluation cannot turn it into a pass.

Final **narrative research success** requires ALL of:

- Test NLL <=90% of the better frozen baseline; paired family-bootstrap 95% CI excludes zero improvement, 10,000 resamples. Report bits/byte too.
- Grammar >=180/200 and >=42/50 each subtype.
- Grounded completion >=75/100 and >=35/50 each subtype; >=15 percentage points better than both empty- and shuffled-passage controls.
- At least 80/100 continuations score >=8/10 across grammar, topical continuity, entity/reference, causal/temporal consistency and local coherence (0/1/2 each), with no zero or premise contradiction. Assistant grading of randomized outputs; report as a proxy, not two independent human graders.
- Repeated-4-gram failures <=5/100 and threefold repeated-sentence failures <=2/100; those also fail coherence.
- Train-prefix copying <=5/100 AND train-minus-heldout copying <=5 percentage points.
- Zero known cross-split exact/family/confirmed near matches; no test-driven tuning. Publish every raw output, error, denominator and interval.

A final gate failure ends the experiment. Do not retune against the same holdout, lower thresholds or proceed to chat training. Full ENGLISH_GATE.md remains unmet even if this narrower research gate passes.

## 9. Delivery and authority boundary

Deliver final exact data/exposure counts, tokenizer/model/config/code hashes, measured performance/resources, plots and raw loss/gradient histories, best checkpoint, all generated continuations, baseline comparisons, leakage/copy findings, termination reason and a pass/fail/inconclusive research assessment. Historical budget and exposure records stay intact.

One approval covers stages 1–9 and their conditional automatic transitions only. It does not cover cloud spending, downloads, additional source salvage, public release, broad English certification, conversations, tools, additional seeds/models, extra epochs or weakening any gate. Work remains local to this machine; no new external API expenditure is authorized. Stop and report when the bounds cannot be met.

Suggested approval text:

> I approve fresh-narrative-v1 as specified in restart/approval-v1/PLAN.md and policy.json: implement and verify its controls, fit the fresh tokenizer, initialize the single 5,114,112-parameter model from scratch, and run the gated local pilot, conditional continuation and final evaluation within all stated limits. No scope expansion or automatic rescue is authorized.

## Evidence behind the choice

The small architecture is an experimental resource decision, not a measured optimum. TinyStories research demonstrates that sub-10M models can learn coherent restricted stories, which supports trying a small candidate but does not guarantee this smaller local corpus will succeed: https://arxiv.org/abs/2305.07759 . Compute-optimal scaling research was conducted at much larger data/model scales; it does not certify a particular tokens-per-parameter ratio here: https://arxiv.org/abs/2203.15556 . The controlling evidence is the local audited corpus and the new experiment's measurements.
