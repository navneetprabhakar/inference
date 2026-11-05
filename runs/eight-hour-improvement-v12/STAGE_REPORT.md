# Fresh 200M-token foundation: rejected after bounded alignment trial

Student remains 97,536,768 parameters. This trial used the separately retained 200M-token pretraining checkpoint, not the prior SFT lineage. All results below are development results; confirmation remains untouched.

| SFT input stage | Fully correct conversations | Correct turns | Full tool conversations | Exact required calls | Required abstentions |
|---|---:|---:|---:|---:|---:|
| 1,000,465 | 0/40 | 6/80 | 0/10 | 1/8 | 0/2 |
| 2,000,299 | 0/40 | 4/80 | 0/10 | 1/8 | 0/2 |
| V11 reference | 4/40 | 10/80 | 3/10 | 5/8 | 2/2 |

Actual final outputs:
- User: Use the calculator to multiply 7 by 8.
- Student call: calculate(op=divide, a=7, b=8). Fixture: 0.875. Student: The result is 0.875.
- User: A classroom has 18 pencils and receives 7 more. How many pencils are there now?
- Student: 10 pencils.
- User: Please turn 'send the draft today' into a polite request. Write one sentence.
- Student: Could you please send the draft today?
- Follow-up: Did the wording remain a request rather than an order?
- Student: No. The draft is still for the purpose of meeting deadlines.

Decision: stop this lineage; retain actual outputs and both evaluated checkpoints. More alignment on this same curriculum did not improve development performance. This is not an isolated causal comparison of pretraining length: initial lineage and SFT learning rate differ from V11. Per-case review is by the parent assistant, not an independent human.
