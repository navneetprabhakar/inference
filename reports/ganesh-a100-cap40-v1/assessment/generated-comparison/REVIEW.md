# Independent generated-output review — 18 November 2026

**Verdict: test contextual-conversation learning next; do not promote any checkpoint. Fit30 is a reasonable provisional experimental parent, not an established best learning initialization.** The new evidence weakens an EOS-only remedy and does not justify an immediate broad foundation-training campaign. It does not prove the foundation sufficient.

## Scope and grading

I independently read all 192 single-turn and 72 rollout records for each of base10b and SFT194: **528 records**. Canonical labels, row-specific reasons and source hashes are in `independent-labels.json`. I did not read the root grader's `manual-decisions.json`. I discussed selected fit30 ambiguities with the root grader, then read its final aggregate report after finishing my labels; fit30 is not independently double-graded here. This is an exposed, investigator-authored diagnostic, not release acceptance.

Exact-output tasks allow outer-whitespace trimming only. Correct facts followed by unrelated material can earn core credit, but not clean credit. Later conflicting answers fail core. Copying an entire prompt including its unanswered question fails core. Paraphrase meaning can earn core credit when copied, but failure to perform the requested transformation fails clean. Generic genuine acknowledgements need not repeat a value; role reversal, whole-prompt echo and unrelated lectures are not acknowledgements. Blocked native turns remain failures.

## Independently reviewed results

All denominators below include every planned row. Every base10b/SFT194 output fails clean content, so neither has a fully successful session in either framing.

| Single-turn family (12 variants per mode) | Base plain core | Base native core | SFT194 plain core | SFT194 native core | SFT194 native-valid |
|---|---:|---:|---:|---:|---:|
| Entity | 4 | 1 | 5 | 2 | 1 |
| Correction | 5 | 1 | 7 | 4 | 1 |
| Temporal state | 5 | 1 | 6 | 6 | 5 |
| Negation | 9 | 0 | 6 | 4 | 1 |
| Exact instructions | 0 | 0 | 0 | 0 | 0 |
| Uncertainty | 3 | 5 | 7 | 3 | 1 |
| Paraphrase | 8 | 5 | 6 | 7 | 0 |
| Supplied-context recall | 7 | 0 | 8 | 6 | 3 |
| Total /96 | 41 | 13 | 45 | 32 | 12 |

Base native-valid is 0/96. Both-variant core-passing pairs: base plain13/48 and native3/48; SFT194 plain15/48 and native8/48. Plain/native discordance: base33 variants plain-only versus5 native-only; SFT19420 plain-only versus7 native-only. These are correlated scenarios, not independent sample-size claims.

| Rollouts | Base plain | Base native | SFT194 plain | SFT194 native |
|---|---:|---:|---:|---:|
| Core-correct turns /36 | 7 | 0 | 9 | 3 |
| Final recall /12 | 3 | 0 | 5 | 0 |
| Complete clean sessions /12 | 0 | 0 | 0 | 0 |
| Blocked turns /36 | 0 | 24 | 0 | 22 |

SFT194 native day1 is especially informative: all three actions complete legally, it acknowledges Monday then the correction to Sunday, but finally answers Monday. This is an observable state-update failure without blocked-history or token-cap explanation (`sft194-rollouts.jsonl`, zero-based57–59). Base and SFT194 failures often involve repeated worksheet text, fabricated metadata and forged dialogue. SFT194's repeated “Work Step by Step” procedures and “Suspend SCALE/disbelief” material show that fluency and initial fact retrieval do not imply useful conversational behavior.

## Challenge to the proposed next step

The root report's fit30 native clean27/96 versus zero for the other two supports **trying** fit30 first. The complete-rollout failures do not erase that measured advantage, but they prevent calling it the best conversation model or assuming it will learn fastest. Fit30 previously worsened held-out content CE while overfitting a narrow corpus; those weights and optimizer state may retain liabilities that the short-answer panel misses.

A diverse-coverage versus exposure-matched narrow-control SFT experiment from identical fit30 states is coherent and more informative than blind additional replay. It answers a specific question: does diversity help this initialization under this recipe? It does **not** establish fit30 superiority over base initialization, that diversity alone is causal when response lengths/target mass differ, or that failed SFT implies foundation training is required. Preserve these distinctions in interpretation.

For a bounded first pilot, I would not multiply arms solely to resolve parent choice. Keep base10b and SFT194 intact; require a fixed baseline and prospective held-out generated exchanges spanning acknowledgements, corrections, factual grounding and ordinary conversation. If fit30 improves only legal endings or training-template recall, stop rather than declare transfer. If both control and treatment deteriorate, diagnose common initialization/optimizer/objective factors before concluding that more pretraining is necessary. A base-parent comparison becomes a justified subsequent question only if that failure pattern points there; it is not automatic authorization.

## Remaining confounds

- Native/plain changes policy scaffolding and token framing together. No isolated EOS or policy-causality claim follows.
- The64-token cap penalizes verbose models. That is relevant to this concise interface, but these are not unrestricted-English scores. More budget would not fix observed wrong entities, contradictions or stale corrected dates.
- Plain `Answer:` is also a learned format, and plain rollouts feed malformed output into later history. Plain/native rollout paths are deliberately different; their final recall numbers are not an isolated memory comparison.
- Twelve acknowledgement-heavy sessions cannot establish a memory ceiling. Blocked turns prove end-to-end failure, not inability to answer unreachable later questions.
- Some core/clean boundaries are subjective. Conservative treatment of invented apology settings or marginal acknowledgement wording changes a few labels, not zero clean sessions or the repeated unambiguous state failures. No blinded human grading or full independent fit30 review was performed.
- The panel size is a bounded diagnostic choice. It supplies no sufficient corpus size, training-update estimate, release threshold or trustworthy GPU-budget estimate.

No new inference, training, cloud action, weight edit or serving change was performed by this reviewer. The next learning design still needs reviewed data, a prospective contract, fixed budget/reserve and applicable operational gates.
