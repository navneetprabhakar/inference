# Fourth-iteration diagnostic and learning-control plan

Creator: Navneet Prabhakar

Date: 19 October 2026

## Starting decision

The completed 81M foundation-plus-SFT model scores **5/100 / zero of eight conversation tasks**, despite a passing NLL smoke. Another broad run with the same recipe has no demonstrated justification yet. Diagnose the gap with a small finite experiment first. This document is a plan, not a new launch contract or an extension of the exhausted experiment allowance.

The latest SFT model is the diagnostic starting point; preserve its exact checkpoint and existing failed conversation. Do not repair or train on the graded transcript, its answers, protected evaluation contexts or reserved evaluation families. The current 915,325-position /539-update experiment remains immutable and closed to additional gradients at its frozen ceiling.

## 1. Freeze fresh-session diagnostics before observing their outputs

Create and hash 16 distinct, short SFW evaluation scenarios and references, separate from admitted training records and the actual eight-turn transcript. Include explicit copying/format, correction/memory, simple quantities, negation and meaning-preserving style. Protect their contexts/families from subsequent training. Keep the original interview score unchanged.

Run each in a fresh session with greedy budgets of 64 and 256 tokens: at most **32 generations /5,120 generated tokens**. Record actual replies, stop reasons, repetition and direct task outcomes. For each reference, measure teacher-forced content/stop-token loss and conditional stop-token rank/probability; do not conflate forced likelihood with free-generation success. This can separate history-amplified failure from failure on a fresh request and expose whether merely extending the cap helps. It does not establish a root cause by itself.

This is local inference only, with no gradients or paid calls. Keep the endpoint and tokenizer/numerical conventions fixed. Do not retune decoding to inflate the prior score.

## 2. Review a small short-response learning control

Inspect up to 16 suitable existing admitted train dialogues in full, including exact assistant text, source identity, masks and message-end/EOS targets. Prefer whole conversations with short assistant turns and directly verifiable content; reject dubious examples individually. Existing bounded research admission does not imply that these were previously individually verified. Preserve original splits and exclude evaluation overlap.

Freeze train membership, exact references, a separate evaluation set, recipe, explicit optimizer-transition policy and total exposure before training. If there are too few suitable rows, report that and prepare an explicitly reviewed replacement source/teacher subset under the appropriate rights/category decision. Do not quietly merge unapproved teacher outputs or foundation rows.

## 3. Propose a finite memorization/control run before scaling

The proposed small control has ceilings of **65,536 additional physical prediction positions, 128 optimizer updates and eight passes per selected group**, whichever limit is reached first. Exact realized counts depend on the inspected subset and must be frozen before launch. A new explicit reviewed-subset admission/experiment contract is required: the existing policy allows only three passes per group and cannot authorize this proposal unchanged.

Carry all previous lineage and physical charges in the project ledger; a fresh output folder or contract must not disguise old exposure. Declare any fresh-optimizer transition rather than calling it a normal resume. Keep full-size architecture/tokenizer and numerical implementations fixed. Verify source import and preserve an exact zero-update baseline. Do not rerun full-size resource probes absent a changed workload or unresolved risk.

This is an overfitting control, not a conversation-quality milestone by itself. Freeze an exact teacher-forced/reference-generation/termination fitting criterion and stop rule after seeing the reviewed subset but before seeing its learned results. Report train fitting separately from fresh held-out task success. A control that cannot fit its small training set calls for a targeted objective/optimization/decoding investigation; fitting without held-out improvement calls for broader evidence/data rather than a capability claim.

## 4. Use the result to choose the next substantial iteration

If the basic control works but fresh requests still fail, measure the deficit against data breadth and foundation exposure before proposing a larger run. The current foundation has only about 10.22M logical training positions; insufficient pretraining is a hypothesis, not an experimentally isolated cause. Compare concrete corpus/source eligibility, short-turn coverage, token budget and expected runtime. Avoid multiplying epochs on the same corpus without a measured reason.

Required teacher integration remains open. Use the approved configurable Codex CLI teacher path only after its access/rights/category and finite usage gates are resolved; no Platform API fallback or automatic output admission. Preserve teacher/source lineage and protected evaluation separation.

The existing **$10 GCP authorization is validation-only**. Prepare a concrete costed proposal and obtain a separate main-training budget before paid cloud training. Local diagnostic/control preparation can proceed without that budget. Full-size MLX/CUDA resumed-quality acceptance remains a separate gate and cannot be inferred from local loss improvement.

## 5. Complete the same assessment cycle

At the end of the next meaningful training iteration, verify the terminal checkpoint, conduct the actual eight-turn raw-history conversation, publish direct rubric scores, failures and limitations, and update the ledger before another iteration. Retain the current 5/100 result regardless of subsequent outcomes. Broad styles/content settings, learned tool/MCP behavior and ESCI remain later capability gates.

## Measured update after fresh-session diagnostics

Milestone sixty-five completes the inference diagnostics before additional training. All 16 tasks fail with system/64, system/256 and bare-context/64. Conditional EOS-after-end is strong; longer generation and removal of the system message do not recover the tasks. Keep the original5/100 assessment unchanged. See `docs/milestone-sixty-five.md` for exact scopes and confounds.

The new 16-dialogue review yields only six considerations/344 prediction positions/188 assistant targets, without automatic admission. Reuse the already explicitly approved **12 train rows in `data/iteration-three-sft-review-v2/release` and its checked tokens** for the fitting control:1,417 prediction positions/851 assistant targets per pass. The earlier review excluded the specific interview strings mira, tara, apple, meeting, caveman and hello. Do not merge the six new considerations merely to enlarge this control.

Proposed concrete control before observing its baseline/learned results:

- Separate explicit **foundation-checkpoint branch**, not a resume of the completed noisy SFT model. Reuse the existing verified foundation-to-SFT transition, preserving exact random-origin foundation weights and declaring fresh AdamW for the objective change. Preserve the completed SFT endpoint independently.
- Eight deterministic complete passes through the 12already approved train groups: **96 microbatches /11,336 prediction positions /6,808 assistant targets**. Accumulation one gives96 optimizer updates and eight passes/group, within the existing proposed ceilings. No arbitrary increase of the repeat cap or new source-reader implementation is needed.
- Freeze a single recipe before model scores: peak LR 3e-4, accumulation one,1,024-position warmup, unchanged beta/epsilon/decay/clipping/FP32/dense-onehot/legacy loss conventions. No learning-rate sweep or extra attempts under the same allowance.
- Bind source/release/tokenizer/state identities and immutable execution location; precharge the full finite attempt before gradients. Keep actual versus conservatively reserved counts distinct on failure. Verify the zero-update exact import and reuse the existing larger full-step resource evidence; no workload expansion.
- Proposed fitting criterion: final masked train NLL at most 0.5 nats, at least 10 of 12exact source-final-reference generations and learned termination on at least 10 of 12 at budget 256. Earlier assistant source turns, where present, are supplied training context, not generated history. Freeze final exact criteria before launching; fitting proves only memorization/optimization on this subset.
- Measure the same fixed train references and four original validation groups before/after. Keep held-out reference NLL separate from generation; no test rows for recipe decisions. Assess the completed control with the required actual eight-turn raw-history interview and direct rubric before advancing. Any improvement over the source foundation branch is separate from a causal comparison to the completed SFT model.

This proposal is not yet a launch contract. The old950-row risk-admission policy/current915,325-position contract stays immutable. A new explicit reviewed-data control contract must record all earlier physical exposure/lineage and the additional11,336-position reservation; a new folder cannot disguise previous work. Main paid cloud training remains unauthorized under the validation-only budget.

The existing control release and all 12 prepared batches reopen successfully after the diagnostic: release manifest 03f0792e14c63fb5000b86a8662946bb1e9ea32075c6a927487f712e8fcec14b; token manifest 2784eb4e4d992a8c3b4407622896e1a8207652c1f292d6e7218f36b91ae432ab; actual maximum prediction length 222. All 12 complete dialogues were reread. References remain source targets for a fitting control, not newly certified factual gold. The original proposed admission requirement concerned a new subset of the 950-row risk corpus; this measured update reuses the existing explicit-row admission and requires a new bounded execution contract. It does not revise the old risk policy or admit the six new considerations.

## Actual control outcome and next decision

Milestone sixty-six executes the fixed 96-update control, preserving the exact source import and eight-pass exposure. Train NLL falls 4.158103 to 0.173769, but exact references are only 5/12, below the frozen 10/12 threshold. Learned stops reach 10/12. Four-group validation NLL worsens 4.880884 to 5.852833. The required actual interview scores 10/100 for grammatical sentences only, with 0/8 tasks solved. This foundation-derived branch is not promoted over the separate prior SFT checkpoint.

The first wrong canonical token in every nonexact reply is also preferred by uncached prefix inference. This targeted investigation finds no obvious cache-only cause; it does not prove universal cache parity or identify a training cause. The failed fitting criterion remains failed. Do not chase the threshold by silently extending replay or relabeling token agreement as conversation success.

Next preparation must address the actual gap: broader English/generalization evidence, training exposure/optimization and required teacher-conditioned instruction/style data. Prepare a concrete costed main-learning proposal before requesting or using paid training funds. In parallel, inspect the accepted Option-A contract and conservative GCP ledger, then freeze the pending actual MLX/CUDA quality comparison within the existing validation authorization if funds and scope permit. The retained learned step-64 checkpoint offers a possible same-state continuation comparison inside the original 96-batch data stream; any replayed validation work needs its own explicit physical accounting and must not reset the closed control budget or claim broad conversation competence.

No next training starts until the completed control assessment and this failure-driven decision are recorded. Existing teacher restrictions and original full English/style/content/tool/MCP/ESCI objective remain unchanged.
