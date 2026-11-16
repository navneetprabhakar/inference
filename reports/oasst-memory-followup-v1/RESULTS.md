# Remaining TRAIN-path correction and memory review

16 November 2026. **20 further complete conversations / 60 assistant responses read; zero retained or admitted.** Prior review and handoff were committed and pushed to main as `9b63b98` before this follow-up began.

## Scope and outcome

| Stage | Eligible source paths before encoding | Complete conversations reviewed | Assistant responses |
|---|---:|---:|---:|
| Remaining writing/correction keyword-filtered paths | 30 | 4 | 12 |
| Additional branches without keyword filter | 446 | 16 | 48 |

The first scan exhausted its remaining filtered pool, not OpenAssistant: 21 paths failed context/reply limits, four distinct trees were selected, and remaining paths belonged to already selected trees. The second scan was capped at 16 distinct trees; 14 paths failed context/reply limits before reaching the cap. The 446 paths are not 446 unique conversations. All selected paths have three assistant turns. Earlier reviewed trees are excluded, and the second stage also excludes the first stage's four trees.

Both use the pinned upstream TRAIN split, reviewed/nondeleted/English/nonsynthetic nodes, reviewed nonnegative assistant ranks, whole-tree split isolation, longest-path-first ordering and hash tie-breaking. Source rank and keyword matches are discovery heuristics, not quality approval.

Full-path manual decisions and each of the 60 assistant-turn observations are in `review.json`. Examples of exclusion:

- N1 fails a request to reformat its own code, then calls that code the user's and overlooks a return in its loop.
- N2 answers a slant-rhyme request with repeated exact rhymes.
- N3 shortens its answer but labels the earlier reply an article; no later turn tests whether the brevity correction persists.
- R3 answers a different question when asked whether a disk command fixes errors or only reports them.
- R9 ends with an elementary grammar error.
- Most remaining paths involve technical, legal, historical or time-sensitive factual content that was not independently verified. They are excluded from this English curriculum shortlist, not certified as globally unusable.

No trajectory demonstrates the required combination of full-path suitability and sustained correction or delayed user-fact retrieval. Topic continuity and three-turn counts do not establish memory. Later good replies do not justify training earlier failures. No answer was rewritten, generated or admitted.

## Verification

`validate.py` checks exact source text, roles, parent IDs, tree membership, metadata and actual assistant ranks against pinned TRAIN parquet. Validation reads only upstream validation tree IDs to enforce isolation. Source archive/parquet hashes match the existing receipts. All 20 trees are distinct and absent from earlier reviewed sets.

**120 generation-prefix checks passed** with Own tokenizer: 60 assistant turns × both no-call modes, native 2K, 512-token discovery reply ceiling. **All 41 frozen files hash-match.** No frozen budget changed. This is source/context verification, not production masking/admission or GPU qualification.

The new shortlist is empty, so no new overlap audit or contamination clearance is claimed. Sealed release content was not read. Pinned dataset revision remains `179dd21fc55192153d94adb0e0ce8f69e222bf75`; card declares Apache 2.0. Nonsynthetic metadata does not independently establish human-only authorship.

The existing four two-turn candidates remain **eight responses / 595 unique targets**, none admitted. Across the two latest three-turn reviews, 70 conversations / 210 responses yielded zero additions. These are source-review counts, not training volume or model-quality gains.

## Remaining work and hold

- Remaining non-keyword TRAIN branches may still contain useful material. The filtered pool is exhausted under these gates; rerunning it unchanged will not produce new trees. Next discovery should explicitly prioritize earlier user-provided facts and later retrieval, while preserving all quality/source gates and accounting for exposures.
- Do not expand into maths/CBSE or relax full-path quality to fill gaps. A separately versioned generated curriculum could address exact missing behaviors, but is not created or approved by this source review.
- Correction retention and delayed memory remain uncovered. Existing candidates still need the production review/split contract and broader contamination handling; frozen fit GO precedes new curriculum training.
- No cloud, training, serving, checkpoint or default changes. No fresh VM-state verification claimed. L4 only; new explicit finite cap and unresolved recovery/upload/provider-STOP qualification remain prerequisites.

Reproduce from repository root with `.venv/bin/python`, in order: `select.py`, `broad_select.py`, `review.py`, `validate.py`. Selection scripts only write this report folder. The manual review script records decisions; rerunning it is not an independent semantic review. `receipt.json` binds the evidence and current handoff snapshot.
