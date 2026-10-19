# Conversation evidence and score publication

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

Prepare the verification/publication step for the required direct conversation assessment while the frozen training run continues. This module **does not judge response quality**. After reading the actual full interview, supply explicit five-dimension grades, per-turn judgments, evidence references and limitations; it checks the transcript and aggregates the declared scores.

No second-iteration interview, student grade or assessment result has been produced here. Tests use synthetic replies and grades only. The previous completed iteration's real conversation score remains 0/100.

## Evidence checked before publication

- Require the same verified terminal model, source-bound diagnostic receipt and optimizer selection as the interview harness. Match the loaded model/tokenizer, architecture, embedding convention and raw greedy decoding identity. The publisher refuses the current live job before transcript/grade allocation.
- Verify completed-session and transcript checksums, the interview implementation/protocol hashes and the declared eight-turn coverage. Generation errors or incomplete interviews cannot be passed off as complete assessments.
- Reconstruct every user/assistant history from the raw rows. Check its context hash, exact BPE prompt length and actual model context ceiling. Do not discard earlier failures or truncate history to make a turn fit.
- Decode every reply from its raw content token IDs; verify vocabulary range, generated/content counts, first structural stop, EOS/message-end/length reason, 64-token bound and finite observed timing. Altered ideal text cannot replace a saved bad reply while retaining its tokens.
- Require delegated expert review, human attestation false, full-transcript-read declaration, one 0–4 score/reason/evidence-turn list per original dimension, and one explicit task-success judgment/reason for every actual turn. Require limitations.
- Aggregate the five direct scores out of 20 and normalize to 100. Keep the full raw transcript, qualitative evidence, model/terminal identity and input hashes in the assessment report. Do not infer production readiness, population accuracy or tool capability from this conversation.

Structural consistency does not prove the qualitative judgments correct or independently authenticate who selected them. The actual operator must read the model's replies and assess them directly, as requested. A source-bound NLL failure is not grounds to skip the interview. Future training use still requires its own lineage/split review.

## Validation and live state

**50 focused checks passed / zero skips**, including transcript tampering, raw control-token changes, forged context/prompt lengths, stop mismatch, nonfinite timing, incomplete coverage, context overflow, out-of-range grades/evidence, missing turn judgments, unread-review declarations and false human attestation. Existing interview/terminal/selection/reservation cases are included. Fixture grades are never represented as student results.

An actual attempt to publish against the live run is refused for its missing terminal report and creates no assessment artifact. The preparation receipt records the live process/step snapshot and confirms that all frozen training-reference hashes still match. No new model generation, extra gradient update, teacher/API/cloud call or spending is caused by this preparation. The original training session remains the next dependency; full project goal active/incomplete.

Evidence: [preparation receipt](../reports/milestone-fifty-one-assessment-preparation.json).

After actual terminal diagnostics and the eight-turn interview, write `data/iteration-two-conversation-grades-v1.json` from direct full-transcript review. It must contain `creator`, `review_mode`, `human_attestation:false`, `full_transcript_read:true`, `dimensions`, `turn_judgments` and `limitations`. Each dimension has an integer `score` in 0–4, nonempty `reason` and valid `evidence_turns`; each turn judgment has `turn`, `task_succeeded` and `reason`.

```sh
.venv/bin/python -m slm.eval.iteration_two_assessment \
  --root data/iteration-two-experiment-v1 \
  --session data/iteration-two-conversation-assessment-v1 \
  --protocol configs/iteration-two-conversation-assessment-v1.json \
  --score reports/iteration-two-terminal-score.json \
  --selection reports/milestone-forty-nine-optimizer-selection.json \
  --freeze reports/milestone-forty-eight-experiment-freeze.json \
  --grades data/iteration-two-conversation-grades-v1.json \
  --output reports/iteration-two-conversation-assessment.json
```

The command refuses existing output and holds the experiment execution lock. Publish the actual transcript, score, limitations and failure-driven next steps before advancing to another iteration.
