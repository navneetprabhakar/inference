# Resolution plan: repair measurement, then continue our own training

**Proposed, not approved. No training or model inference has restarted.** This is a bounded route to a better-evidenced checkpoint, not a promise of a working conversational model within a few hours. The plan deliberately includes further training and a final decision; it does not authorize an indefinite audit or TinyStories loop.

## Fixed starting point and scope

- Continue our own **15,191,712-parameter** model, step **2,889**, with **378,667,008 retained training targets**. SHA256: `1fc366363a74bf514aa22ea334a938253bf31e437d588e3e0a0c712557e47335`.
- No random restart, pretrained-weight import, architecture/vocabulary change, adapters, new download or data admission. The learned parameter count stays unchanged and below100M.
- Native MLX BF16 compute with FP32 masters/moments, microbatch16 × accumulation32, context256,131,072targets/update. Same AdamW, original clipping/decay settings, exact data stream, saved optimizer and RNG.
- The only experimental variable is learning-rate scheduling. The same future examples go to both training branches.
- **Pause for owner review after every phase.** Approval of one phase does not authorize the next. Existing English, conversation and tool gates remain separate.

## Execution phases

| Phase | Work | Expected time | Hard wall cap | Exit |
|---|---|---|---|---|
| R0 | Correct evaluator, verify both saved checkpoints, freeze and calibrate measurement |30–45min|45min|Report corrected baselines; stop for approval|
| R1 | Two equal-work training branches,33.55Mtargets each; choose an eligible checkpoint |2–2.5h|3h|Report both results, including loser; stop for approval|
| R2 | Continue selected branch for74.97Mtargets, with checkpoint and response reviews |2.25–2.75h|3h|Final checkpoint and go/no-go decision; stop even if passed|

Estimated execution across all phases: roughly **5–6hours**, excluding owner review waits. Sum of hard phase caps: **6h45m**. Each phase uses its own approval-bound clock, including setup, checks and reporting; no clock restarts. Source preparation is still required before any model-executing attempt. If preparation cannot fit the phase cap, stop and report rather than quietly extending it.

### R0 — establish trustworthy measurement

Implement a new evaluator version, preserving every old source, score, stop and attempt. Use one shared runner/scorer/clock schema, parameterized by phase; do not copy another set of nearly identical stage programs.

1. Tokenize complete prefix-plus-option strings, locate the actual continuation span, and sum only its conditional log probabilities. Verify all600existing candidates against intended text, prefix stability, lengths and score indexing. Add small independent CPU fixtures for causal masking, shifted targets, continuation-only loss and every clock/phase interface.
2. Re-evaluate own checkpoints at steps1745and2889 with corrected grammar/grounding, empty/shuffled-passage controls and unchanged fixed131,072-target loss. Independently verify FP32/native fixed NLL within the existing **0.02absolute tolerance**, plus checkpoint immutability. A coding failure is not a parity pass.
3. Freeze **40new development prefixes in20families**, two per family, plus **20grading anchors**:10clearly coherent,10with explicit entity/causal contradictions. Prefixes must fit96native tokens and96generated tokens within the256context. These are authored after observing failures and are explicitly development material, not a fresh independent acceptance set.
4. Freeze the rubric before new generation. Keep five0/1/2dimensions and the original binary rule. Clarify that coherent narrative development is allowed; failure to choose an implied solution is not automatically nonsense. Talking animals require no penalty when internally consistent. Preserve unfinished-final-sentence handling.
5. Generate40current-checkpoint baseline continuations, seal the primary review, then request **two independently shuffled Sol reviews**, each40baseline stories+20anchors. Require at least9/10positive and9/10negative anchors correct in each request; inter-review anchor kappa>=0.6; real-story binary repeat agreement>=85%; mean absolute total-score difference<=1/10.

**R0 passes only when the computation and measurement checks pass.** The current model need not pass a capability gate to enter a learning experiment. If grader calibration fails, classify the result inconclusive and stop; no automatic prompt revisions or paid retries. Repaired scores do not retroactively pass the historical failed gate.

### R1 — continue training through one controlled comparison

Two branches start independently from the same complete step2889state. Training runs **serially on one GPU**, preserving memory headroom. Each consumes the exact same next256updates: sequence offset1,479,168, with per-update input hashes checked across arms. No new warmup, optimizer reset or teacher corrections enter the training data.

| Branch | Updates / targets | Learning rate |
|---|---|---|
| A: reference continuation |256 /33,554,432|Original global-step schedule, starting0.0004995509721941322|
| B: cooldown hypothesis |256 /33,554,432|Linear decrease from the same first-update rate to0.00005on update256|

For B, local index `j=0..255`: `lr=start_lr+(0.00005-start_lr)*j/255`. This is an experiment, not a claim that decay is the proven fix.

- Save a full exact-reload checkpoint and fixed loss every **64updates**—approximately every13minutes. Record loss, gradient norms, throughput and resources. Independently check the saved endpoint against FP32.
- At both endpoints, score the corrected objective packet/controls and generate the same40new development continuations using frozen seeds, temperature0.7, top-p0.9and96-token windows. Preserve every full output.
- Seal primary reviews, then make two140-case Sol requests:40baseline+40A+40B+20anchors, with different blind permutations. Compare branches within each review; keep all raw ratings and disagreement.
- A branch is eligible only if NLL improves at least **0.01nats** from the corrected step2889baseline; grounding loses at most5/100; distinct grammar loses at most2/45; story mean loses at most0.25/10and incoherent-sentence rate rises at most10points versus baseline in each paired teacher review. It must also show **at least one behavioral gain**: grounding improves>=5/100, or paired story mean improves>=0.25/10in each teacher review. Lower loss alone cannot release R2. All calibration, correctness and resource checks must pass.
- If exactly one branch is eligible, select it. If both are eligible, choose B only when its NLL is at least0.01below A, while losing at most5grounding cases and2distinct grammar pairs relative to A. Otherwise keep A and label cooldown advantage **unproven**. If neither is eligible, stop; no R2.

This phase selects an optimization candidate; it does not certify English or conversation readiness, or establish a semantic advantage from loss alone.

Both branches end at step **3145**, each with **412,221,440retained targets**. Physical training work is **67,108,864targets**, but the chosen model retains only **33,554,432new targets**. The losing branch remains charged and preserved; its learning is not added to the selected checkpoint.

### R2 — one bounded continuation, then decide

After owner review and approval, restore the selected step3145checkpoint and train **572updates /74,973,184targets**. If A wins, continue its original schedule; if B wins, hold0.00005. Do not reheat or restart warmup. Preserve the optimizer, RNG and next data position.

Save and check every64updates and at the endpoint. End at step **3717 /487,194,624retained targets**. The last60updates after the final64-update boundary end at the cap; no rounding up.

Endpoint evaluation includes corrected grammar/grounding and controls, the original100story cases, and the40new probes. Seal primary reviews. Two blinded200-case Sol requests each contain100current original-packet stories+40current probes+40selected-R1probe outputs+20anchors, in different orders.

All development success criteria must pass:

- Fixed validation NLL improves at least **0.03nats** from the selected R1checkpoint.
- Original grammar>=75/100; distinct correct pairs>=max(36, selected-R1distinct correct).
- Corrected grounding>=max(50, min(100, R0step2889correct+10))/100, and intact passages beat both empty and shuffled controls by>=15percentage points.
- Original100story conservative intersection of primary and **both** teacher reviews>=20. Historical failed results remain unchanged.
- On40new paired probes, mean two-review total improves>=0.5/10from selected R1; a20-family,10,000-resample bootstrap with seed20261023has a95%lower bound above zero. This interval is a research diagnostic conditional on these reviewers, not independent-human certification.
- Primary/teacher binary kappa>=0.6on the original100cases, teacher repeat agreement>=85%, and anchor calibration passes. Undefined or inadequate agreement is inconclusive, not a pass.
- Degeneration<=5/100under the unchanged narrow rule. All correctness/resource checks pass.

**Stop even if successful.** These are prospective development criteria. They do not replace the formal English gate, establish broad-English generalization, or authorize conversation/tool training.

## Hard stops and recovery policy

- Finite losses, gradients, master weights and optimizer moments; exact CPU save/reload; unchanged source/data hashes; independent FP32/native NLL tolerance0.02.
- Abort if a periodic fixed NLL exceeds its phase-source NLL by0.10nats. During the first16updates abort on batch loss>2×phase-source NLL; afterward abort on3consecutive losses>1.5×first16mean. These are failure guards, not tuning triggers.
-12GiB GPU and process-tree RSS caps; at most512MiB added global swap from the preserved382.75MiB baseline; free disk>=60GiB; AC required; stop after60seconds of sustained critical thermal state. Reserve five minutes for final save/shutdown.
- One model-executing attempt per phase after source freeze. No automatic recovery, tolerance relaxation, extra updates, teacher substitution, prompt rescue, data switch or borrowing another phase's budget. Routine CPU preparation may iterate before model execution, within its clock allowance.
- A technical failure in either training arm stops the entire phase. Selecting the other completed arm is not an automatic recovery. The one-eligible-arm selection rule applies to measured learning outcomes after technically valid arms.
- Owner pause cancels active execution safely and preserves charged work/checkpoints. Approval waits between phases have no workers and are reported separately.

## New allowances — old budgets are not erased

| Phase | New processed-position cap | New Sol requests |
|---|---:|---:|
| R0 |2,000,000|2|
| R1 |72,000,000|2|
| R2 |82,000,000|2|
| Total |**156,000,000**|**6**|

Processed positions include full-prefix generation recomputation, validation, controls, reference checks and **both** training branches. Maximum new physical training targets:142,082,048. Maximum new targets retained by the selected model:108,527,616.

The closed legacy continuation ledger retains306,104,851positions and its original320Mcap. This proposal explicitly requests a **new** allowance beyond that closed experiment; it does not pretend the new training fits the old cap. Combined continuation/resolution ledger ceiling:462,104,851. Earlier feasibility/benchmark ledgers remain separately charged; this is not a lifetime-project total.

All4original Sol request slots remain consumed. New allowance: at most6requests, each<=240seconds,512KiBprompt UTF-8bytes and12,000observed output-plus-reasoning tokens; at most72,000new observed tokens. Combined original/resolution ceiling:10requests and100,828observed output-plus-reasoning tokens. Record input usage separately. Use provider-side output limits when available and halt further dispatch on a usage breach; post-response usage checks cannot prevent already incurred usage. No tools, retries, hidden model substitution or teacher text entering foundation training. Requested model remains `gpt-6-sol` through Codex CLI; record actual client version and available identity metadata.

Existing failed stops/clocks/charges remain untouched. The old plan states, **“A correctness, resource, quality or deadline stop is terminal.”** Each new phase therefore needs explicit approval of this exception, its scope and its limits. A plan file is not an execution receipt. All current training authority remains false.

## Route from this experiment to the actual goal

- **If R2 passes:** report development progress and prepare a separately approved foundation-to-conversation readiness decision. The formal English gate, or an explicitly approved replacement/exception, must be resolved first. A20%story pass floor alone is insufficient evidence for proper conversation.
- **Conversation:** a separate bounded SFT proposal must retokenize/re-review the existing curriculum, measure usable assistant targets, add coverage justified by measured failures, freeze genuinely separate family-heldout cases, and retain base regression tests. Sol is the teacher only under an approved new allowance. The older500-conversation pilot is not silently reused as fresh acceptance evidence.
- **Tools:** only after conversation acceptance, train/test tool selection, internal/MCP schemas, arguments, result grounding and permission behavior. MCP transport/execution belongs to the runtime; teacher-produced final answers cannot count as student competence.
- **If R2 fails or is inconclusive:** stop this resolution experiment. Preserve the15Mlineage and explicitly decline another automatic TinyStories extension. A new broad-data/architecture/compute proposal may be justified within100M, but this plan does not initialize it or claim that15M/100Mis mathematically incapable.

No working-conversation ETA is promised before the relevant gates and data counts exist. The next promised deliverables are a trustworthy baseline, an actual controlled training result and one bounded follow-up checkpoint.

Exact machine-readable limits: [plan.json](plan.json). Starting-state verification: [reference-snapshot.json](reference-snapshot.json). Evidence behind the design: [cause audit](../foundation-cause-audit-v1/REPORT.md).
