# Reference-passage foundation candidates

Creator: Navneet Prabhakar

## Outcome

- Extracted **3,165** exact Dolly reference passages without any question or answer targets, from the pinned 15,692-record source population. Re-grouping retained **2,900**: **2,314 train / 283 validation / 303 test**. Train text is **2,891,329 characters**, compared with 3,691,712 before re-grouping. No token count is inferred from characters.
- Preserved all **1,651 original heldout records** as heldout references. Every retained derivative has a partition at least as restrictive as its parent; 314 retained derivatives already had heldout parents. Fresh grouping moves **272 retained parent-train candidates to heldout**, protecting shared passages that a simple extraction-only split would have left in training.
- This removes known unreliable Dolly answer supervision from a foundation-data candidate. It does not prove passage truth, broad English coverage, conversation competence or corpus admission. The training reader still refuses the artifact.

## Frozen transformation and grouping

`configs/context-prose-candidate-v1.json` was fixed before measuring extraction yields. `src/slm/data/context.py` keeps only an exact, uniquely delimited context substring, with parent record/content/policy hashes and inherited split proof. It applies conservative word/script/function-word, topic, visible privacy, URL, repeated-line and boilerplate eligibility rules. Unknown language, content, privacy and quality status remains explicit. There is no translation, repair, truncation, synthetic replacement or invented human attestation. The policy and scope are described in [context prose candidates](context-prose-candidates.md).

Different question/answer rows can collapse into identical context prose. The existing disk-backed exact/near stager therefore runs again with the complete frozen parent heldouts present. It removes **265 exact duplicates**, records **1,177 near pairs** from **1,332 candidate comparisons**, and preserves heldout precedence. Global semantic decontamination is not claimed.

Main staging DB allocation was 141,586,432 bytes (135.03 MiB); observed stage time 124.53 seconds. The local test suite ran concurrently during part of this workflow, so this is an operational observation, not a controlled performance comparison or production throughput estimate. Main DB metrics exclude sort spill, journals and output.

## Actual audit and development inspection

- The pinned offline detector/quality audit covers all **4,551 staged rows**, including original frozen heldouts: **6,991 message windows**, **107 sampled rows / 71 whole groups**. Thirty-two sampled rows are derived prose, including six train rows.
- Across all 2,900 derived passages, signals flag **three non-English-top-window records** and **one privacy candidate**. Two of the language flags and the privacy candidate are in train; one language flag is in validation. These signals are unverified candidates, not confirmed defects or calibrated confidence. The separate totals for all staged records include additional frozen-reference flags.
- Actual delegated development inspection covers **ten complete passages**: all six sampled train passages and four heldout passages. Recorded notes identify a malformed trailing citation in a GDP passage, unanchored current quantities in otherwise readable prose, minor punctuation/style issues, and public biographical details requiring explicit policy treatment. This inspection does not claim that the other sample rows were graded, that accepted facts were independently verified, or that the population has an estimated error rate.
- The immutable sample, detector evidence and exact row notes are bound in `reports/milestone-thirty-eight-context-review.json`. There are **zero new training approvals**. The existing 42-row explicit conversation release remains unchanged.

## Verification and next action

Focused prose tests: **12 passed**; combined prose plus preserved model-context tests: **15 passed**, covering exact substring/lineage preservation, exclusion rather than rewrite, ambiguous/missing contexts, privacy/topic/boilerplate attention, invalid encoding, length/script proxies, and independent regrouping of equal passages across train/test. The new tests are in `tests/test_context_prose.py`; `tests/test_context.py` is restored byte-for-byte to its prior context-parity coverage. An initial naming collision briefly displaced its three tests: the retained initial 711-pass report is therefore incomplete evidence. Final full local suite: **714 passed / 15 hardware-dependent skips** after restoring those tests. Read-only readiness evidence is captured separately.

Next: implement a distinct bounded research-admission artifact/reader for this derivative, preserving policy-admitted status rather than individual human verification. Quarantine attention flags and observed malformed text under a prospective policy; bind the population, source evidence, policy, sampled judgments and delegated decision. Enforce local experiment/exposure ceilings before tokenization/training, then measure actual 16K/24K tokenizer yield and a finite 1M-position pilot. If the resulting unique corpus is too small, obtain additional suitable data rather than manufacture a milestone with excessive replay. This is a foundation pilot; broader dialogue/style/tool training still requires the original full goal.

No downloads, new teacher launches, public-data model updates or cloud jobs. Teacher remains CLI-only at 17/20 reserved slots; conservative CUDA allowances remain USD 7/10, settled cost unknown. Option A remains accepted and strict trajectory failures remain diagnostics. The full goal remains active/incomplete.
