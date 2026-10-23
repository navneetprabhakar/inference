# Second foundation stage complete — mandatory narrative gate failed

**Training is stopped. No further foundation stage, conversation SFT, correction training, or tool training is authorized.** The saved model remains our own 15,191,712-parameter foundation checkpoint; no public pretrained model weights were loaded.

## Measured results

This stage resumed step1173 with the original optimizer, schedule, cursor and RNG. It completed **572 updates / 74,973,184 new training targets**, ending at **step1745 / 228,720,640 total retained targets**. Cumulative continuation since step601 is 149,946,368 targets. These are target exposures, not unique usable corpus tokens.

| Frozen development measure | Previous checkpoint | Current checkpoint |
|---|---:|---:|
| Fixed validation NLL, 131,072 targets | 1.710346 | 1.527115 |
| Grammar, 100 rendered trials | 71 | 75 |
| Grammar, 45 distinct pairs ignoring answer order | 33 | 37 |
| Grounded four-choice completion, 100 cases | 27 | 42 |
| Primary narrative passes, 100 cases | 9 | 8 |
| GPT-6 Sol narrative passes, same blinded paired review | 5 | 14 |
| Primary + Sol conservative intersection | 3 | 3 |
| Generated document-boundary markers, 100 cases | 9 | 0 |

The previously published first-stage conservative score was 1/100 using Luna. It remains unchanged in the historical report. The paired Sol score above is a separate regrading of those same saved outputs, controlling for the teacher change without regenerating student responses or training on evaluation data. Student generation and full-window scoring stayed frozen. Current outputs contain zero BOS boundaries, so the earlier hidden-boundary limitation does not explain the current failure. Generated IDs and first-document text are saved for audit.

The primary agent read all 100 original prefixes and continuations, recorded per-case five-dimension scores and reasons, and sealed the review before dispatching Sol. GPT-6 Sol graded 200 shuffled cases (100 prior, 100 current) with checkpoint identities blinded, through one read-only Codex CLI request. Requested model was exactly `gpt-6-sol`; the CLI does not return a backend-resolved model identifier. No tools, corrections or student training were permitted in that request. Graders disagree substantially; these development judgments are not calibrated human measurements. Both individual current pass counts are below 20/100, so the progress-gate failure does not depend solely on taking their intersection.

## Mandatory +150 M progress gate

- **PASS:** fixed NLL improves at least 0.10 nats from the original step601 baseline. Actual gain: **0.840224 nats**.
- **FAIL:** at least 20/100 coherent continuations. Conservative result: **3/100** (primary 8, Sol 14).
- **FAIL:** at least ten percentage points of conservative coherence gain over the original 0/100 baseline. Actual gain: **3 points**.

All conditions were required. The gate failed; no remaining budget is released. Thresholds, sampler and acceptance conditions were not relaxed. Formal English acceptance has not been run or passed.

## What is going wrong

The optimizer is learning the TinyStories distribution: fixed loss fell by 0.183231 nats this stage, grammar improved slightly and grounded completion improved. That improvement has not produced reliable maintenance of entities, motives and physical events. Primary review found major causal/temporal failures in 64/100 cases, entity failures in 30, and local coherence failures in 36. One output triggered the frozen repetition criterion.

For example, a continuation about providing water to a thirsty bird contains **“Ben ate the pot.”** An open-gate/dog premise becomes a closed gate and contradictory bug descriptions. These are semantic failures despite readable surface prose. A successful example has a parent help repair a broken cup and the friend thank the child.

The observed behavior is consistent with an immature narrative foundation. This short learning curve does not establish whether more tokens alone will resolve it, and lower NLL is insufficient evidence to start conversation training. A read-only diagnosis of the failed behavior gate and training/data assumptions is the appropriate next decision point; further training needs a new explicit decision.

## Compute and correctness

- Training elapsed **113.6 minutes**; elapsed from this stage's recorded approval clock to finalized metrics **120.8 minutes**. The 3-hour stage cap and earlier overall clock were preserved.
- Average **11,002 targets/sec**; final 30 minutes **10,682 targets/sec**. One Mac GPU process, BF16 compute, FP32 master weights/moments, unchanged effective batch 131,072 targets and original schedule.
- Peak supervised process-tree RSS **1.48 GiB**; additional global swap **0 bytes**. No memory, power, thermal, disk, numerical or deadline stop occurred.
- Recoverable state saved every 100 updates and at the final checkpoint. Every save passed exact CPU reload checks for all FP32 weights, moments, steps, data cursor and RNG. Source checkpoint and all 50 token shards are unchanged.
- Independent PyTorch FP32/MPS validation of the saved updated checkpoint: NLL 1.526985 versus native BF16 1.527115; absolute difference **0.000131**, within unchanged 0.02 tolerance. No optimizer updates in this check.
- Current-stage aggregate work **75,974,410 processed positions**; prior 77,705,855 charged positions preserved; cumulative **153,680,265 / 320,000,000**. No clock, charge or swap-baseline reset.
- Teacher original-budget accounting: **3/4 requests**, **19,980/48,000 observed output-plus-reasoning tokens** across the corrected preflight and two checkpoints. The paired Sol request took 102.3 seconds. No retry or model substitution.
- All workers exited and were reaped. Historical first-stage hold remains preserved; the new hold records `MANDATORY_150M_NARRATIVE_PROGRESS_GATE_FAILED`.

Local checkpoint: `restart/foundation-stage2-v1/stage2-checkpoint.pt`  
SHA256: `8dc0f786499d08c670adfe53d55ddcf213ff6dcd07db5dca70835fd723fe3f69`

## Scope and limitations

This is a TinyStories development experiment. The 100 stories span 20 template families, not 100 independent families; grammar includes repeated pairs. Native-shard near-duplicate/family leakage remains unresolved. The existing 1,004,262,627 training corpus positions are not a claim of that many unique or fully audited usable tokens. No new broad-English data, SFT corpus or tool-call data was admitted. No acceptance threshold or original corpus-quality claim is upgraded by this run.

Evidence: [machine-readable report](report.json), [checkpoint receipt](stage2-checkpoint.json), [primary review](primary-review.json), [paired teacher review](teacher-review.json), [blinded mapping](teacher-blind-map.json), [teacher receipt](teacher-receipt.json), [raw continuations](stage2-evaluation/stories.json), [option scores](stage2-evaluation/option-scores.json), [FP32 check](serialized-reference.json), [final integrity](final-integrity.json), [contract](contract.json), [clock](clock.json), [terminal hold](global-stop.json).
