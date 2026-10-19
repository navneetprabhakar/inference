# Conversation language diagnostics and a larger foundation pool

Creator: Navneet Prabhakar

Date: 19 October 2026

## Result

The proposed conversation-aware language rule resolves the observed short/informal-English rejection problem on the selected diagnostic set. A larger local pool now contains **25,911 train candidates** from complete Dolly instructions and retained OASST dialogues, with **6,670,200 content tokens counted once per exact message text** under the existing pilot tokenizer. All **5,363 frozen heldout rows** remain preserved.

This is still an **unadmitted candidate pool**, not completed second-iteration training. Next: quarantine/reconcile known prior nonapprovals, review the new population, publish a bounded research release with a checked reader, compare representative tokenizers and freeze the training experiment. Do not turn repeated source preparation into a substitute for the neural experiment.

## Versioned language evidence

Version one remains retained as a failed screening experiment. Its semantics and policy are unchanged. The screening engine now dispatches an explicitly versioned second policy; tests continue to exercise version one separately.

The version-two rule separately assumes that its caller already requires publisher English labels, and then distinguishes:

- **Strong non-English attention:** a prose window has at least 80 alphabetic characters, a non-English top label and score at least 0.8.
- **Review attention:** short, low-confidence, missing/incomplete or code-heavy evidence. These observations are retained without automatically calling them English or rejecting them solely for low English confidence.
- **No strong non-English evidence:** no contradiction observed under the rule. This is not English, coherence, privacy or factual certification.

The thresholds and rule were fixed before running the comparison. These are exploratory evidence rules, not calibrated probabilities or accepted population error bounds. Privacy, original-text integrity, scope, source identity/role artifacts, template/code attention and whole-group review exclusions remain unchanged. The legacy minimum-English-score field stays validated for version-one compatibility; version two's hard language decision is bound by its separate rule hash.

## Actual comparison

| Selected diagnostic | Version one | Version two |
| --- | ---: | ---: |
| Hard language attention on 77 previously read English conversations | 38 | 0 |
| Natural non-English prose controls receiving hard attention | 12/12 | 12/12 |

The natural controls are twelve fully read roots across **German, Spanish, French, Italian, Russian and Chinese**, sampled by a fixed hash order within declared language/length constraints. They are conditioned negative controls, not a representative sample of mislabeled English-source errors. Sixteen additional explicit controls cover short/casual/caveman language, corrections, longer English, code, JSON, numeric text and short foreign utterances. **All 28 explicit/natural case expectations are met.** Short foreign utterances intentionally remain uncertain; they are not accepted as English.

The cases, rule, implementation and pinned offline detector were hash-bound before prediction. The 77 prior readings are development positives, not fresh heldout English annotations. No model weights were fitted or student tokens trained. [Comparison receipt](../reports/milestone-forty-six-language-comparison.json).

## Actual source limitations

The new screen raises language attention on **60 candidate paths**. All **48 unique triggering windows** were subsequently read in full for language only. Forty-six contain foreign prose or mixed/translation text; two have English framing dominated by foreign song titles. The latter remain potential false exclusions. Translation material can also be valid conversation outside the bounded monolingual pool.

This review does not read or grade every complete path, verify translations or assess facts/privacy/content. It is not a claim of zero real-corpus false positives. Preserve these counterexamples for later calibration, including proper names and product strings. [Trigger-window review](../reports/milestone-forty-six-trigger-review.json).

Version-two screening retains **14,999 paths: 12,821 train / 1,449 validation / 729 test**. It records 16,980 pre-quarantine candidate paths with review-attention language evidence, 3,549 without a strong contradiction and 60 with a strong language flag. Soft uncertainty is not silently erased. All output remains sample-only. [Screen receipt](../reports/milestone-forty-six-dialogue-screen-v2.json).

## Broader local foundation candidates

The complete existing Dolly snapshot contributes **14,991 canonical instruction records**, rather than only the earlier extracted reference passages. All original source labels/text/provenance remain intact. Prior Dolly judgments are attached with their exact source hashes: 42 approved explicit rows and 51 nonapproved rows in the old review. They do not approve the rest of the source.

These records and the retained OASST paths are grouped jointly against the latest complete heldout reference snapshot. No new download is required. The actual job completes in **495.815 seconds** with a peak main staging database of **1,015,209,984 bytes**, excluding journal/sort/output. This is an observed local run, not production-scale preprocessing economics or a controlled performance comparison.

| Joint population | Rows |
| --- | ---: |
| Train | 25,911 |
| Validation | 3,330 |
| Test | 2,362 |
| Total, including frozen references | 31,603 |

The train candidates comprise **12,803 OASST paths and 13,108 Dolly records**. Joint grouping moves another eighteen OASST candidates out of their previous train assignment. All **5,363 prior heldout rows** remain text-identical and retain at least their prior partition strength. A full-message quality audit covers **91,273 windows** and selects **239 paths / 67 groups** for the new frozen population; these new sample records have not yet received a complete population-review decision. [Preparation receipt](../reports/milestone-forty-six-foundation-preparation.json).

The parent heldout population includes sources retained solely as references. Their presence in a joint audit does not admit FineWeb/UltraChat or establish broader source rights. The unchanged training reader refuses the entire sample-only candidate bundle.

## Exposure and holdout measurements

The existing 16K prose-pilot BPE is loaded without fitting or changing it. Train-only sizing gives:

| Measurement | Result |
| --- | ---: |
| Content tokens once per raw message identity | 6,678,745 |
| Content tokens once per exact message text | 6,670,200 |
| Content-token occurrences across paths | 8,394,515 |
| Shared-node repeated content occurrences | 1,715,770 |
| Full serialized processed positions | 8,562,218 |
| Assistant-supervised positions | 6,435,258 |
| Full paths above 1,024 positions | 1,086 |
| Full paths above 2,048 positions | 107 |

A raw message identity is a source node ID for OASST, or a parent example/message index for Dolly. Exact-message counting does not remove common Wikipedia passages inside different question prompts, arbitrary substrings or semantic duplicates. These are unadmitted sizing observations; they do not prove a final prepared schedule or sufficient volume after admission. No truncation occurs. [Measurement](../reports/milestone-forty-six-foundation-measurement.json).

The exact checks cover all **25,911 train rows**, prior IDs/parents, the eight normalized development prompts and **586 complete heldout reference contexts**. They find **zero conflicts** under those checks. This is not a guarantee against arbitrary paraphrase/substring or global semantic scenario contamination. [Holdout receipt](../reports/milestone-forty-six-holdout-check.json).

Prior-review reconciliation also finds **87 current train rows with previous judgments**, with whole-message hashes matching exactly. **Thirty-nine carry graded nonapprovals** that must be quarantined or explicitly reconciled before admission; twenty match prior explicit approvals, twenty-five were not graded/approved, and three were suitable only for research consideration. Nonapproval may include scope/verification deferral; it does not necessarily mean a proven false answer. No new manifest can erase these distinctions. [Reconciliation](../reports/milestone-forty-six-prior-review-reconciliation.json).

## Validation and next action

**70 focused checks passed**, including the version-one regression cases, version-two policy/rule binding, short/missing/code evidence, strong non-English attention, malformed window/score rejection and unchanged nonlanguage/whole-group exclusions. The initial language/screen subset passed 24 checks. The prior full-suite result remains historical; it was not rerun here.

Actual diagnostic prediction, both language reviews, version-two screening, full-source grouping/audit, frozen-reference checks, train sizing and prior-review reconciliation completed successfully. No new neural update, teacher generation, Platform teacher API or cloud job; budgets and Option A are unchanged. The full project goal remains active and incomplete.

Next publish a **bounded research admission decision and checked release**, with known nonapprovals and privacy/scope attention handled explicitly. Use the new population's sample evidence and retain research assumptions separately from production claims. Then train/compare representative 16K/24K tokenizers, freeze cumulative exposure/optimizer/evaluation limits and execute the second-iteration experiment. The conversation → direct score → next-iteration loop remains required.

Reproduction commands refuse existing outputs:

```sh
.venv/bin/python scripts/compare-dialogue-language.py
.venv/bin/python -m slm.data.dialogue_screen \
  --dataset data/iteration-two-dialogue-preparation-v1/staged \
  --audit data/iteration-two-dialogue-preparation-v1/quality \
  --review reports/milestone-forty-five-dialogue-review.json \
  --policy configs/iteration-two-dialogue-screen-v2.json \
  --output data/iteration-two-dialogue-screen-v2
.venv/bin/python scripts/prepare-iteration-two-foundation.py
.venv/bin/python scripts/measure-foundation-candidates.py
.venv/bin/python scripts/check-foundation-holdouts.py
.venv/bin/python scripts/check-foundation-prior-reviews.py
```
