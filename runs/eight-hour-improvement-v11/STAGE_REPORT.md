# V11 corrected-menu trial

One bounded 1M-input-token stage from V9 at LR 1e-5. Expanded 480 tool menus, removed 428 unverified upstream examples, and reduced small-teacher oversampling. Data/mixture changes occur together, so this is not a causal ablation.

| Strict development metric | V9 | V11 |
| --- | ---: | ---: |
| Fully correct conversations | 3/40 | 4/40 |
| Fully correct turns | 10/80 | 10/80 |
| Complete tool conversations | 2/10 | 3/10 |
| Exact required calls | 4/8 | 5/8 |
| Required abstentions | 2/2 | 2/2 |

All 80 replies and post-tool answers were read by the assistant. This is not independent human review. V11 is the best experimental candidate so far, but 10% conversation accuracy is inadequate. Only one of 30 prose conversations fully passed. Confirmation remains untouched.

## Actual outputs

User: Use the calculator to divide 42 by zero.

Student call: `<|tool_call|>{"name":"calculate","arguments":{"op":"divide","a":42,"b":0}}`

Fixture: `{"error":"division by zero"}`

Student: The calculator reports division by zero. A nonzero divisor is required.

User: What must the divisor be for a valid division?

Student: The calculator reports division by zero. A nonzero divisor is required.

Failure: for 7 × 8 the correct fixture returned 56, but the student answered and recalled 61. For 6 km to metres the correct result was 6000 m, but the student final answer used cm.

## Next decision

Preserve V11. Test a fresh SFT lineage from the existing 200M-token pretrained foundation, which has the same 97,536,768 parameters and tokenizer. V12 uses the corrected dataset and an initial 1M-token stage at LR 3e-5, then strict development review. It does not resume old pretraining or use the new quarantined teacher expansion. Original deadline and resource guards remain unchanged.
