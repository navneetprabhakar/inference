# Explicit-choice decoder diagnosis

**Keep this forced-choice method experimental.** Restricting selection to the two labels in the user's instruction guaranteed the requested output format on all 64 cases. The calibrated decoder selected the correct option in **both counterfactual members for only 2/32 pairs**, and returned the same option in **30/32 pairs** despite a changed fact.

| Method | Both correct, yes/no | Both correct, shortlist | Both correct, total | Correct individual answers |
|---|---:|---:|---:|---:|
| Raw greedy, strict requested format | 0/16 | 0/16 | 0/32 | 0/64 |
| Raw greedy, semantic judgment | 0/16 | 0/16 | 0/32 | 0/64 |
| Direct completion likelihood, secondary | 2/16 | 2/16 | 4/32 | 36/64 |
| Neutral-calibrated likelihood, primary | 1/16 | 1/16 | 2/32 | 34/64 |

One raw reply began with an affirmative to a question about an outbound shuttle traveling toward the station, which was wrong. One shortlist pair produced incoherent references to “second” and “first.” Even giving the pair full semantic credit for those ordinals yields only **1/32 raw pairs**, so the promotion decision is unchanged. The decoder emitted a parseable text frame on **41/64** raw final turns. These tests measure the raw checkpoint's answers under the explicit unfamiliar instructions, not all its capabilities.

**Example.** The first wax inspection selected ochre, then its otherwise identical counterpart selected olive. The calibrated scorer chose olive both times. Because every pair has one of each correct label, any method that gives a constant choice within every pair earns exactly 32/64 individual answers, while passing zero whole pairs. The calibrated method was only two correct individual answers above that floor.

## Experimental control

- Preregistered 32 independently written scenarios: 16 yes/no and 16 arbitrary two-label options. Both targets occur within every pair; order and which member has which outcome are balanced. For eight pairs, the fact appears in an earlier user turn. The model generates the actual first response once per member. The final raw and constrained methods see the exact same token prefix, including that response. Conditional and direct-copy tasks are both represented. No protected conversation set was consulted.
- The primary score sums token log probabilities for each permissible full assistant JSON frame, including EOT, then subtracts the same completion's log probability under a neutral instruction listing the identical options in the same order. The secondary uncalibrated score uses the first term alone. Gold labels, semantic parsing and symbolic task rules never enter either score. The wrapper supplies output candidates directly and enforces formatting.
- The precommitted promotion gate required at least 20/32 primary pairs, at least 8/16 in each class, and at least five more fully correct pairs than the raw semantic result. Every threshold failed. No threshold sweep, model update, live UI change or integration occurred.
- Working-chat-02 checkpoint SHA-256 `c83f9792200747cf20c9f93ff92087fa0dba45d7c54a9af7581454f019e53609`. Protocol SHA-256 `28363d30dce84e7b411b83593e2a31172440b802297e8c6a5b263e919fc48f43`. Run used one CPU thread and took 283 seconds. `protocol.json`, `scores.json` and `transcripts.jsonl` preserve each input, expected answer, actual prior/raw replies, candidate likelihoods, selections and judgments.
