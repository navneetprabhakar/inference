# Dialogue format and paired development probe

**Gate status.** The CPU serialization, masking, scorer and fixture-correlation checks passed. The next measured gate requires a student checkpoint to pass at least 16 of 20 pairs separately for copying, correction and reporting an observed result. This package contains no student generations.

## Using the format

The host supplies a trusted role header, then a compact JSON body. Numeric GPT-2 EOT 50256 terminates each frame. Ordinary content is escaped as JSON, including quotes, newlines and literal angle brackets. The assistant emits exactly one JSON object containing either text or a proposed call. The actual trusted broker owns the call ID, authorization and result.

- Use `assistant_prompt(tokenizer, history, reply_budget=...)` to make the generation prefix. Feed only the new student output IDs through `parse_assistant`. Complete the trusted broker step before appending the observed tool record.
- Use `training_row(tokenizer, history)` for SFT. Inputs and labels are already shifted once. Sum CE over labels other than `-100` and divide by the supervised-token count across the update. Use `pad_row` to add ignored pad targets.
- Host headers, system/user text and observed tool data are masked. Each assistant JSON body and its terminating EOT are supervised. The host call ID first appears in the tool record. The transcript object privately binds the proposed call to that same ID and rejects unrelated or replayed records.
- The codec rejects invalid role ordering, unfinished training transcripts, rows without assistant targets, and histories that exceed the reserved context. The caller should count rejected examples by reason when compiling a training corpus.

## Reproduction

Run `.venv/bin/python verify_dialogue.py` from the workspace. The test uses a real offline broker record for subtraction. It verifies input/label alignment, both assistant-prefix positions, full tool masking, exact end-marker supervision, failed calls, chained calls, call-ID/argument mismatches, attempted role injection, context reservation, and scorer controls.

## Frozen probe

`counterfactual-dev-v1.jsonl` contains 60 paired families, 20 in each skill. Every pair has two members and both must pass for the family to pass. Each prompt asks for just the value. The scorer trims surrounding whitespace and requires the exact text, including case. Decode greedily with at most 32 newly generated IDs including frame termination. The longest prefix is 143 tokens. Run `verify_dialogue.score_probe(tokenizer, generate)`, where `generate(prefix_ids, reply_budget)` returns the raw generated suffix. Save its per-member outputs and reasons with checkpoint and decoding metadata.

Copying pairs vary one source fact with a distractor present. Correction pairs keep an earlier user fact and scripted acknowledgment in history, then vary the replacement fact. Grounding pairs inject an already-correlated, explicitly labeled offline replay. Both members share a proposal and differ only in the result field. One result deliberately disagrees with arithmetic. The probes measure conditional answer generation. A separate end-to-end evaluation must measure tool selection and uncued multi-turn conversation using actual student history.

Store the probe as evaluator-only development data. The probe inputs and labels must be excluded from future supervised data and teacher prompts. `overlap.json` records the exact audit against the 5,770 pilot documents and 12 development conversations. There were zero shared eight-word windows. Semantic overlap and overlap with any future corpus still need review. The sealed confirmation prompts were not opened for this assignment. A blinded custodian can audit that separation without releasing text to training.

## First supervised diagnostic

The fixed mixture in `sft-teaching-v1.jsonl` contains 289 assistant-authored synthetic conversations. The author reviewed the per-family text patterns and checked fixture values against the local broker. The set has 72 copying, 72 correction, 96 counterfactual calculator-grounding, 20 ordinary prose, 12 no-call, five conversion, six failure and six clarification conversations. The correction and grounding tasks intentionally dominate this narrow diagnostic. Independent human review and a broader conversational training distribution remain open.

The record identified as `sft-0278` was retired before freezing after the confirmation custodian flagged a scenario-family similarity. Other IDs remain stable. The teaching and probe preparation scripts never read sealed cases. The frozen hash is `2e70e4d24e58fc8aef2f43014e1c4613bc50f9c2b984f2af4310929ad0b433ef`. The teaching audit found zero matching eight-word windows against the paired probes and the 12 development conversations.

The first diagnostic fixes seed 137 and two passes, totaling 48,210 nonpadding model inputs and 12,438 supervised assistant targets across 74 updates. The active cap is 30 minutes including both evaluations. The elapsed cap is 45 minutes. AdamW uses a peak learning rate of 0.0001, four warmup steps and cosine decay. Each update uses the sum of assistant-token CE divided by the number of actual assistant targets in its batch. A baseline and the single fixed endpoint are evaluated with identical greedy settings on the probe and all 12 development conversations.

Run `.venv/bin/python verify_sft.py` for CPU wiring evidence. Run the full diagnostic only with a protected, measured passing extended-pretraining base and its verified hash:

    .venv/bin/python sft.py <base-checkpoint> <base-sha256> runs/astra-sft-01

The runner reserves input and target budget before updates, publishes status atomically, and uses the shared device lock, resource guards and checksum-verified checkpoints. If an interruption left a verified running checkpoint, append `--resume` with the same arguments. Replayed work counts against the original cap. A failed paired gate closes the diagnostic. Passing all paired gates leaves the candidate pending separate adjudication of complete development conversations, followed by a decision on the sealed evaluation.
