# Approved successor completed — failed gate, training paused

The owner approved one 1,144-update continuation. It completed and stopped. **The model remains 15,191,712 parameters.** It added 149,946,368 training targets, ending at step 2,889 with 378,667,008 retained training targets. These are repeated target exposures, not newly admitted or unique corpus tokens. No conversation SFT, tool training, new model initialization, download or full reference run occurred.

## Results

| Development measure | Previous checkpoint | Current checkpoint | Required current result |
|---|---:|---:|---:|
| Fixed validation NLL, lower is better | 1.527115 | 1.400689 | Gain ≥0.10 nats — pass |
| Grammar, 100 rendered trials | 75 | 78 | ≥75 — pass |
| Grammar, 45 distinct pairs | 37 | 36 | Diagnostic; rendered gains do not generalize to distinct pairs |
| Grounded completion, 100 four-choice trials | 42 | 30 | ≥42 — fail |
| Primary coherent stories | 8 | 23 | Primary alone cannot pass |
| Sol coherent stories in this paired review | 4 | 5 | Teacher alone cannot pass |
| Primary ∩ Sol, same paired review | 4 | 4 | ≥20 — fail |
| Current conservative score vs published baseline | 3 published | 4 | Gain ≥10 points — fail |
| Narrow degeneration failures | 1 | 0 | ≤5 — pass |
| Generated BOS/document boundaries | 0 | 3 | Diagnostic; full windows retained |
| Independent saved-checkpoint FP32 parity | Passed previously | **Not verified: verifier failed** | All correctness checks pass — fail |

Validation NLL improved by 0.126427 nats (8.28%). This does not establish improved conversational reliability. The grounded score fell by 12 points; coherent paired results stayed flat. Common failures include self-addressed dialogue, objects changing identities or locations, lost problem statements, and nonsensical causal actions. Examples include bringing a kitten to itself, boarding a toy boat, washing bread in a washing machine, and eating an oven. No corrective examples were inserted into training.

The primary reviewed all 100 original full-window continuations before the teacher request. GPT-6 Sol was requested through Codex CLI once for 200 shuffled, checkpoint-blinded cases: 100 previous and 100 current. Same prior checkpoint: 14/100 in its earlier Sol review versus 4/100 in this paired regrade. **Absolute agent grades are unstable research judgments.** Historical results are preserved; the new regrade does not replace the published baseline or justify a capability claim. There are 20 narrative template families, not 100 independent task families. The formal English gate was not run or passed. Native corpus deduplication/leakage limitations remain unresolved.

## Checkpoint verification failure

Exact CPU serialization/reload of weights, optimizer moments, steps, cursor and RNG passed at the final save and all 11 periodic saves. The separate saved-checkpoint FP32/MPS verifier then failed **before its inference loop**:

`KeyError: 'stage3_deadline_epoch'`

The frozen verifier requests that key; the active clock contains `authorized_stage_deadline_epoch`. This is an implementation bug in the verifier, not an observed numerical parity failure. It should have been caught during preparation. It leaves independent parity unverified. No verifier edit, clock alias, tolerance change, automatic replay or extra attempt was made. The original failure log and one-attempt supervisor receipt are preserved. The independent approved teacher review was completed solely for reporting; no training resumed.

The metadata-only finalizer records the verifier failure as a failed correctness criterion. It does not waive the check or mark the stage successful. The frozen model/training sources and their hash manifest remain unchanged. Further execution needs a separate explicit approval; this run's authorization is consumed.

## Time, resources and accounting

- Worker training, including initial loading/compilation: **13,870.991 seconds / 231.2 minutes**. Update-clock duration: 13,806.513 seconds. Average including initialization: **10,810 targets/sec**; final 30 minutes: **10,499 targets/sec**. Final saved result includes subsequent evaluation. Final metrics were written about 238.2 minutes after approval, inside the five-hour cap.
- Peak supervised process-tree RSS: **1.473 GiB**. Additional global swap: **0 bytes**, using the unchanged original 382.75 MiB baseline. No resource guard breach; AC, disk and thermal monitoring remained active. All training, verifier and teacher workers are reaped.
- Current stage: **152,258,314 processed positions**, including 149,946,368 training targets, 11 fixed validation checks, final loss/grammar/grounding scoring and full-prefix autoregressive recomputation. The failed verifier entered no inference reservations. Prior charges: 153,846,537; original cumulative total: **306,104,851 / 320,000,000**. No budget was reset.
- Teacher: exactly **one** new request, completing the original **4/4** request allowance. New observed output plus reasoning: 8,848 tokens; cumulative **28,828 / 48,000**. Requested identity `gpt-6-sol`; backend-resolved model identity is not returned. Client `codex-cli 0.163.0-alpha.11.2`, tools disabled, no retry/substitution.
- All 50 token shards, tokenizer, fixed evaluation packet/validation array, original checkpoint and frozen training sources passed post-run hash checks. No data were newly admitted. Broader-source capture checks during the wait changed no active training inputs or usable counts.

Final checkpoint: `stage3-checkpoint.pt`, SHA256 `1fc366363a74bf514aa22ea334a938253bf31e437d588e3e0a0c712557e47335`. Checkpoint weights/optimizer, corpus payloads, virtual environments, SQLite accounting and raw event streams stay local and are excluded from Git.

## Decision

**Stop. Do not extend this TinyStories prototype automatically or begin conversation/tool training.** The bounded exposure hypothesis produced lower loss and no defensible semantic readiness gain. This experiment does not determine whether the broader goal is feasible below 100M parameters. It does demonstrate that another narrow narrative continuation is not an established path to that goal.

The broader path remains the one in [GOAL_PATH.md](GOAL_PATH.md): finish existing broad-English data admission, choose and benchmark a fixed architecture below 100M, then meet a justified foundation gate before conversation and tool stages. The 62.93M analytical candidate is uninitialized and unapproved. Nothing in this failed run releases another stage.

Evidence: [report.json](report.json), [primary review](primary-review.json), [paired teacher review](teacher-review.json), [blinding map](teacher-blind-map.json), [actual continuations](stage3-evaluation/stories.json), [option scores](stage3-evaluation/option-scores.json), [periodic checks](validation-history.json), [input integrity](post-integrity.json), [terminal stop](global-stop.json), and [approval receipt](approval.json). Failure traceback and raw runtime ledgers remain available locally.
