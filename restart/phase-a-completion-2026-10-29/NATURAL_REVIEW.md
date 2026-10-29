# Natural development reference review

Reviewer: a separate model-agent reviewer, not a human reviewer or an independent model provider. This is a separate-author reference review, not fresh blind grading: the prior calibration review is known.

New evidence access was limited to NATURAL_DEVELOPMENT.md in this directory. No other evidence files, author labels, repository history, or reports were read. No student-model training or inference was performed. The source packet was not edited.

## Decision standard

Admit means the reference conversation is usable for semantic development grading, with any stated interpretation limits. Revise means a local correction is needed to remove ambiguity, unsupported content, or an inadequate recall probe. Reject would mean the frame is unusable without fundamental replacement. Decisions concern reference quality, not observed student performance. No desired pass count was assumed.

Results: 17 admit; 7 revise; 0 reject.

## Cross-case findings and limitations

- The packet has meaningful local task variation: entity binding, negation, unknown-to-known updates, event order, conditional reasoning, attribution, clarification, placeholder drafting, constrained edits, retraction, format switching, ordered actions, causal explanation, and simple arithmetic. These are not 24 unrelated task structures; several reuse slot retrieval, one-field updates, or short sequence tracking.
- All 24 use the same four-turn architecture: initial fact/task, follow-up/update, one brief interruption, and an explicit return cue. This does not establish varied conversation lengths, interruption positions, multi-turn digressions, implicit returns, or robustness to substantial context interference.
- Cases 04 and 07 end with absent-information questions that can be answered without recovering a previously supplied value. They need positive recall additions. Cases 05, 08, 21, and 22 have inference-limit or yes/no returns; supplying recalled facts or reasoning improves evidence, but a correct generic negative answer alone is weak evidence of memory.
- Many other turn-4 answers are already present in earlier assistant responses. Cases 01, 03, 13, 14, and 16 provide useful retrieval or recombination beyond repeating only the immediately preceding task answer. Case 10 introduces a competing time, whereas most interruptions are unrelated single-fact questions.
- Family labels are approximate. Case 12 is a placeholder/edit task under clarification; case 23 is arithmetic under explanation; cases 01 and 16 overlap entity-specific state updates. Evaluate actual operations rather than treating four cases per label as balanced coverage.
- Turn 1 of case 05 contains a reasonable inferred protective motive. Do not prohibit ordinary supported inference. Conversely, the added pronoun in its turn 4 is unsupported, and quantifier/necessary-condition ambiguities in cases 21 and 24 deserve explicit repair.
- Semantic grading must allow paraphrases, ordinary terminal punctuation, and valid alternative reminders or actions. It must not require exact reference wording, or treat one admissible reference as exhaustive. Missing-information clarification can be reasonable without being the only permissible response unless explicitly required.
- The reference answers themselves do not prove any model performed actual recall, followed instructions reliably, or generalized. This is a small authored development packet, not a held-out population sample, adversarial test, human confirmation, or independent-provider validation. Authorship independence is asserted by the packet and not independently verified here.
- The prior calibration review is known and some motifs recur (object locations, missing reminder times, revised storage actions, cause explanations). This limits claims of fresh blind judgment. No files from that calibration were reopened for this review.

## Per-case decisions

### natural-01 — admit

Turns 1–3 correctly track the red-key update and interruption. Turn 4 requires the unchanged blue-key location from turn 1, so it tests earlier state rather than merely repeating the latest answer. No correction required; interpret the move as a stipulated scenario update, not a claim of physical tool execution.

### natural-02 — admit

Turns 1–2 correctly distinguish owner from borrower. Turn 4 recalls Lena and the ownership/borrowing distinction after interruption, without inventing a transfer. No substantive correction required. Optional wording improvement: ask "Who borrowed the camera?" instead of "Who currently borrowed".

### natural-03 — admit

Turns 1–2 correctly bind white to the mug and blue to the plate, including negation and the color-only instruction. Turn 4 compares both earlier attributes after interruption. All references are supported. No correction required.

### natural-04 — revise

Turns 1–3 correctly move from missing sender to Arun and answer the interruption. Turn 4 is correct but asks about an always-missing delivery date; a generic missing-information response can pass without recovering the supplied sender. Add or substitute "Who does the new label identify as sender?" with reference "Arun." If retaining the abstention probe, ask for both sender and whether a delivery date was supplied.

### natural-05 — revise

Turn 1 reasonably infers protection from rain; turns 2–3 are correct. Turn 4 correctly rejects the claim that ruin was stated, but introduces unsupported "she" for Jo and says the note "only" describes moving indoors although it also describes rain. Replace with "No. The note says rain entered the shed and Jo moved the seeds indoors; it does not say they were ruined." For stronger positive recall, ask turn 4 to name both where the seeds moved and whether ruin was stated.

### natural-06 — revise

The drying answer at turn 1 is admissible, but "after washing" also includes the later packing event; the reference must not uniquely privilege the immediately next event without saying so. Change the question to "What happened immediately after washing?" Turns 2–4 are correct; turn 4 recalls the drying/packing order across the interruption.

### natural-07 — revise

Turns 1–3 correctly apply a conditional rule and stop treating its antecedent as true when the gate opens. Turn 4 correctly reports the side-door lock state as unknown, but this negative-information probe does not demonstrate recovery of the updated gate state. Replace or extend it with "Is the gate now locked or open, and does the rule require the side door?" Reference: "The gate is open, so this rule does not require the side door." Keep the side-door lock-state question as a separate abstention probe if useful.

### natural-08 — admit

Turns 1–2 correctly assign the two causes to Nora and Eli. Turn 4 avoids interpreting Nora’s stated cause as proof that she did not also lose a ticket, and recalls that Eli did. This is a useful attribution-plus-inference-limit probe. No correction required; a generic "not stated" alone would provide weaker recall evidence than the full reference.

### natural-09 — revise

The reference clarification at turn 1 is reasonable, and turns 2–4 correctly preserve the selected blue bag. However, "Which bag should you ask about?" mixes a meta-question about what to ask with the ambiguous instruction itself; asking red versus blue is only one interpretation of that wording. For a natural clarification task, use "I have a red bag and a blue bag. Write an instruction to put it on the chair" and allow a clarifying question. For an explicitly prompted clarification task, say "Ask me which bag I mean before writing the instruction." Turn 4 then tests recall of the resolution.

### natural-10 — admit

Turn 1 reasonably asks for missing reminder time; turn 2 supplies the requested reminder with 16:35. Turn 3 introduces a competing event/time, and turn 4 correctly recovers the chess lesson rather than substituting 18:00. This is stronger interference than unrelated-color distractors. No correction required; semantic grading should allow usable reminder variants.

### natural-11 — admit

Turn 1 follows the explicit request to ask for destination. Turn 2 writes a complete note naming Sam, books, and hall. Turn 4 recalls actor and destination after interruption. All assertions are supported. No correction required; this tests prompted clarification, not autonomous detection of missing information.

### natural-12 — admit

Turn 1 obeys the explicit no-question instruction and exact placeholder. Turn 2 substitutes 12:15, and turn 4 recalls that supplied value after interruption. No correction required. Although filed under clarification, its actual structure is placeholder drafting followed by an edit, not asking a clarifying question.

### natural-13 — admit

Turn 2 changes only room 3 to room 7 while preserving Ada and Monday. Turn 4 correctly recalls that the day stayed Monday after interruption. References are supported. No correction required; this probes preservation of an unedited field rather than delayed recall of the changed room.

### natural-14 — admit

Turn 2 correctly resolves the final location after two moves, and turn 4 recalls the intermediate shelf location rather than merely the final answer. No correction required. The two updates arrive within one user turn, so this is not evidence of handling successive corrections across separate conversational turns.

### natural-15 — admit

Turn 2 correctly cancels the proposed change and preserves 14:20. Turn 4 rejects the retracted 15:00 and supplies the retained time after interruption. No correction required. The update and retraction are within one user turn, limiting the conversational-state claim.

### natural-16 — admit

Turns 1–2 correctly transfer only the ruler from Dev to Noor. Turn 4 recovers the unaffected pen-holder Tara after interruption. No unsupported ownership or movement assertions occur. No correction required.

### natural-17 — admit

Turns 1–2 give concrete one-step actions that retain the book and adapt from the desk to the free shelf. Turn 4 recovers the revised plan after interruption. No correction required. Occupied does not universally mean unusable, but the explicit request to revise with a free shelf supports the reference plan; do not grade all desk use as physically impossible outside this scenario.

### natural-18 — admit

Turns 1–2 correctly switch from color-only to a sentence. Turn 3 follows a separate time-only request, and turn 4 restores color-only while recalling green. No correction required; terminal punctuation should not be treated as extra semantic content unless an exact-string format is explicitly required.

### natural-19 — admit

Turn 1 changes red to blue, and turn 2 changes small to large while preserving blue and the object. Turn 4 recalls the cumulative edited object after interruption. No substantive correction required. The reference adds terminal punctuation to the quoted source; use semantic edit-scope grading or omit that punctuation if testing literal character preservation.

### natural-20 — admit

Turns 1–2 obey first-step-only and next-step-only while incorporating the jar’s closed state. Turn 4 recalls the prerequisite that it be closed when bagged. No correction required; this is ordered action selection, distinct from extracting temporal events despite a related sequence structure.

### natural-21 — revise

Turns 1–3 correctly explain blocked light and reject invented darkness production. Turn 4 upgrades "some" into an explicit "not all," which is a common conversational implication but not a logically guaranteed reading of the original statement. Either make turn 1 explicit: "The screen blocks some, but not all, light," or revise turn 4 to "Does the note establish that all light is blocked?" with reference "No. It says some light is blocked; it does not establish that all is blocked." The latter tests the stated quantifier, though it remains a weaker positive-recall probe.

### natural-22 — admit

Turn 1 stays within the stated mechanism of reduced water loss rather than inventing a detailed physical mechanism. Turn 2 correctly declines an exact amount. Turn 4 correctly rejects the inference that slower loss entails zero loss; it does not claim a measured nonzero quantity. No mandatory correction required. The comparison implicitly assumes comparable bowls or conditions; optionally specify the same initial water and otherwise identical conditions with and without the lid to make the baseline explicit.

### natural-23 — admit

Turn 1 correctly computes half of 8 as 4 and turn 2 explains it. Turn 4 recalls the earlier quantities and correctly compares them after interruption. No correction required. This introduces numerical transformation, but only a single easy halving example.

### natural-24 — revise

Turns 1 and 4 correctly use the necessity of both switches. Turn 2 is ambiguous: "works only when both switches are on" gives a necessary condition, not a guarantee of operation. "Can it work now?" can mean merely that the rule no longer rules it out, making the reference defensible, or ask whether operation is established, making an unqualified yes too strong. Preserve the necessary-condition task by asking "Are the required switch conditions met, and does that guarantee it works?" Reference: "Both switches are on, so the stated necessary condition is met; the rule alone does not guarantee it works." Alternatively state an if-and-only-if operating rule if guaranteed operation is intended.
