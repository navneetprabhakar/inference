# Foundation recovery — corrected run

- **Result: R0 passed; D0 failed; R1/R2 did not start.** Blanket approval was recorded and routine preparation fixes proceeded without further questions. Failed data gates ended the experiment.
- **Zero training updates and zero training targets.** All three own checkpoint hashes are unchanged; all workers are reaped. The model remains15,191,712parameters. No downloads, conversation SFT, tools training or new student initialization occurred.
- This is a measurement/data admission result, not evidence that a larger model is required or that the Mac cannot train it.

## R0: measurement passed, capability remains poor

| Check | Result |
|---|---:|
| Native BF16 versus independent saved-checkpoint FP32 maximum NLL difference |0.000233, limit0.02 |
| Teacher binary repeat agreement |95% |
| Teacher repeat total-score mean absolute difference |0.65/10, limit0.75 |
| Primary versus each teacher Cohen kappa |0.6491 /0.7917, minimum0.6 |
| Anchor classifications |40/40correct; four fixed anchors repeated across ten requests |
| Source selected prospectively |Own cooldown checkpoint, step3145 |
| Selected reference native NLL |1.3430354 |
| Selected reference new fact fixture |37/100 |
| Selected reference conservative coherent outputs |1/20 |

The exact prospective rule selected the source before any broader-domain loss evaluation. It does not certify English readiness. The primary read/sealed60sampled continuations before teacher dispatch;20previously reviewed step1745outputs were reused only after exact prefix/response/generated-token identity checks. Greedy outputs remained diagnostics.

Ten requested`gpt-6-sol`high-reasoning CLI requests used157,038input tokens (33,792cached),23,173output and16,203reasoning tokens: **39,376observed output-plus-reasoning**, within the approved304,000aggregate cap. Backend-resolved model identity is unavailable and is not asserted. No tools, model substitutions or paid retries were used.

## D0: measured candidates, no admitted release

The existing35,948-document repaired PressBooks candidate frame was scanned against both local source files (106,881raw occurrences). Native SentencePiece counts were recomputed; old65.09M M1-BPE counts were not converted by a ratio.

CPU development repaired concrete false exclusions before any fresh sample: brand-substring family detection on custom domains,`taxi`matching a tax filter, benign learning-objective mentions, bare figure labels, compound-word equals signs and supporting reference URLs. Each version and its provisional counts is preserved. No new corpus was substituted and the phase clock was never reset. Grant classes, semantic pass thresholds, model configuration and training budgets were unchanged.

| Final provisional domain | Native content tokens |
|---|---:|
| General educational exposition |8,403,643 |
| Self-contained procedural candidates |3,793,445 |
| Everyday explanatory candidates |1,460,204 |
| **Total after normalization/near retrieval/protected exclusions** |**13,657,292** |

The surviving frame has **15,764documents**,15,764BOS boundary positions and900conservative connected source-family components. These are **candidate counts, not usable/admitted counts**. Authorship share, rights exceptions and full release/split acceptance were not certified.

The10M-training floor requires at least1.5M everyday content tokens in training. The **entire** surviving everyday pool has only1,460,204: a minimum39,796-token shortfall even before holdouts and further quality exclusions. Its optimistic training-capacity upper bound is9,734,693content tokens. Actual feasible supply is lower after heldouts/family limits. Do not treat39,796as a sufficient acquisition target.

Near retrieval compared8,097candidate pairs, finding5,270Jaccard>=0.8edges;11exact normalized duplicate records were identified. Two protected matching records caused two connected families to be excluded. This uses64MinHash values and16bands, with exact Jaccard on retrieved candidates; it is not an exhaustive semantic duplicate guarantee. Protected sealed text was accessed only by the CPU leakage-screen process, never displayed to the primary or used for model evaluation/selection. Independent human custody remains uncertified.

The older398-record protocol and later391-record capture are **different frozen samples**, each400draws: only six text hashes overlap; their union is783, and zero mode/draw/source/hash assignments match. Both sets were excluded from the new fresh frame. Earlier counts/partial reviews were not merged into a fictitious completed admission review.

## Fresh semantic sample: definitive early failure

The final cohort was frozen, then50uniform documents and50native-content-token-weighted draws were selected once. All100were unique. Six uniform documents were read in full; the other94draws were not reviewed and never counted as passes. No filter repair or redraw followed.

- The first unit was Poe's poem`The Raven`: readable poetry, outside the required explanatory/procedural cohort. This is a scope failure, not a claim that poetry is bad English.
- A documentary-only unit repeated the same brief description twice and lacked the substantive media.
- A classroom-introduction unit repeated its whole prompt twice and supplied no self-contained exposition.
- Those three clear scope/context failures alone make48/50uniform passes impossible, even without the other holds. The full recorded six-review result is one pass/five failures or holds. Legal/ergonomic assertions were held rather than declared false; the typing document also had the wrong domain label.
- **No cohort pass rate or confidence interval is estimated from this early-stop audit.** The weighted sample and100nearest cross-split audit remain incomplete; no accepted split was materialized.

**New admitted documents:0. New admitted native broad content tokens:0.** The13.66M frame remains quarantined as a research candidate. Previously recorded local data remains unchanged.

Six prelaunch CPU fixtures and six terminal data-audit fixtures passed. This validates the recorded mechanics/stop, not corpus admission or model readiness.

## Accounting and next decision

- Current run student work:1,768,824reserved evaluation positions; prior aborted v2 work1,021,037remains charged. Combined2,789,861, with zero training targets. Closed prior continuation/resolution work plus both v2attempts totals378,874,312positions; these are not lifetime project totals.
- R0 took10.29minutes; D0 stopped after17.63minutes of its150-minute cap. Unused time/work is not borrowed for another training run.
- Peak supervised phase process-tree RSS:1.185GiB. Current-run storage:601.1MiB; free disk about127.6GiB. AC stayed available; observed global swap was below the original baseline. No resource stop occurred.
- The immediate blocker is **document-level data admission and composition**, not another TinyStories-only continuation. Future work needs a new source-bound candidate version that actually contains self-contained everyday explanations and instructions, full fresh review, resolved ancestry/grants and adequate heldout counts. No automatic larger model, new download or lowered quality threshold is scheduled.
- Blanket approval is preserved in[approval-receipt.json](approval-receipt.json). This experiment ends on its failed gates; no further overnight approval request is being made.

Machine-readable evidence:[report.json](report.json),[R0 decision](R0/result.json),[D0 decision](D0/result.json),[semantic reviews](D0/semantic-review.json),[terminal stop](STOP.json). Corpora, private sealed plaintext, weights, SQLite and raw CLI events stay local.
