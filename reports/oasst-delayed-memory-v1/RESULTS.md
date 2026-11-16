# Multi-turn correction and delayed-memory source review

16 November 2026. **50 complete TRAIN conversations / 150 assistant responses reviewed; zero new candidates retained or admitted.** This is a negative source-discovery result, not a model assessment or a reason to lower admission standards.

## Search and full review

| Stage | Eligible paths before encoding | Complete conversations read | Assistant responses |
|---|---:|---:|---:|
| Previously unseen, reviewed rank-zero paths | 34 | 18 | 54 |
| Broader reviewed nonnegative-rank branches | 531 | 16 | 48 |
| Additional writing/correction-keyword branches | 67 | 16 | 48 |

Paths require 3–6 assistant turns; all selected paths have three. Selection prefers longer paths, with deterministic hash ordering and one path per tree. Every node is English, reviewed, nondeleted, marked nonsynthetic and upstream TRAIN. Entire trees must be absent from upstream validation. Previously reviewed trees are excluded. Source rank is a discovery filter, never semantic acceptance.

The first scan exhausts eligible new rank-zero paths under these constraints: 16 paths fail encoding/context/reply limits and 18 are selected. The two broader scans are bounded samples, **not exhaustion of OpenAssistant**. Keyword filtering finds apparent corrections but does not prove successful retention. Broader source ranks did not produce an acceptable target in the reviewed sample.

Review requires a fully suitable trajectory, plus either a correction preserved into a later reply or retrieval of an earlier user fact after an intervening completed exchange without the target restated in the query. Acknowledgments, repeated user facts and simple same-topic continuation do not count. This scope-specific rubric does not imply all excluded material is globally unusable. Manual observations for every assistant turn are in `review.json`; original source text is retained separately and not rewritten.

Concrete failures:

- F9 applies a requested code fence, then loses it in the following TypeScript revision.
- F5 keeps the same chorus three times after being asked to reduce repetition.
- D10 accepts ownership of the user's argument as if the assistant had made it.
- F15 retains names but invents product features absent from the user's brief.
- D16 is a clean three-turn exchange consisting of document-help setup, thanks and goodbye; it does not teach delayed recall.
- F6 coherently extends a fictional premise, but has no corrected state or delayed user-fact retrieval. D7 is explicitly fictional reunion roleplay, with the name repeated in the last user prompt; it is not evidence of memory.

No final-turn salvage: later repair does not justify supervising an earlier bad answer. Domain-heavy paths are excluded/deferred where specialist facts or code have not been independently verified. They are not presented as externally fact-checked.

## Checks and evidence

Pinned OpenAssistant/oasst2 revision `179dd21fc55192153d94adb0e0ce8f69e222bf75`; archive and TRAIN/validation parquet hashes checked against existing download receipts. Dataset card declares Apache 2.0; nonsynthetic metadata is not independent proof of human-only authorship.

`validate.py` independently matched every selected message's exact text, role, parent linkage, tree ID, source flags and actual assistant rank against TRAIN parquet. Validation uses upstream validation tree IDs only, not its conversation text. All 50 trees are distinct and train-only. See `validation.json` for ranks and source hashes.

Own's tokenizer passed all **300 generation-prefix checks** (150 assistant turns × both no-call modes) at native 2K, with a 512-token candidate reply ceiling. This does not change frozen diagnostic budgets or constitute production masking/admission qualification. **All 41 frozen files hash-match.** No overlap audit was run for the empty shortlist; no contamination clearance is claimed. Sealed release content was not inspected or consumed.

The earlier shortlist remains **four two-turn conversations / eight assistant responses / 595 unique supervised targets**, none admitted. This review contributes **zero targets**. Sustained correction and delayed-memory coverage remain open; source counts cannot substitute for those capabilities. Model quality remains unchanged and unaccepted.

## Next work and boundaries

1. A further source sweep can examine remaining reviewed TRAIN branches for explicit user facts and later retrieval. Record full-path quality and actual memory distance, not keyword hits or turn count. Keep whole-tree grouping and the same provenance/context gates.
2. Do not broaden this shortlist with factual, coding or low-quality examples merely to fill coverage. If organic discovery continues to fail, prepare a separately versioned generated curriculum with explicit provenance, source/scenario splits and full review; that would be a separate work item, not a rewrite of these sources or the frozen fit set.
3. No curriculum admission until contamination, full review and production contracts pass; frozen diagnostic fit GO remains a prerequisite to curriculum training. Prior four candidates retain their previous limited contamination checks.
4. No VM, GCS, training, model/default or HTTP actions. No fresh cloud-state verification claimed. L4 only, with new explicit finite cap and qualification before compute. Existing CUDA signal-recovery, upload and provider-STOP blockers remain.

Reproduce selection in order: `select.py`, `branch_select.py`, `focused_select.py`; materialize the recorded manual decisions with `review.py`, then run `validate.py` using `.venv/bin/python` from repository root. These scripts write only this report directory, not training inputs. `receipt.json` binds this snapshot; rerunning selectors does not independently redo semantic review.
