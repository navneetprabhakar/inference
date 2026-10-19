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
