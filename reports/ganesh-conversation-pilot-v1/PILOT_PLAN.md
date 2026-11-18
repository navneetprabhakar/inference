# Controlled Fit30 conversational pilot — local preparation, 18 November 2026

**Current decision: corpus review and offline experiment plan complete; VM remains off. Request a new $25 A100 cap only after the remaining runner/controller work passes local tests. This is not launch-ready today.** The proposed cap buys a bounded learning experiment, not a guaranteed conversational model. No old cap or failed campaign is reused.

## Reviewed data and actual baseline

| Set | Distinct conversations | User turns | Supervised target positions |
|---|---:|---:|---:|
| Broader training candidate | 70 | 218 | 2,286 |
| Narrow control | 33 | 99 | 1,128 |
| Development | 35 | 109 | 916 |

The broader set contains64 conversational scenarios: eight each for ordinary conversation, clarification, instructions, grounding, entity roles, corrections, memory and rewriting. Two identity scenarios teach Ganesh-base / Navneet Prabhakar without an answer-bearing system prompt. Four calculator lessons provide small, replay-verified tool coverage. The control is an exact33-row subset selected using only training target/length counts, never development/model scores. The shared identity/tool material has identical exposure in both arms.

Both no-call policy modes and tools-enabled/call are present. Every one of the105 distinct train/development trajectories (327 user turns) was reviewed by the Codex author; six actual tool calls were replayed. This is same-author semantic review, not independent human review. All new rows are labelled Codex-authored synthetic. No organic-source admission is claimed. Source-group splits were assigned before authoring; six close development siblings were reauthored during review. Related abstract skills are necessarily shared; this is development, not pristine release.

The data remains deliberately small:2,286 distinct-conversation target positions do not mean2,286 distinct token values or enough data for broad English. Replies span short exact answers and natural exchanges, with a maximum36 reference tokens; maximum training context672 tokens. There is no2K-saturation or4K-memory claim.

A new local MPS baseline was run on all35 development sessions and all109 planned turns were reviewed, including26 blocked turns. Fit30 passes **20/104 English turns and2/32 complete English sessions**. Identity0/3 turns; tool checks0/2, with no correct actual tool use.69/109 replies have completed native frames. Accepting a directive-style recall answer is a borderline judgment: stricter grading gives1/32 English sessions; preserve both counts when comparing near a decision boundary. No training occurred.

## Controlled question and exact exposure plan

Does broader scenario coverage improve generated conversation more than narrow replay, conditional on the same Fit30 initialization and recipe?

- Exact starting manifest: `70075d157bb3a1bfa96866b3a5737d41037f416ce54b961b2ed0d5f16aa13145`; local base10B ancestry was validated. Both arms independently warm-start identical weights and inherited optimizer state. Neither resumes the quality-stopped old run. Preserve its stopped guard state/evidence untouched.
- Each arm has **40 optimizer updates and9,144 supervised target exposures**, with exact target equality **at every corresponding update**, not just at run end. Family target mass, conversation exposures and turn counts also match at each block. See `exposure-plan.json` and `block-checks.json`.
- Four cycles each contain ten family blocks, shuffled with seed103+cycle. Broader rows occur four times each. The control repeats3–4 selected scenarios per English family, with at most20 exposures for any individual row; identity/tool rows occur four times. This is an explicit bounded replay proposal, not a silent relaxation of the current8-epoch production limit.
- Each block is one update, packed with buffer1 and microbatch1 into at most four2048-position rows. Remaining rows are fully ignored padding, so both arms use8,192 position slots/update. Padding contributes no targets; full conversations and end tokens are retained. Offline continuous versus1+restore+39 block tensors match exactly. This is a cursor/packing check, not GPU optimizer restart qualification.
- Keep tokenizer/native2K format, eager Muon, optimizer initialization policy and nominal8,192-position LR scaling fixed. LR multiplier remains0.25. Both arms use the same predeclared40-update LR/momentum clock. Do not change decoder penalty, EOS weighting, architecture or reset moments in one arm.
- Input position lengths still differ slightly; per-reply length distributions and lexical/task content cannot be identical when scenario coverage changes. Residuals are recorded. The experiment tests the proposed coverage mixture conditional on this parent and schedule; it does not establish diversity as the sole cause or Fit30 as the best initialization.

The old finite-epoch approach was rejected: naive2-versus6 epochs does not match targets, update counts or common tool/identity exposure. `existing-runner-schedule-audit.json` records that rejected prototype with its then-current input hashes. It is not the final schedule.

## Evaluation and prospective decisions

Use the frozen new development suite with96 tokens **per action**, greedy decoding and real generated histories. Never insert reference assistant answers or repair malformed outputs. English scoring excludes identity and tools. All blocked followups remain in denominators. Source and evaluation data must remain fixed after seeing this baseline.

- Observe aggregate and per-family **content-only CE** every5updates, separately from end-token loss. Persist their stop states across restart. Keep the5% relative regression tolerance / two consecutive strikes; no after-the-fact relaxation. Track end loss and premature/empty endings separately.
- Generate at baseline, update20 and final; also inspect each arm's best-loss and last checkpoint if different. At most seven distinct snapshots across both arms (one shared baseline plus midpoint/best/last per arm). Evaluate the existing eight-turn protected tool/no-call suite for each snapshot.
- **Primary comparison is matched update40** with both arms reaching9,144 targets. Comparing one arm's early best to the other's later endpoint is not an equal-exposure result. Early-stop evidence is retained, but cannot be relabelled a completed primary comparison.
- A provisional learning GO requires treatment improvement of at least four complete English sessions over its fixed baseline, improvement spanning at least three English families (including correction or memory), and at least three additional complete sessions versus the matched control. No family may lose more than one correct turn versus baseline. Require no persistent content regression, no new forbidden dispatch/false tool-success claim, and no loss on previously passing protected items. These are prospective pilot decision margins, not statistically validated release thresholds. Use conservative borderline adjudication consistently; disagreement at a boundary means HOLD.
- If both arms improve similarly, learning may be demonstrated but the coverage advantage is unproven. If only training examples improve, or complete-session performance does not improve, HOLD. Two failed arms force diagnosis. If shared failures dominate, inspect parent/state/objective/data before inferring that additional pretraining is necessary.
- No result here authorizes release or changes the serving default. Independent release evidence and selected-checkpoint MPS qualification remain separate. Keep existing local checkpoints available and HTTP off.

## Remaining implementation blockers — must precede allocation

1. Integrate the exact block replay plan into the mandatory trainer and controller with hash-bound arm identity, fixed update clock and per-block target checks. The current `nano_sft` finite-epoch path does **not** implement this plan. Do not approximate it with ordinary epoch flags.
2. Add/persist content-only development guards and the new block cursor through save/resume; preserve old stopped guards. Test wrong arm/plan/dataset, changed target totals, rollback, zero-target padding microbatches and restarted observation cadence. Offline packing checks do not substitute for these integration tests.
3. Bind the reviewed corpus, all split/review receipts, parent, tokenizer and new bounded replay limits into an executable quality contract. `admission.json` intentionally remains `training_admitted:false` until enforcement exists. No fake release suite or bypass of mandatory coverage.
4. Complete a fail-closed controller dry run covering one writer, budget/lease accounting, stage admission, best/last retention, GCS rejection and backup-failure disk preservation. Fresh price/inventory/input readbacks and a newly approved cap are then required.

## Minimum cap and time envelope

**Recommended minimum practical A100 cap: $25 incremental USD usage.** Calculated envelope **$22.11**; headroom approximately$2.89. This replaces the preliminary$20 estimate: adverse review found that enabled tool turns can generate two calls plus a final reply, so one action per turn was an unsafe budget assumption.

| Component | Planned allowance |
|---|---:|
| A10040 `a2-highgpu-1g` +200GiB balanced disk, up to196minutes | about$12.09 |
| 25% pricing/runtime accounting margin on that usage | about$3.02 |
| Seven-day stopped recovery-disk reserve | about$4.60 |
| Initial GCS month allowance | $0.80 |
| Downloads and operations allowance | $1.60 |
| Total modeled envelope | **$22.11** |

The stage envelope is195minutes:20 boot/input restore,15 changed-path GPU checks,24 both training arms including development CE,90 generated checks,25 backup/readback,21 scheduling/stop-observation reserve. Provider STOP is fixed at195minutes before launch; an external/guest fallback has at most one additional minute, accounted above. Do not rely on editing a running VM's deadline.

The historical A100 decoder measured at most0.021279seconds/token and15.67seconds/load. Counting **164,640 worst-case generated tokens**, multiplying decode time by1.5 and adding seven loads gives **89.41minutes**. This is a planning extrapolation, not a measurement of the new runner. Fresh timing must fit all remaining stages and backup reserve before the first update. If it does not, HOLD rather than reduce review, increase the cap or extend the VM.

A g2-standard-8 L4 costs less per hour. An illustrative seven-hour envelope is about$14.71, suggesting a$15 bounded attempt, but there is no measured completion envelope for this new plan on L4. It requires fresh memory/restart/throughput qualification and is not an automatic fallback. A100 is the better-supported estimate from retained measurements; neither capacity nor successful learning is guaranteed.

Prices checked18November2026, [Google accelerator VM pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized), [disk pricing](https://cloud.google.com/compute/disks-image-pricing) and [GCS pricing](https://cloud.google.com/storage/pricing). A100 machine$3.673385/hour; balanced disk$0.000136986/GiB-hour. Refresh the regional quote before any allocation. This is a USD usage estimate, not a fixed tax/FX invoice. GCS charges recur after the first-month allowance; retained sole-copy recovery disks must not be deleted to force a cap. Resolve recovery before the seven-day reserve expires.

## Cloud and retention guardrails

Read-only GCP inventory returned zero instances in executespecv1. No VM/disk/bucket was created, no training launched and no GCS writes were performed for this task.

After future approval, use at most one VM and one training writer, sequential arms with independent output roots. Keep corpus, runtime, controls and parent identities backed up before training. Save and hash-readback required best/last/recovery checkpoints and raw evidence; stop/join writers before normal shutdown. Keep selected weights locally. Failed backups prevent normal shutdown/cleanup, but the finite provider lease still stops compute with the non-auto-delete disk preserved. Observe scheduled provider STOP explicitly at closeout or retain the unresolved qualification status; do not call an ordinary API stop a provider-stop fault test.

No retries, extra epochs, GPU changes, decoder tuning, budgets or quality thresholds may expand automatically. Budget approval alone does not clear the local implementation blockers above.
