# Diagnostic chat alignment result

The frozen build and full fresh-process reload passed in 402.2 seconds from freeze. No model or GPU was used. The build retains the state `prepared_for_diagnostic_pending_independent_verification`; the subsequent separate independent verification receipt is now PASS. This is formatting/packing evidence, not training admission, teacher-quality certification or assistant capability.

| Split | Retained histories | Prefix rows | Assistant targets |
| --- | ---: | ---: | ---: |
| Train | 22,143 | 29,082 | 3,707,850 |
| Validation | 394 | 511 | 64,228 |

Context alignment refused 646/22,789 train histories (2.83%) and 14/408 validation histories (3.43%), all from Magpie. These remove 285,651 train and 6,426 validation original targets. Summarize and rewrite retain every surviving source history. Entire histories are refused; no tail truncation or answer edits occur. Retained original target totals equal aligned supervised target totals, so prefix expansion does not duplicate supervision.

The separate little-endian uint16 streams, indices and refusal list occupy 77,694,863 bytes. Index records retain source/document/turn/family/split/offset/length/target count/original-history hash; raw histories remain in the original pinned database. Actual process observations were approximately 63–66 MiB RSS at nice10; runtime checked the 200 MiB ceiling, 3 GiB output limit, 20 GiB free-disk floor, STOP files and 15-minute aggregate deadline. Tokenizer/library threads were constrained to one.

Supervised predicted-token exposure across both splits is: positions 0–255: **0**; 256–511: **2,349,816**; 512–767: **1,290,865**; 768–1023: **131,397**. The host policy and prompt consume the early positions. These are target counts, not unique tokens or quality scores.

`data/own-base-chat-aligned-v1/reload-verification.json` confirms exact reserialization and byte comparison of every row, current-turn masks, original-history hashes, index bounds/contiguity, target counts, family splits, cumulative exclusions and re-evaluation of every omitted eligible history. All frozen code/input pins were rechecked.

The separate root-authored `verify_independent.py` passed all structural stream ranges, shifts, masks/counts, positions, exclusion IDs and split/family checks. It also reserialized 48 fixed hash-stratified rows (eight per cohort/split) directly through `dialogue._frames`, independently of the builder/chat-row helper, including publisher-system relocation. Evidence: `data/own-base-chat-aligned-v1/independent-verification.json`. Both verification receipts reference build receipt SHA256 `7970c9c35c76f1bfcc2dfded6589846db365e51166a84636a170de61b701b609`.

Limitations: the independent serializer audit covers 48 rows; full source reserialization uses the same helper as the builder. Per-cohort original before/refused target counters are builder-reported and have not been independently recomputed; accepted per-cohort counts and global target totals were checked. Lexical source screening and instruction relocation do not establish semantic correctness, fact preservation or useful model behavior. No SFT allocation, training launch or promotion is implied.
