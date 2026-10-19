# Post-training conversation workflow

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

The actual second-iteration conversation will run **after the selected continuation completes and its terminal loss diagnostics are published**. The interview harness and comparative rubric are prepared now, without altering the live training implementation, data, optimizer or budget. No student interview or new conversation grade has occurred in this milestone.

Use the same initial greeting request, eight-turn / 64-new-token limits, raw greedy decoder and five 0–4 dimensions as iteration one: understanding, relevance, coherence, context/corrections and instruction following. Rate the complete conversation out of 20 and normalize to 100. Follow-ups are chosen after reading each actual reply. This is an adaptive development assessment; later prompts can differ, so compare overlapping tasks explicitly rather than claiming independent benchmark accuracy.

## Evidence boundaries

- **Require the terminal model.** A live run without a terminal report or a partial invocation is rejected before source/model allocation. Verify the selected plan, complete schedule, resume identity, physical counts, terminal events/checkpoint and bound terminal-score receipt. Reconstruct the frozen validation selection. The loaded model/tokenizer must match the verified model identity.
- **Assess failures too.** The interview does not require the foundation NLL smoke to pass. Refusing failed-loss models would bias the assessment. No partial checkpoint can substitute for the completed run.
- **Preserve actual history.** Accept only one user string per request. Append each raw model reply unchanged, including empty or failed content. Retain raw token IDs, stop reasons, timing and the exact context hash. The harness supplies no teacher, retrieval, tool execution, corrected assistant reply or fallback.
- **Retain generation errors.** A generation exception records its actual request, context binding and error, then stops without fabricating an assistant reply. Early input termination retains the partial transcript and cannot produce a completion record.
- **Separate transcript completion from grading.** Eight replies yield `assessment_pending:true`, not success. Direct grading still requires reading the full transcript and recording dimension/turn-specific evidence. Review remains delegated expert, human attestation false and training approval false.
- **Protect execution and artifacts.** Hold the existing exclusive execution lock throughout the interview. Refuse existing output; flush/fsync each turn. Greedy generation refuses context overflow without truncating prior history. Evaluation conversations are not admitted training targets.

The protocol keeps the first-iteration rubric bound by its exact file hash. Its critical budgets, first prompt, dimensions, anchors and aggregation cannot change unnoticed. Newly chosen follow-ups are development material; the earlier source checks do not prove global semantic decontamination for every future scenario.

## Actual preparation validation

**36 focused checks passed**, covering unchanged comparative protocol, raw failed-reply history, mutation isolation, user-only requests, exact turn cap, early EOF, generation-error recording, nonterminal rejection, terminal/selection integrity and persistent physical-budget reservations. Model responses in these tests are synthetic fixtures, not the trained student's answers.

An actual call against the live selected continuation refuses the missing terminal report before model/source allocation and creates no interview artifact. The specific live training process and update events were observed; every reference-source hash in its frozen logical plan still matches the current file. The preparation receipt contains that step/time snapshot. It is not a liveness guarantee for later times.

No new gradient positions, student generations, teacher calls, Platform API calls or cloud jobs are caused by interview preparation. Existing training continues within its frozen budget. The prior iteration's real conversation score remains **0/100**; second-iteration assessment is still pending. Full project goal active/incomplete.

Evidence: [protocol](../configs/iteration-two-conversation-assessment-v1.json), [preparation receipt](../reports/milestone-fifty-interview-preparation.json).

After verifying the actual terminal checkpoint and publishing its diagnostic receipt:

```sh
.venv/bin/python -m slm.eval.iteration_two_interview \
  --root data/iteration-two-experiment-v1 \
  --score reports/iteration-two-terminal-score.json \
  --selection reports/milestone-forty-nine-optimizer-selection.json \
  --freeze reports/milestone-forty-eight-experiment-freeze.json \
  --protocol configs/iteration-two-conversation-assessment-v1.json \
  --output data/iteration-two-conversation-assessment-v1
```

Supply one JSON line per turn: `{"user":"..."}`. Read the returned actual answer before choosing the next follow-up. At eight turns the process finishes without requiring a ninth request or input EOF. Then publish the transcript, direct score, limitations and failure-driven next steps before advancing.
