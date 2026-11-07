# Independent grounded packed-stream reload

All three prepared sources passed exhaustive verification; exact receipt/proof hashes and counts are in results.json. This is not training admission.

verify.py imports no packer, production serializer, tool adapter or row builder. It reuses the separately reviewed and hash-pinned independent frame interpreter from tool-review/verify.py. For chat it reconstructs every alternating user/assistant prefix under the independently stated host policy; for tools it independently restores original recorded observations and all turn prefixes. It compares every uint16 input/label byte and every index field, checks union exclusions, complete inventory, no trailing/unindexed bytes, immutable artifacts, exact target/position totals and family split separation. Tool semantics remain supported by the separately pinned candidate-verification receipt; this reload is a structural/frame proof, not a second claim of independent semantic review.

The four-call source additionally checks all 552 retained histories have four successful actual offline observations, with 2+2+0 calls and three retained prefix rows. A separate root admission/qualification still follows. All three sources had zero union exclusions; the verifier nevertheless requires both actual custody receipts and the union equality.

Run bounds are 30 minutes, 1.5 GiB RSS, 20 GiB disk floor and source/output/root STOP checks. Completed independent receipts are immutable. A mismatch raises without writing PASS. No source candidate, custody proof or packed stream was changed.
