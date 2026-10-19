# Cosmopedia candidate acquisition and provisional screening

Creator: Navneet Prabhakar

Date: 19 October 2026

## Actual outcome

- **49,000 published rows /39,327,734 student-BPE text-token occurrences**, acquired from49 revision-pinned Parquet files. Screening provisionally passes31,920 rows /24,630,245 content tokens. These are candidate counts, not admitted training exposure or a model-quality result.
- The fixed hash selection covers at most one compatible group from each of50 distinct files out of104. It is a clustered source sample, not a representative quality estimate. One failed1,000-row group remains excluded and charged; the original50,000-row reservation is fully accounted for.
- Original prompt, generation, audience, format, constituent label and upstream token-count metadata are retained. Actual student token counts are measured independently. No conversation roles, ideal assistant targets or train/validation/test partitions are invented.

## Implemented controls

- Revision/size/strong-entity-tag-bound exact HTTP ranges; unchanged declared row-group/footer/compressed/decoded bounds; actual Arrow size checked after decode. No whole-shard fallback or automatic network retry. Whole-shard LFS hashes are not independently recomputed.
- Persistent precharges for requests, body bytes, decoded rows and retained output. The earlier metadata probe's charges are imported rather than reset. Cached completed responses and outputs are hash-checked on recovery; pending/failed operations cannot silently replay. Row work is reserved **before** decode.
- An independent parent supervisor enforces the original three-hour deadline and owns a separate process group containing the worker and its detector children. Explicit continuation reuses the original SQLite contract/deadline. Free-disk/work checks and precharged outputs remain bounded; this is not a hard RSS or hostile-codec sandbox.
- Provisional screening requires the exact FineWeb seed-excerpt profile and rejects unresolved constituent sources, known prompt/seed nonapprovals, protected evaluation text in either original field, privacy/credential patterns, short/repetitive/control-corrupted text and contradictory English-window predictions.
- Every otherwise eligible prompt and generated text is checked in all qualifying1,024-character language windows using the pinned offline detector. Window offsets and actual score pairs are retained. These are language/privacy signals, not certifications or factual review.
- All rows remain `training_approved:false` and `partition:null`. Global exact/near/seed overlap with other sources, ancestral heldout protection and finite membership admission remain mandatory.

## Observed failure and correction

The initial worker completes seven groups, then stops on the eighth. Two literal `</s>` words in the detector input act as fastText end-of-line controls:4,664 input windows produce4,666 predictions. Retained outputs all parse individually; the mismatch correctly refuses alignment instead of associating scores with the wrong source windows.

The pinned local fastText dictionary implementation identifies `</s>` as its EOS word. A read-only experiment on the retained input confirms that escaping this syntax **only in the classifier view** restores4,664 predictions. No network request, source-group re-decode or student update is used for this diagnosis.

The separate `detector_projection` helper preserves original source strings and offsets. Its classifier view replaces literal `</s>` with `< /s >` and flattens line endings. This is explicitly recorded detector-input preprocessing, not a repair to training text.

Versioned worker/plan v2 retains the original source, plan, failure and first seven completed outputs. It continues the remaining original file selection using the same limits and deadline; it skips the failed file without replaying its uncertain decode. The1,000-row charge stays pending and visible. Final outputs therefore contain49,000 rows while reserved work totals50,000. Per-phase source identities remain in the receipt.

## Resource evidence

| Counter | Actual or conservative charge | Frozen ceiling |
| --- | ---: | ---: |
| Logical requests, including prior metadata |201|256|
| Successful bodies, including prior metadata |303,912,303 bytes|Body reservation governs|
| Conservative body reservation |304,140,431 bytes|536,870,912 bytes|
| Retained-output reservation |683,542,747 bytes|1,073,741,824 bytes|
| Published /reserved rows |49,000 /50,000|50,000|

HTTP header/redirect overhead is outside body counters. Temporary work and filesystem allocation are distinct from retained-payload reservations; observed work stays well below the12GiB work cap. The20GiB free-disk reserve is checked before each selected file.

## Verification and next step

- **52 focused tests pass:**13 range-reader,8 seed-parser,10 exclusion,8 ledger,5 cache,4 provisional-quality,2 detector-projection and2 supervisor checks. The supervisor tests exercise the actual timeout path against an owned dummy process and confirm that a preexisting resume deadline is retained. Earlier43/48-check receipts overlap; the separate50+2 receipts cover52 distinct checks.
- The retained-output checker verifies every published row's payload hash, raw-record digest, seed span/family, evaluation exclusions, privacy flags, recorded full-window scores and actual BPE count. It reconciles all reservations and the unreplayed pending decode. It does not refetch or independently re-decode upstream groups or rerun detector predictions.
- This check covers231,778 recorded language windows and verifies296 retained payloads. It finds31,903 distinct normalized texts among31,920 provisional passes (17 repeated member rows), plus1,718 repeated exact-seed member rows across parsed FineWeb seeds. These counts are input to the next grouping stage. Counting them does not constitute global deduplication, new split assignment or near-heldout isolation.
- Evidence: `reports/cosmopedia-candidate-intake.json`, `reports/cosmopedia-candidate-intake-check.json`, `reports/fasttext-line-projection-diagnostic.json` and the50-test plus two-supervisor receipts. Raw rows, range payloads, scores and ledger remain under ignored `data/cosmopedia-candidate-intake-v1`; metadata receipts identify each row-cache artifact.
- Next acquire the larger general-English and simple-narrative portions, then perform cross-source grouping/heldout checks and finite admission. This explanatory source alone must not silently replace the corrected60/20/20 language mixture. Required teacher-conditioned conversation learning follows the separate language gate.
- No model update, teacher call, paid resource or cloud spend occurred. Existing failed checkpoints and all prior training-runtime hashes remain unchanged. The full project goal remains active and incomplete.
