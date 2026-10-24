# Broader curriculum: stopped by retention guard

The continuation was rejected at **update 100**. Earlier factual accuracy fell from **77/80 to 64/80**, below the frozen minimum of 69/80. No new checkpoint qualified for selection. Training stopped without a retry; the prior factual-binding checkpoint and original foundation remain unchanged.

## Measured outcomes

| Metric | Parent | Rejected update 100 |
| --- | ---: | ---: |
| Fresh synthetic broader answers correct+EOS | 0/80 | 37/80 |
| Fresh EOS endings | 80/80 | 80/80 |
| Fresh fully correct fact-change pairs | 0/24 | 8/24 |
| Familiar-template answers | 0/40 | 20/40 |
| Novel-template answers | 0/40 | 17/40 |
| Earlier factual retention correct+EOS | 77/80 | 64/80 |
| Original narrative NLL regression | +1.49% | +2.30% |

Original foundation NLL is 1.3430354408919811; parent NLL was 1.363068901002407; rejected NLL was 1.3738726079463959. The 5% ceiling stayed anchored to the original foundation. Numerical and narrative checks passed; factual retention failed.

| Fresh skill family | Rejected correct+EOS |
| --- | ---: |
| Complete location phrases | 8/8 |
| Full owner names | 0/8 |
| Exact printed times | 0/8 |
| Selecting facts among distractors | 4/8 |
| Three-turn updates, including acknowledgment | 8/24 |
| Answerability, present or missing owner | 4/8 |
| Clarification questions | 5/8 |
| Complete factual sentences | 8/8 |

Only **1/8 delayed final-location queries** was correct; the 8/24 family total does not establish reliable state tracking. Answerability was 4/4 on absent facts and 0/4 on supplied names; conditional answerability remains unpassed.

Post-stop inference on the already-exposed earlier broader bank produced **24/48 automatic passes, 23/48 manually valid answers**, versus the parent's earlier 13/48. One irrelevant question matched a keyword in the old rubric. Automatic evidence is preserved; the semantic tally subtracts the false positive. This bank did not select or rescue the checkpoint.

## What went wrong

The primary agent directly read all 80 rejected fresh answers, 80 retention answers, 40 development answers and 48 earlier broader answers. Fresh scores had no detected false positives; all five accepted fresh clarification questions were valid.

The retention loss was predominantly **instruction and output-format interference**, rather than complete loss of the underlying facts. Of 16 failed retention turns, eight returned a factually correct full sentence despite a color-only instruction; five returned correction fragments; two repeated stale colors; one answered the wrong attribute. Fifteen previously correct turns regressed and two previously wrong locations improved, giving a net decline of 13.

Rehearsal was 25% of examples, but only **581/4,699 = 12.36% of consumed assistant/EOS targets**. The single target-normalized SFT loss did not guarantee a 25% old-task loss weight. New full-sentence replies competed with older word-only replies without enough paired instruction contrasts. These are plausible mechanisms supported by outputs and accounting, not causal ablation results.

Eight skill families were introduced together. At the stop, only 538 distinct new conversations out of 2,592 had been consumed. Names and time strings remained wrong, often producing a repeated invented time. Longer training might change this, but would violate the frozen terminal stop. This experiment does not establish insufficient 15M or sub-100M capacity.

The proposed repair is to normalize old/new losses separately, explicitly weight retention, and consolidate paired instructions on identical facts before expanding further. See [next-run proposal](NEXT_RUN_PROPOSAL.md). It has not been executed.

## Scope and accounting

- Same 15,191,712 parameters and tokenizer. Parent SHA256: 62b83c558ac5d9b844494f7080c4a99e2a852c8a7dcbb90fcfec2eea997b2a3c. No imported weights, downloads, architecture changes or new teacher calls. Exact-answer drill data used a deterministic fact oracle.
- Prepared **2,592 new + 384 rehearsal = 2,976 conversations**, with **103,113 native content tokens / 15,333 assistant tokens / 19,053 assistant+EOS targets** per complete bank pass. These are templated skill examples, not a general English corpus. Task grammars and value dictionaries were inspected; exact oracle, duplicate, prefix, mask and context assertions passed before execution.
- Development: 32 conversations/40 turns. Fresh test: 64 conversations/80 turns. Entity/value combinations were held out across all training templates; test included a fourth unseen template. Values/entities appeared individually in training. Familiar/novel strata share combinations; only two test entities and four values per extraction field are represented. These are correlated synthetic probes, not an independent sealed benchmark.
- Old rehearsal remained training-only. The prior exposed 80-turn bank was a declared retention guard and was not added to training. Overlap assertions check exact conversations, not broad semantic independence.
- Frozen cap: 800 updates, 30 minutes, 12M student positions, 160k SFT target exposures, 1,638,400 replay targets, 5 GiB artifacts, 12 GiB RSS/GPU limits and 60 GiB disk floor. Checkpoints every 100 updates. Fresh AdamW, LR 2e-5, five warmup updates, clip 1, BF16 compute and FP32 masters/moments. Objective: 0.5 masked SFT CE + 0.5 narrative CE, normalized separately; six new and two rehearsal examples per batch.
- Consumed: **100 updates / 4,699 SFT targets / 204,800 narrative replay targets**. All remain charged; **zero new updates or exposures were retained** in an eligible child. Parent lineage remains 400 earlier SFT updates, 9,600 SFT targets and 819,200 replay targets. Original retained foundation exposures remain 412,221,440.
- Consumed SFT targets: 4,118 new + 581 rehearsal. Distinct consumed examples: 538 new + 149 rehearsal. Replay reused an existing training-only narrative bank; exposures are not new unique data or broad-foundation admission.
- Main execution and fallback assessment: **37.52 seconds, 756,039 positions**. Read-only diagnosis added 25,828 positions; **781,867 aggregate**, with 99.53 seconds elapsed from the original start when diagnosis finished. No extra training or clock reset occurred.
- Engine peak active/driver memory: 2,241,640,650 bytes (~2.09 GiB), not total laptop memory or process RSS. RSS was guarded at 12 GiB. Artifacts approximately 182 MiB.
- Independent FP32 numerical preflight passed: NLL difference 0.0148144, gradient relative L2 0.0237275, cosine 0.9997199. Masked-label and padding perturbations changed loss by zero. Parent and original hashes were verified again after work.
- Rejected child SHA256: 78c5213150ef5599dd0734db924b077c09c756ab43a6084b21f7ec8ada4d0cb3. Saved tensors matched in-memory parameters; diagnostic inference reloaded the hash-verified file. It remains local and is not promoted.

## Reading the artifacts

The exact main-run result.json final test and retention fields describe the **unchanged parent fallback**, since no new checkpoint passed the guard: 0/80 on the new broader bank and 77/80 retention. The parent was measured before training and again during fallback. These are not rejected-child results.

The rejected child's fresh bank was evaluated once, separately after the stop, in rejected-assessment.json. That is the source of the **37/80** diagnostic score. It cannot change selection or undo the stop. Audit PASS means evidence consistency, not model acceptance.

Evidence: [plan](plan.json), [data receipt](data-receipt.json), [main result](result.json), [rejected-child assessment](rejected-assessment.json), [manual review](manual-review.json), [audit](audit.json), [terminal stop](STOP.json), [decision](decision.json).

Exact preparation code contains held-out templates and remains local/ignored as prepare.py, hashed in freeze.json. Public runners consume private frozen banks. Raw data, held-out text, logs and weights remain local. Historical receipts and stops remain unchanged: D0 remains failed and R1/R2 remain unstarted. All workers for this experiment have exited.
