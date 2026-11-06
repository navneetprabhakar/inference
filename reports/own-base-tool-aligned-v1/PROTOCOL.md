# Tool alignment v1: diagnostic preparation only

Freeze candidate DB/manifest/policy, root custody, completed independent tool review/verification/selection/judgments, this protocol and scripts, framing/helper/broker/tokenizer pins before candidate execution. Verify frozen identities before and after. Do not reopen protected cases. Preserve all existing files.

Keep train and exposed-development separate. Retain only custody-eligible lessons not independently excluded: expected5334train/422development lessons and225426/17834current-turn assistant targets. Reuse exact frozen adapted complete per-user prefixes and current policy without answer rewriting or truncation. Recompute last_turn_row(reply256,context1024); whole lesson excluded on any fit/identity failure. Report all exclusions; never silently omit a turn.

Write separate split.inputs.u16 and split.labels.u16 little-endian streams (65535 ignored labels), and split.index.jsonl. Schema matches chat alignment: source,doc_id,turn,family,split,offset,length,target_count,original_history_sha256,position_exposure. Source is own-base-tool-varied; add original_lesson_sha256=doc_id. Position bins0..255,256..511,512..767,768..1023 use predicted position label index+1. Original text remains in frozen source DB only.

Budget10minutes total after freeze, nice10, one CPU/tokenizer thread, RSS200MiB, outputs200MiB, free disk20GiB; honor runs/STOP, foundation STOP and output STOP. Abort and preserve partial artifacts; never overwrite. No GPU/model/new training admission. Tiny encode/reload test before freeze.

A fresh verification process independently reads all output rows, checks hashes/bounds/contiguity/legal IDs/masks/current-turn positions/counts, rebuilds directly from original frozen adapted histories and checks complete lessons, families/splits and exclusion absence. Independently derive label masking from dialogue._frames rather than using last_turn_row during verification. Confirm total populations and targets; retain provisional diagnostic-only status even after pass.
