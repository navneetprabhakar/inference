# Complete OASST sample review and screening diagnosis

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

**Do not admit the proposed version-one screened pool.** Its uncalibrated per-window English cutoff rejects observed valid short and informal English. It also leaves insufficient data for the intended 10M experiment at the proposed exposure limits. Preserve this experiment unchanged as diagnostic evidence; develop a separately versioned language policy and expand the foundation pool.

No second-iteration neural training has started. The first-iteration conversation score remains 0/100. The complete conversation/style/content/tool/portability/ESCI objective remains unchanged.

## Actual readings

All **74 sampled OASST paths**, plus three Dolly references in the same mixed groups, have now been read in full: **77 paths / 20 complete groups**. Shared messages were read once with their exact path lineages and equality checks. Earlier twenty-path judgments remain intact. The cumulative outcomes are:

| Development judgment | Paths |
| --- | ---: |
| Suitable for bounded SFW research consideration | 18 |
| Excluded | 32 |
| Unresolved | 27 |

These are delegated expert judgments with **human attestation false**, bound to the original audit, sample and record hashes. They are not source-wide quality rates or training approvals. The other 52 sampled source/reference rows remain ungraded; they are outside this OASST candidate decision.

Observed failures include source-project identity answers that would misdescribe the new student, taking all player actions in an interactive game, broken requested formats, role-label artifacts, missing-context references, ungrammatical revisions and unsupported technical guarantees. Bibliographic, biographical, game-mechanics and dated numerical claims remain unresolved where they were not checked; unknown is not relabelled false.

Concrete checks strengthen three judgments:

- A JSON conversion changes source-supplied Germany, UK and Italy GDP values by a factor of **100**. An executable decimal/JSON comparison verifies the mismatch against the source text; it does not verify real-world GDP. [Quantity check](../reports/milestone-forty-five-quantity-check.json).
- The oxygen explanation omits oxygen-17 while claiming only two stable isotopes; [CIAAW's oxygen table](https://ciaaw.org/oxygen.htm) lists oxygen-16, oxygen-17 and oxygen-18 with terrestrial abundances. The separate terminology/history questions remain unresolved where not verified.
- A timer example manipulates GUI objects in a background thread; [Qt 5.15 documents the main-thread restriction](https://doc.qt.io/archives/qt-5.15/threads-qobject.html). A Dolly reference gives Washington's presidency end year as 1997; [Mount Vernon's history](https://www.mountvernon.org/george-washington) gives 1797. Neither source example is silently repaired.

[Complete bound judgments](../reports/milestone-forty-five-dialogue-review.json). The replay script contains static notes for these exact inputs and refuses changed hashes; it is not a classifier. Source/factual checks above do not establish an independently executed real GUI/PDF application or complete factual verification of a conversation.

## Proposed screen and measured outcome

`slm.data.dialogue_screen` consumes the frozen staged population, full-message audit, completed review and [proposed policy](../configs/iteration-two-dialogue-screen-v1.json). It:

- Recomputes structural/privacy signals, validates complete language-window coverage and binds the original raw-node text hashes and metadata.
- Marks declared research-scope attention, privacy/redaction/transformation attention, unfilled templates, source identity/role artifacts and unverified code. These are explicit exploratory exclusions, not calibrated classifiers; benign educational, informal or technical examples can be affected.
- Applies the proposed 0.8 English top-score rule to each window. Any candidate attention or known excluded/unresolved review quarantines its entire existing group. A good sibling can therefore be removed deliberately; that group effect is distinct from a direct language false exclusion.
- Preserves original text, content labels and partition assignments in remaining candidates. It never sets a training approval or grants source rights. Output remains sample-only; the policy validator refuses an admitted status.

The actual run completed and retained **9,471 paths / 2,494 groups**: **8,108 train / 890 validation / 473 test**. Another 9,355 train candidates are quarantined. The original 2,237 frozen references remain unchanged in their parent snapshot and are not promoted into train by this screen. [Screen receipt](../reports/milestone-forty-five-dialogue-screen.json).

First-pass attention includes 6,130 paths with low/non-English top-scoring windows, 2,061 with unverified code, 826 with source identity/role patterns and 514 with bounded-scope expressions. Counts overlap and do not measure actual language/content/privacy error rates.

Existing-tokenizer sizing on the remaining train candidates gives:

| Measurement | Result |
| --- | ---: |
| Content tokens counted once per raw node | 2,688,887 |
| Content-token occurrences across paths | 3,731,773 |
| Shared-node repeated content occurrences | 1,042,886 |
| Full serialized processed positions | 3,795,189 |
| Assistant-supervised positions | 3,286,152 |

No tokenizer fitting, truncation, admission or neural updates occurred. These are sizing observations, not a prepared schedule or global semantic uniqueness. Even two passes over the measured full-path positions do not reach 10M on this source alone. [Measurement](../reports/milestone-forty-five-screen-measurement.json).

## Why version one is not accepted

Of the **16 sampled OASST paths judged suitable for research consideration**, **11 directly trigger the language-score rule**, including ordinary greetings, a requested pirate persona, riddles and coherent clarifications. All sixteen are ultimately quarantined, some additionally through intended sibling-group effects. The two suitable Dolly references are not current OASST candidates and are excluded from this denominator.

This is a selected diagnostic, not a population false-negative estimate. It is sufficient evidence that copying the prose-oriented cutoff into every short conversation window is unsuitable for this project's informal-English requirement. The cutoff was an exploratory screen, not an accepted production classifier. No historical numerical/training gate is relaxed, and the failed screen is not rewritten to appear successful. [Retained decision and exact low-score windows](../reports/milestone-forty-five-screen-decision.json).

The next language comparison must separately examine short utterances, informal/persona language, longer prose and genuinely non-English negatives. Publisher labels, detector scores and lexical script features are evidence with different failure modes. A confidence score cannot substitute for a correctness or coherence judgment.

## Prospective sample and next work

Before selection, a [new review protocol](../configs/iteration-two-dialogue-prospective-review-v1.json), the screened population manifest and audit specification were frozen. The completed audit selected **74 paths / 22 groups**, with **zero group overlap** with the earlier twenty reviewed groups. All new paths remain **ungraded**. The old 52 ungraded reference rows and these new 74 paths are different review packets.

The new audit reports no attention flags because its input was selected using those same features. This is conditional selection, not independent proof of quality, privacy or factual correctness. [Prospective sample receipt](../reports/milestone-forty-five-prospective-sample.json) and [audit](../reports/milestone-forty-five-prospective-audit.json).

Next actions:

1. Calibrate a separately versioned language policy against complete short/informal English and non-English examples. Preserve the rejected version-one pool and its evidence.
2. Measure a broader licensed foundation pool. Reuse the existing complete-source artifacts where appropriate; do not manufacture sufficient exposure by repeating this small filtered subset.
3. Freeze the resulting population before independent sampling/admission. Separate language-foundation suitability from conversation-SFT correctness; neither grants blanket production approval.
4. Publish an exact bounded delegated research admission decision and checked reader, compare representative train-only tokenizers, then freeze and run the next local experiment. Keep the conversation → score → next-iteration workflow.

## Validation and reproduction

**61 focused checks passed** across screening, candidate extraction and the existing quality audit. New checks cover whole-group quarantine, preserved labels/partitions, raw text changes, forged signals, incomplete windows, population/audit/review bindings, existing-output refusal, cleanup and refusal to claim admission. The prior full-suite result remains historical; it was not rerun here.

Actual review replay, screening, candidate sizing, executable quantity comparison and prospective audit completed successfully. No new neural update, teacher generation, Platform teacher API or cloud job. Budgets and Option A remain unchanged; full goal active and incomplete.

The actual unchanged training reader also [refuses the screened output](../reports/milestone-forty-five-reader-refusal.json) as sample-only data; the proposed policy cannot silently become a training release.

```sh
.venv/bin/python scripts/review-iteration-two-dialogue-holdouts.py
.venv/bin/python -m slm.data.dialogue_screen \
  --dataset data/iteration-two-dialogue-preparation-v1/staged \
  --audit data/iteration-two-dialogue-preparation-v1/quality \
  --review reports/milestone-forty-five-dialogue-review.json \
  --policy configs/iteration-two-dialogue-screen-v1.json \
  --output data/iteration-two-dialogue-screen-v1
```

Commands refuse existing outputs. Preserve actual artifacts; use a separately named output for a new experiment.
