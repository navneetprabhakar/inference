# Root tool-candidate custody

Frozen candidate DB SHA256: `113d5d37d35fd03fee3ff00d07614d4295f3fb8452bd84f9660b800fe253b07f`.

`protect_own_tool_candidates.py` screened all 5,922 original lessons, including full original text, every utterance and structured call signatures, against the existing original/practical/historical evaluation custody indexes. It did not score or disclose protected cases. The immutable receipt is `data/own-base-tool-candidates/custody.json`, with input/code hashes and exact excluded source IDs.

| Split | Reviewed | Excluded | Retained assistant targets |
|---|---:|---:|---:|
| Train | 5,488 | 154 | 225,426 |
| Exposed development | 434 | 12 | 17,834 |

The 26.7-second CPU screen preserved STOP, memory, time and disk safeguards. Root separately reran all 11 adapter unit tests. These establish tested wiring and overlap screening only. Independent family semantics review, post-exclusion packing validation and explicit training admission remain outstanding. Exposed development is not a sealed evaluation.
