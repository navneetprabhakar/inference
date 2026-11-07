# Independent v2 review

PASS for CPU preparation; root launch decision remains separate. See independent-review.json for draft identity and exact budget arithmetic.

- Worker differs from frozen v1 only in controller imports. Nine worker CPU groups pass; thirteen controller CPU groups pass. Both actual Python environments pass metadata-only gates on in-memory reviewed-state copies. No GPU/model allocation occurred.
- Race fix uses one lstat and ignores only disappearance of already-enumerated files inside a still-existing owned root. Symlinks, permission failures, vanished roots/directories and unrelated I/O errors still fail. Regression tests exercise these cases.
- Prior9,216 attempts and23.572912454605103 wall seconds remain charged. Correctness keeps21.064050334040076 seconds, overhead receives2.508862120565027. Original six-hour calendar deadline remains. Global token limit and every backend/phase criterion are unchanged.
- Aggregate storage includes retained run01 evidence plus run02. Root's separate receipt records removal of only the hash-verified disposable neutral conversion. Protected parents and numerical/watchdog evidence remain. Full rerun charges all repeated work; no automatic retry.
- Early reviewed-state refusal and required inheritance of run01 STOP were corrected before draft freeze. No remaining concrete CPU integration blocker found. First-attempt numerical passes do not establish full parity, native resume or speed.
